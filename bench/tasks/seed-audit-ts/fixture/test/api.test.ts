import { afterEach, beforeEach, describe, expect, it } from "vitest";
import { call, seedProducts, signupAndLogin, startServer, type TestServer } from "./helpers.js";

let srv: TestServer;

beforeEach(async () => {
  srv = await startServer();
  seedProducts(srv.db);
});

afterEach(async () => {
  await srv.close();
});

describe("accounts", () => {
  it("signs up and logs in", async () => {
    const signup = await call(srv, "POST", "/signup", {
      email: "Grace@Example.com",
      name: "Grace",
      password: "a long enough password",
    });
    expect(signup.status).toBe(201);
    expect(signup.body.email).toBe("grace@example.com");

    const login = await call(srv, "POST", "/login", {
      email: "grace@example.com",
      password: "a long enough password",
    });
    expect(login.status).toBe(200);
    const me = await call(srv, "GET", "/me", undefined, login.body.token);
    expect(me.body).toMatchObject({ email: "grace@example.com", role: "customer" });
  });

  it("rejects bad credentials and missing tokens", async () => {
    await signupAndLogin(srv);
    const bad = await call(srv, "POST", "/login", { email: "ada@example.com", password: "nope" });
    expect(bad.status).toBe(401);
    expect((await call(srv, "GET", "/orders")).status).toBe(401);
  });

  it("rejects duplicate emails", async () => {
    await signupAndLogin(srv);
    const again = await call(srv, "POST", "/signup", {
      email: "ada@example.com",
      name: "Ada again",
      password: "correct horse battery",
    });
    expect(again.status).toBe(409);
  });
});

describe("orders", () => {
  it("creates an order and takes stock", async () => {
    const token = await signupAndLogin(srv);
    const created = await call(
      srv,
      "POST",
      "/orders",
      { items: [{ productId: 1, quantity: 2 }, { productId: 2, quantity: 1 }], note: "gift" },
      token,
    );
    expect(created.status).toBe(201);
    expect(created.body.total_cents).toBe(4900);
    expect(created.body.items).toHaveLength(2);
    const mug = srv.db.prepare("SELECT stock FROM products WHERE id = 1").get() as { stock: number };
    expect(mug.stock).toBe(8);
  });

  it("refuses orders beyond stock and leaves stock alone", async () => {
    const token = await signupAndLogin(srv);
    const res = await call(
      srv,
      "POST",
      "/orders",
      { items: [{ productId: 1, quantity: 1 }, { productId: 2, quantity: 4 }] },
      token,
    );
    expect(res.status).toBe(409);
    const mug = srv.db.prepare("SELECT stock FROM products WHERE id = 1").get() as { stock: number };
    expect(mug.stock).toBe(10);
  });

  it("finds orders by note", async () => {
    const token = await signupAndLogin(srv);
    await call(srv, "POST", "/orders", { items: [{ productId: 1, quantity: 1 }], note: "birthday mug" }, token);
    await call(srv, "POST", "/orders", { items: [{ productId: 2, quantity: 1 }], note: "for work" }, token);
    const found = await call(srv, "GET", "/orders/search?q=birthday", undefined, token);
    expect(found.status).toBe(200);
    expect(found.body.orders).toHaveLength(1);
    expect(found.body.orders[0].note).toBe("birthday mug");
  });

  it("returns 404 for a missing order", async () => {
    const token = await signupAndLogin(srv);
    expect((await call(srv, "GET", "/orders/999", undefined, token)).status).toBe(404);
  });
});

describe("admin", () => {
  it("needs the admin key to import products", async () => {
    const res = await fetch(`${srv.url}/admin/products/import`, {
      method: "POST",
      headers: { "content-type": "text/csv" },
      body: "sku,name,price,stock\nCAP-01,Cap,15.00,4\n",
    });
    expect(res.status).toBe(403);
  });
});
