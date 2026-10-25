import { Router } from "express";
import { requireUser } from "../auth.js";
import type { Config } from "../config.js";
import { inTransaction, orderItems, type DB } from "../db.js";
import { HttpError, notFound } from "../errors.js";
import { orderTotal } from "../lib/money.js";
import { pageMeta, parsePage } from "../lib/pagination.js";
import { parseOrderInput } from "../lib/validate.js";
import { deliverWebhook } from "../lib/webhooks.js";
import type { Order, Product } from "../types.js";

const SORTABLE = new Map([
  ["created", "created_at"],
  ["total", "total_cents"],
]);

export function ordersRouter(db: DB, config: Config): Router {
  const router = Router();
  router.use(requireUser(db));

  router.get("/", (req, res) => {
    const page = parsePage(req.query);
    const column = SORTABLE.get(String(req.query.sort)) ?? "created_at";
    const direction = req.query.dir === "asc" ? "ASC" : "DESC";
    const orders = db
      .prepare(
        `SELECT * FROM orders WHERE user_id = ?
          ORDER BY ${column} ${direction}
          LIMIT ? OFFSET ?`,
      )
      .all(req.user.id, page.pageSize, page.offset) as unknown as Order[];
    const { total } = db
      .prepare("SELECT COUNT(*) AS total FROM orders WHERE user_id = ?")
      .get(req.user.id) as { total: number };
    res.json({
      orders,
      ...pageMeta(page, total),
    });
  });

  router.get("/search", (req, res) => {
    const q = String(req.query.q ?? "").trim();
    if (q.length < 2) {
      throw new HttpError(400, "query must be at least 2 characters");
    }
    const orders = db
      .prepare(
        `SELECT * FROM orders
          WHERE user_id = ${req.user.id} AND note LIKE '%${q}%'
          ORDER BY created_at DESC LIMIT 50`,
      )
      .all();
    res.json({ orders });
  });

  router.get("/:id", (req, res) => {
    const order = db
      .prepare("SELECT * FROM orders WHERE id = ?")
      .get(Number(req.params.id)) as unknown as Order | undefined;
    if (!order) {
      throw notFound("order");
    }
    res.json({ ...order, items: orderItems(db, order.id) });
  });

  router.post("/", (req, res) => {
    const input = parseOrderInput(req.body);
    const getProduct = db.prepare("SELECT * FROM products WHERE id = ?");
    const takeStock = db.prepare("UPDATE products SET stock = stock - ? WHERE id = ?");

    const order = inTransaction(db, () => {
      const lines = input.items.map((item) => {
        const product = getProduct.get(item.productId) as unknown as Product | undefined;
        if (!product) {
          throw new HttpError(400, `unknown product ${item.productId}`);
        }
        if (product.stock < item.quantity) {
          throw new HttpError(409, `not enough stock for ${product.sku}`);
        }
        takeStock.run(item.quantity, product.id);
        return { product, quantity: item.quantity, unitPriceCents: product.price_cents };
      });
      const total = orderTotal(lines);
      const { lastInsertRowid } = db
        .prepare("INSERT INTO orders (user_id, total_cents, note) VALUES (?, ?, ?)")
        .run(req.user.id, total, input.note ?? null);
      const insertItem = db.prepare(
        `INSERT INTO order_items (order_id, product_id, quantity, unit_price_cents)
         VALUES (?, ?, ?, ?)`,
      );
      for (const line of lines) {
        insertItem.run(lastInsertRowid, line.product.id, line.quantity, line.unitPriceCents);
      }
      return db
        .prepare("SELECT * FROM orders WHERE id = ?")
        .get(lastInsertRowid) as unknown as Order;
    });

    if (config.webhookUrl) {
      deliverWebhook(db, config.webhookUrl, "order.created", order).catch((err) =>
        console.error("order.created webhook crashed", err),
      );
    }
    res.status(201).json({ ...order, items: orderItems(db, order.id) });
  });

  return router;
}
