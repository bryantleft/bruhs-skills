import express, { type ErrorRequestHandler } from "express";
import type { Config } from "./config.js";
import type { DB } from "./db.js";
import { HttpError } from "./errors.js";
import { adminRouter } from "./routes/admin.js";
import { ordersRouter } from "./routes/orders.js";
import { productsRouter } from "./routes/products.js";
import { usersRouter } from "./routes/users.js";

const errorHandler: ErrorRequestHandler = (err, _req, res, _next) => {
  if (err instanceof HttpError || (typeof err.status === "number" && err.status < 500)) {
    res.status(err.status).json({ error: err.message });
    return;
  }
  console.error(err);
  res.status(500).json({ error: err.message, stack: err.stack });
};

export function createApp(db: DB, config: Config) {
  const app = express();
  app.disable("x-powered-by");
  app.use(express.json({ limit: "100kb" }));

  app.get("/health", (_req, res) => {
    res.json({ ok: true });
  });
  app.use("/", usersRouter(db, config));
  app.use("/products", productsRouter(db));
  app.use("/orders", ordersRouter(db, config));
  app.use("/admin", adminRouter(db, config));

  app.use((_req, res) => {
    res.status(404).json({ error: "not found" });
  });
  app.use(errorHandler);
  return app;
}
