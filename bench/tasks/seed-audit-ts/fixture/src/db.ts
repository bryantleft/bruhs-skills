import { DatabaseSync } from "node:sqlite";
import type { OrderItem } from "./types.js";

export type DB = DatabaseSync;

const MIGRATIONS: string[] = [
  `CREATE TABLE users (
     id INTEGER PRIMARY KEY,
     email TEXT NOT NULL UNIQUE,
     name TEXT NOT NULL,
     password_hash TEXT NOT NULL,
     role TEXT NOT NULL DEFAULT 'customer',
     created_at TEXT NOT NULL DEFAULT (datetime('now'))
   );
   CREATE TABLE sessions (
     token TEXT PRIMARY KEY,
     user_id INTEGER NOT NULL REFERENCES users(id) ON DELETE CASCADE,
     expires_at INTEGER NOT NULL
   );`,
  `CREATE TABLE products (
     id INTEGER PRIMARY KEY,
     sku TEXT NOT NULL UNIQUE,
     name TEXT NOT NULL,
     price_cents INTEGER NOT NULL,
     stock INTEGER NOT NULL DEFAULT 0
   );
   CREATE TABLE orders (
     id INTEGER PRIMARY KEY,
     user_id INTEGER NOT NULL REFERENCES users(id),
     status TEXT NOT NULL DEFAULT 'pending',
     total_cents INTEGER NOT NULL,
     note TEXT,
     payment_ref TEXT,
     created_at TEXT NOT NULL DEFAULT (datetime('now'))
   );
   CREATE TABLE order_items (
     id INTEGER PRIMARY KEY,
     order_id INTEGER NOT NULL REFERENCES orders(id) ON DELETE CASCADE,
     product_id INTEGER NOT NULL REFERENCES products(id),
     quantity INTEGER NOT NULL,
     unit_price_cents INTEGER NOT NULL
   );
   CREATE INDEX order_items_order ON order_items(order_id);`,
  `CREATE TABLE webhook_deliveries (
     id INTEGER PRIMARY KEY,
     event TEXT NOT NULL,
     body TEXT NOT NULL,
     status TEXT NOT NULL DEFAULT 'pending',
     attempts INTEGER NOT NULL DEFAULT 0,
     created_at TEXT NOT NULL DEFAULT (datetime('now'))
   );
   CREATE INDEX orders_user ON orders(user_id, created_at);`,
];

export function openDb(path: string): DB {
  const db = new DatabaseSync(path);
  db.exec("PRAGMA foreign_keys = ON");
  migrate(db);
  return db;
}

function migrate(db: DB): void {
  db.exec("CREATE TABLE IF NOT EXISTS schema_version (version INTEGER NOT NULL)");
  const row = db.prepare("SELECT version FROM schema_version").get() as
    | { version: number }
    | undefined;
  if (!row) {
    db.prepare("INSERT INTO schema_version (version) VALUES (0)").run();
  }
  const current = row?.version ?? 0;
  for (let v = current; v < MIGRATIONS.length; v++) {
    db.exec("BEGIN");
    try {
      db.exec(MIGRATIONS[v]);
      db.prepare("UPDATE schema_version SET version = ?").run(v + 1);
      db.exec("COMMIT");
    } catch (err) {
      db.exec("ROLLBACK");
      throw err;
    }
  }
}

export function inTransaction<T>(db: DB, fn: () => T): T {
  db.exec("BEGIN IMMEDIATE");
  try {
    const result = fn();
    db.exec("COMMIT");
    return result;
  } catch (err) {
    db.exec("ROLLBACK");
    throw err;
  }
}

export function orderItems(db: DB, orderId: number): OrderItem[] {
  return db
    .prepare("SELECT * FROM order_items WHERE order_id = ? ORDER BY id")
    .all(orderId) as unknown as OrderItem[];
}
