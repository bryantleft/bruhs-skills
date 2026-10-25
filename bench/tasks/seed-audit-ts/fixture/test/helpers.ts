import type { AddressInfo } from "node:net";
import type { Server } from "node:http";
import { createApp } from "../src/app.js";
import type { Config } from "../src/config.js";
import { openDb, type DB } from "../src/db.js";

export const ADMIN_KEY = "test-admin-key-0123456789";

export interface TestServer {
  db: DB;
  url: string;
  close: () => Promise<void>;
}

export async function startServer(overrides: Partial<Config> = {}): Promise<TestServer> {
  const db = openDb(":memory:");
  const config: Config = {
    port: 0,
    dbPath: ":memory:",
    adminKey: ADMIN_KEY,
    paymentsUrl: "http://127.0.0.1:9",
    sessionTtlHours: 1,
    ...overrides,
  };
  const server: Server = await new Promise((resolve) => {
    const s = createApp(db, config).listen(0, "127.0.0.1", () => resolve(s));
  });
  const { port } = server.address() as AddressInfo;
  return {
    db,
    url: `http://127.0.0.1:${port}`,
    close: () =>
      new Promise((resolve) => {
        server.close(() => {
          db.close();
          resolve();
        });
      }),
  };
}

export async function call(
  srv: TestServer,
  method: string,
  path: string,
  body?: unknown,
  token?: string,
): Promise<{ status: number; body: any }> {
  const res = await fetch(srv.url + path, {
    method,
    headers: {
      ...(body !== undefined ? { "content-type": "application/json" } : {}),
      ...(token ? { authorization: `Bearer ${token}` } : {}),
    },
    body: body !== undefined ? JSON.stringify(body) : undefined,
  });
  const text = await res.text();
  return { status: res.status, body: text ? JSON.parse(text) : null };
}

export async function signupAndLogin(srv: TestServer, email = "ada@example.com") {
  await call(srv, "POST", "/signup", { email, name: "Ada", password: "correct horse battery" });
  const login = await call(srv, "POST", "/login", { email, password: "correct horse battery" });
  return login.body.token as string;
}

export function seedProducts(db: DB) {
  const insert = db.prepare(
    "INSERT INTO products (sku, name, price_cents, stock) VALUES (?, ?, ?, ?)",
  );
  insert.run("MUG-01", "Mug", 1200, 10);
  insert.run("TEE-01", "T-shirt", 2500, 3);
}
