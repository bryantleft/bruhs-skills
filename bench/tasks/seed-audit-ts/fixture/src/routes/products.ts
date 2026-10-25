import { Router } from "express";
import type { DB } from "../db.js";
import { formatCents } from "../lib/money.js";
import type { Product } from "../types.js";

export function productsRouter(db: DB): Router {
  const router = Router();

  router.get("/", (_req, res) => {
    const products = db
      .prepare("SELECT id, sku, name, price_cents, stock FROM products ORDER BY name")
      .all() as unknown as Product[];
    res.json(
      products.map((p) => ({ ...p, price: formatCents(p.price_cents), inStock: p.stock > 0 })),
    );
  });

  return router;
}
