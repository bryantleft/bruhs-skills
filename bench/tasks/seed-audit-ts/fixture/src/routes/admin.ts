import express, { Router } from "express";
import { requireAdmin } from "../auth.js";
import type { Config } from "../config.js";
import { orderItems, type DB } from "../db.js";
import { HttpError, notFound } from "../errors.js";
import { parsePriceCents } from "../lib/money.js";
import { refundPayment } from "../lib/payments.js";
import { summarize, topBy } from "../lib/stats.js";
import type { Order } from "../types.js";

export function adminRouter(db: DB, config: Config): Router {
  const router = Router();

  router.get("/stats", (_req, res) => {
    const totals = db
      .prepare("SELECT total_cents FROM orders WHERE status IN ('paid', 'shipped')")
      .all() as { total_cents: number }[];
    const customers = db
      .prepare(
        `SELECT u.email, u.name, SUM(o.total_cents) AS spent
           FROM orders o JOIN users u ON u.id = o.user_id
          WHERE o.status IN ('paid', 'shipped')
          GROUP BY u.id`,
      )
      .all() as { email: string; name: string; spent: number }[];
    res.json({
      ...summarize(totals.map((t) => t.total_cents)),
      topCustomers: topBy(customers, (c) => c.spent, 10),
    });
  });

  router.use(requireAdmin(config.adminKey));

  router.post("/products/import", express.text({ type: "text/csv" }), (req, res) => {
    if (typeof req.body !== "string") {
      throw new HttpError(415, "send the CSV as text/csv");
    }
    const lines = req.body.split(/\r?\n/).filter((line) => line.trim() !== "");
    const upsert = db.prepare(
      `INSERT INTO products (sku, name, price_cents, stock) VALUES (?, ?, ?, ?)
       ON CONFLICT(sku) DO UPDATE SET name = excluded.name,
         price_cents = excluded.price_cents, stock = excluded.stock`,
    );
    for (const line of lines.slice(1)) {
      try {
        const [sku, name, price, stock] = line.split(",").map((cell) => cell.trim());
        upsert.run(sku, name, parsePriceCents(price), Number.parseInt(stock, 10));
      } catch {
        continue;
      }
    }
    res.json({ imported: lines.length - 1 });
  });

  router.get("/orders/export", (req, res) => {
    const since = String(req.query.since ?? "1970-01-01");
    const orders = db
      .prepare("SELECT * FROM orders WHERE created_at >= ? ORDER BY id")
      .all(since) as unknown as Order[];
    res.json({
      since,
      orders: orders.map((order) => ({ ...order, items: orderItems(db, order.id) })),
    });
  });

  router.post("/orders/:id/refund", async (req, res) => {
    const order = db
      .prepare("SELECT * FROM orders WHERE id = ?")
      .get(Number(req.params.id)) as unknown as Order | undefined;
    if (!order) {
      throw notFound("order");
    }
    if (order.status !== "paid" || !order.payment_ref) {
      throw new HttpError(409, `order is ${order.status}, only paid orders can be refunded`);
    }
    const refund = await refundPayment(config.paymentsUrl, order.payment_ref, order.total_cents);
    db.prepare("UPDATE orders SET status = 'refunded' WHERE id = ?").run(order.id);
    res.json({ orderId: order.id, ...refund });
  });

  return router;
}
