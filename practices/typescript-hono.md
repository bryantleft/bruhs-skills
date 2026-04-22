# TypeScript + Hono Best Practices

Hono is a small, fast, edge-native web framework. Built on Web Standards (`Request`/`Response`), runs anywhere — Cloudflare Workers, Vercel Edge, Deno, Bun, Node, AWS Lambda. Loaded by `cook` and `slop` when `framework: hono` is detected.

Sources: official [Hono docs](https://hono.dev/docs), [Hono Best Practices guide](https://hono.dev/docs/guides/best-practices), [Hono RPC docs](https://hono.dev/docs/guides/rpc).

## Contents

- [Mental Model](#mental-model)
- [Project Structure](#project-structure)
- [Pillar 1: Keep the Chain Inline](#pillar-1-keep-the-chain-inline)
- [Pillar 2: One `Hono()` Per Resource — Mounted](#pillar-2-one-hono-per-resource--mounted)
- [Pillar 3: Typed Bindings and Variables](#pillar-3-typed-bindings-and-variables)
- [Pillar 4: Validation with Zod](#pillar-4-validation-with-zod)
- [Pillar 5: Typed Middleware](#pillar-5-typed-middleware)
- [Pillar 6: RPC — End-to-End Type Safety Without Codegen](#pillar-6-rpc--end-to-end-type-safety-without-codegen)
- [Pillar 7: Errors](#pillar-7-errors)
- [Pillar 8: Edge-Native Discipline](#pillar-8-edge-native-discipline)
- [Pillar 9: Testing](#pillar-9-testing)
- [Pillar 10: Performance](#pillar-10-performance)
- [Quick Reference](#quick-reference)
- [References](#references)

---

## Mental Model

> **Type inference flows through chained methods.** Break the chain and you lose end-to-end type safety. Keep handlers inline; abstract through `factory.createMiddleware()` and `factory.createHandlers()`, not loose helpers.

The Hono superpower is that the *same* type definition produces:
- Validated request inputs (via `zValidator` etc.)
- Typed response shapes
- A typed RPC client (`hc<typeof app>`) — no codegen, no schema export

This only works if you keep the inference chain intact.

---

## Project Structure

```
src/
├── index.ts                    # main app, mounts routers
├── env.ts                      # Bindings type (Cloudflare Workers vars/secrets)
├── middleware/
│   ├── auth.ts                 # createMiddleware-based
│   └── logger.ts
├── routes/
│   ├── users.ts                # one Hono() instance per resource
│   └── orders.ts
├── schemas/
│   └── user.ts                 # Zod schemas
├── services/
│   └── userService.ts
└── lib/
    └── db.ts
```

---

## Pillar 1: Keep the Chain Inline

> *"To get the most out of Hono's type-safety, chain methods and implement handlers inline rather than abstracting them."* — Hono best practices guide

```typescript
// ❌ Loses type inference at the boundary
const handleGetUser = async (c) => {  // c has no type
  const id = c.req.param("id");
  const user = await db.findUser(id);
  return c.json(user);
};

app.get("/users/:id", handleGetUser);

// ✅ Inline — c is fully typed, including any middleware-injected vars
app.get("/users/:id", async (c) => {
  const id = c.req.param("id");           // typed as string
  const user = c.get("user");             // typed if auth middleware was applied
  const data = await db.findUser(id);
  return c.json(data);                    // response shape inferred
});
```

If you need to split handlers (long file, reuse), use **`factory.createHandlers()`** rather than plain functions.

```typescript
import { createFactory } from "hono/factory";
const factory = createFactory<{ Bindings: Env; Variables: { user: User } }>();

export const getUser = factory.createHandlers(async (c) => {
  const id = c.req.param("id");
  const data = await db.findUser(id);
  return c.json(data);
});

// In the route file:
app.get("/users/:id", ...getUser);
```

`createHandlers` preserves the typed Context (`Bindings`, `Variables`) you've configured.

---

## Pillar 2: One `Hono()` Per Resource — Mounted

```typescript
// routes/users.ts
import { Hono } from "hono";
import type { Env } from "../env";

const users = new Hono<{ Bindings: Env }>();

users.get("/", async (c) => { /* list */ });
users.post("/", async (c) => { /* create */ });
users.get("/:id", async (c) => { /* get */ });

export default users;

// index.ts
import { Hono } from "hono";
import users from "./routes/users";
import orders from "./routes/orders";

const app = new Hono<{ Bindings: Env }>();
app.route("/users", users);
app.route("/orders", orders);

export default app;
```

This is the **only** structure that produces a usable type for `hc<typeof app>` — chained `.route()` calls preserve the path-to-handler mapping.

---

## Pillar 3: Typed Bindings and Variables

```typescript
// env.ts — declared once, used everywhere
export type Env = {
  Bindings: {
    DATABASE_URL: string;        // Cloudflare secret
    KV: KVNamespace;             // Cloudflare KV namespace
    BUCKET: R2Bucket;            // R2 bucket
  };
  Variables: {
    user: User;                  // set by auth middleware
    requestId: string;           // set by request-id middleware
  };
};
```

`Bindings` are runtime-provided (from `wrangler.toml` / Vercel env vars / `process.env`). `Variables` are populated by your middleware and accessible via `c.get()` / `c.set()`.

```typescript
const app = new Hono<Env>();

app.use("*", async (c, next) => {
  c.set("requestId", crypto.randomUUID());
  await next();
});

app.get("/me", (c) => {
  const reqId = c.get("requestId");        // typed as string
  const user = c.get("user");              // typed as User
  return c.json({ user, reqId });
});
```

---

## Pillar 4: Validation with Zod

Use `@hono/zod-validator` to validate inputs and get typed `c.req.valid()`:

```typescript
import { Hono } from "hono";
import { z } from "zod";
import { zValidator } from "@hono/zod-validator";

const CreateUser = z.object({
  email: z.string().email(),
  age: z.number().int().positive(),
});

const users = new Hono();

users.post(
  "/",
  zValidator("json", CreateUser),
  async (c) => {
    const body = c.req.valid("json");      // typed: { email: string; age: number }
    const created = await db.createUser(body);
    return c.json(created, 201);
  },
);

users.get(
  "/",
  zValidator("query", z.object({ limit: z.coerce.number().default(20) })),
  async (c) => {
    const { limit } = c.req.valid("query");  // limit: number, defaulted
    const list = await db.listUsers(limit);
    return c.json(list);
  },
);
```

`zCoerce.number()` parses query strings (`?limit=50`) into numbers. `zValidator` short-circuits with a 400 + structured error if validation fails — wire a custom failure handler if you want a different shape:

```typescript
zValidator("json", CreateUser, (result, c) => {
  if (!result.success) {
    return c.json({ error: "validation", issues: result.error.issues }, 400);
  }
});
```

---

## Pillar 5: Typed Middleware

`createMiddleware` from `hono/factory` preserves type safety, including writes to `Variables`:

```typescript
// middleware/auth.ts
import { createMiddleware } from "hono/factory";
import type { Env } from "../env";

export const requireAuth = createMiddleware<Env>(async (c, next) => {
  const token = c.req.header("authorization")?.replace(/^Bearer\s+/, "");
  if (!token) return c.json({ error: "missing token" }, 401);

  const user = await verifyJwt(token, c.env.JWT_SECRET);
  if (!user) return c.json({ error: "invalid token" }, 401);

  c.set("user", user);                     // typed write into Variables
  await next();
});

// Usage — c.get("user") is typed downstream
app.get("/me", requireAuth, (c) => {
  const user = c.get("user");
  return c.json(user);
});
```

Order matters: middleware runs in the order applied. Apply `requireAuth` *before* the handler, not after.

---

## Pillar 6: RPC — End-to-End Type Safety Without Codegen

The killer feature. Export the app type and import it in the client:

```typescript
// server (src/index.ts)
const app = new Hono()
  .post("/users",
    zValidator("json", CreateUser),
    async (c) => {
      const body = c.req.valid("json");
      const user = await db.createUser(body);
      return c.json(user, 201);
    })
  .get("/users/:id", async (c) => {
    const user = await db.findUser(c.req.param("id"));
    if (!user) return c.json({ error: "not found" }, 404);
    return c.json(user);
  });

export type AppType = typeof app;        // export the inferred type
export default app;
```

```typescript
// client (anywhere — same monorepo, separate package, even another repo via npm)
import { hc } from "hono/client";
import type { AppType } from "@my/server";

const client = hc<AppType>("https://api.example.com");

const res = await client.users.$post({
  json: { email: "a@b.co", age: 30 },    // typed — wrong shape = compile error
});

if (res.ok) {
  const user = await res.json();         // typed: User
}

// Path params + query
const res2 = await client.users[":id"].$get({ param: { id: "42" } });
```

**No schema sharing infrastructure. No codegen. No runtime cost** — just TypeScript inference.

### Caveats

- Works only if the `app` instance is assembled with chained `.method()` calls (no loose `app.get(...)` after construction). The chain *is* the type.
- The client uses `fetch` under the hood — works in browsers, Cloudflare Workers, Deno, Bun, Node 18+.
- Headers/auth pass through as `init` options.

---

## Pillar 7: Errors

### Centralized error handler

```typescript
import { HTTPException } from "hono/http-exception";

const app = new Hono();

app.onError((err, c) => {
  if (err instanceof HTTPException) {
    return err.getResponse();              // honors HTTPException's status + message
  }
  console.error(err);
  return c.json({ error: "internal" }, 500);
});

// Throw HTTPException from handlers
app.get("/users/:id", async (c) => {
  const user = await db.findUser(c.req.param("id"));
  if (!user) throw new HTTPException(404, { message: "user not found" });
  return c.json(user);
});
```

### Don't swallow errors in middleware

Hono short-circuits if you `return` a response from middleware. If middleware throws, `onError` catches it. Don't swallow — let the error reach `onError`.

```typescript
// ❌ Hides the failure
const safe = createMiddleware(async (c, next) => {
  try { await next(); }
  catch (e) { console.log(e); /* request just dies silently */ }
});

// ✅ Either handle and convert, or let it propagate
```

---

## Pillar 8: Edge-Native Discipline

Hono runs on *Web Standards*. Code you write should run on every supported runtime — don't reach for Node-specific APIs unless you're sure your deploy target is Node-only.

| Don't use | Use instead |
|-----------|-------------|
| `fs.readFile` | `c.env.BUCKET.get()` (R2), or fetch a URL, or KV |
| `process.env.X` | `c.env.X` (typed via `Bindings`) |
| `Buffer` | `Uint8Array` / `ArrayBuffer` |
| `setInterval` | Cron triggers (`scheduled` handler) |
| Long-lived connections | Cloudflare Durable Objects / `WebSocket` standard |

### Cloudflare Workers `wrangler.toml`

```toml
name = "my-api"
main = "src/index.ts"
compatibility_date = "2026-04-01"
compatibility_flags = ["nodejs_compat"]   # only if needed

[[kv_namespaces]]
binding = "KV"
id = "..."

[[r2_buckets]]
binding = "BUCKET"
bucket_name = "my-bucket"

[vars]
PUBLIC_API_URL = "https://api.example.com"

# Secrets are added via: wrangler secret put DATABASE_URL
```

The same Hono code with the same type definitions runs on Vercel Edge or Bun — change runtime, change deploy command, the app code doesn't change.

---

## Pillar 9: Testing

Hono ships with a perfect test client — no HTTP server needed:

```typescript
// app.test.ts
import { describe, it, expect } from "vitest";
import app from "./index";

describe("users", () => {
  it("creates a user", async () => {
    const res = await app.request("/users", {
      method: "POST",
      headers: { "content-type": "application/json" },
      body: JSON.stringify({ email: "a@b.co", age: 30 }),
    });
    expect(res.status).toBe(201);
    const body = await res.json();
    expect(body.email).toBe("a@b.co");
  });

  it("rejects invalid email", async () => {
    const res = await app.request("/users", {
      method: "POST",
      headers: { "content-type": "application/json" },
      body: JSON.stringify({ email: "not-an-email", age: 30 }),
    });
    expect(res.status).toBe(400);
  });
});
```

Pass `Bindings` for tests against a worker:

```typescript
const res = await app.request("/protected", {}, {
  KV: mockKv, DATABASE_URL: "sqlite::memory:",
});
```

---

## Pillar 10: Performance

> **Edge is pointless without caching, streaming, and `waitUntil`.** These aren't optimizations — they're the defaults.

Hono is already fast. What matters is not defeating it.

### Parallelize Independent Awaits

```typescript
// ❌ Two roundtrips
const user = await db.getUser(id);
const orders = await db.getOrders(id);

// ✅ One
const [user, orders] = await Promise.all([db.getUser(id), db.getOrders(id)]);
```

### Cache at the Edge

Cloudflare's `caches.default` is free, global, and per-colo:

```typescript
app.get("/popular", async (c) => {
  const cache = caches.default;
  const cacheKey = new Request(c.req.url, c.req.raw);
  const hit = await cache.match(cacheKey);
  if (hit) return hit;

  const data = await expensiveLookup();
  const res = c.json(data);
  res.headers.set("cache-control", "public, max-age=60, s-maxage=300, stale-while-revalidate=60");
  c.executionCtx.waitUntil(cache.put(cacheKey, res.clone()));
  return res;
});
```

Always set `Cache-Control` with `s-maxage` + `stale-while-revalidate` on cacheable routes. On Workers, use `fetch(url, { cf: { cacheTtl, cacheEverything } })` for upstream caching.

### `waitUntil` for After-Response Work

```typescript
app.post("/event", async (c) => {
  const body = await c.req.json();
  c.executionCtx.waitUntil(logToAnalytics(body));   // doesn't delay response
  return c.json({ ok: true });
});
```

Use for: analytics, cache warming, audit logging, webhook fanout. Never `await` these before returning.

### Stream Large / LLM Responses

```typescript
import { streamSSE } from "hono/streaming";

app.get("/chat", (c) =>
  streamSSE(c, async (stream) => {
    for await (const chunk of llm.stream(prompt)) {
      await stream.writeSSE({ data: chunk });
    }
  })
);
```

Never buffer large responses — memory is tight at the edge, and time-to-first-byte is a user-visible metric.

### Small Response Shapes

```typescript
// ❌ Returning the whole ORM object — includes hydration metadata, relation keys
return c.json(await db.user.findFirst({ where: { id } }));

// ✅ Project to the shape the client needs
const user = await db.user.findFirst({ where: { id }, select: { id: true, name: true, avatarUrl: true } });
return c.json(user);
```

### Route-Level Middleware, Not Global

```typescript
// ❌ Runs on every request, including static + health checks
app.use(heavyAuthMiddleware);

// ✅ Only where it matters
app.use("/api/*", heavyAuthMiddleware);
```

### Keep Bundles Small (Cold Start Dominates at the Edge)

- Prefer **Valibot** over Zod where size matters (Hono supports both via `@hono/valibot-validator`)
- Use `hono/tiny` if you're bundle-budget sensitive
- Avoid Node-only deps (`fs`, `Buffer`, `crypto.createHash` old form) — they break on Workers/Deno and bloat bundles

### Singleton Clients

```typescript
// ❌ New client per request — no connection reuse
app.get("/users", async (c) => {
  const db = new Database(c.env.DATABASE_URL);
  return c.json(await db.query(...));
});

// ✅ Initialize once at module scope (or middleware with cache)
let db: Database | null = null;
app.use(async (c, next) => {
  if (!db) db = new Database(c.env.DATABASE_URL);
  c.set("db", db);
  await next();
});
```

### Traps

- **Awaiting analytics before returning.** Always `waitUntil`.
- **Global mutable state for caching** — per-isolate, not shared across the fleet. Use KV / D1 / Durable Objects.
- **Exotic route patterns** that defeat Hono's `RegExpRouter` / `TrieRouter` selection.

### Performance Checklist

- [ ] `Promise.all` for independent awaits
- [ ] `Cache-Control` + `s-maxage` + `stale-while-revalidate` on cacheable GETs
- [ ] `caches.default.match` / `put` for edge caching
- [ ] `c.executionCtx.waitUntil(...)` for logging, analytics, cache warming
- [ ] `streamSSE` / `stream` for LLM, long queries, large payloads
- [ ] Response shapes projected to what the client needs (no whole ORM objects)
- [ ] Middleware scoped to routes that need it
- [ ] No Node-only deps on Workers/Deno targets
- [ ] DB / Redis / upstream clients initialized once, not per request

---

## Quick Reference

### Always
- [ ] Chain `.method()` calls on the app instance — never break inference
- [ ] One `Hono()` per resource, mounted via `.route()` in main
- [ ] `Env` type with `Bindings` + `Variables`, applied as `Hono<Env>`
- [ ] `zValidator` on every endpoint that takes a body / query / params
- [ ] `createMiddleware` / `createHandlers` from `hono/factory` — never plain functions
- [ ] Export `AppType = typeof app` for RPC clients
- [ ] Centralized `app.onError`; throw `HTTPException` for status + message
- [ ] `c.env.X` (not `process.env.X`); Web Standards APIs

### Avoid
- [ ] Loose handler functions outside the chain (kills type inference)
- [ ] `app.get(...)` in two separate places (re-assembling the app drops RPC types)
- [ ] Node-only APIs unless deploy target is Node
- [ ] Swallowing errors in middleware
- [ ] Long sequential `await` chains where `Promise.all` would do
- [ ] Hardcoded secrets — use `c.env.*` (and Cloudflare/Vercel secret stores)

### Testing
- [ ] `app.request(...)` for unit tests — no need to spin a server
- [ ] Pass mocked Bindings for protected routes
- [ ] Vitest with `@cloudflare/vitest-pool-workers` if testing Worker-specific APIs

---

## References

- [Hono official docs](https://hono.dev/docs)
- [Hono Best Practices](https://hono.dev/docs/guides/best-practices) — official
- [Hono RPC](https://hono.dev/docs/guides/rpc) — type-safe client
- [Hono Middleware](https://hono.dev/docs/guides/middleware) — patterns
- [Cloudflare Workers docs](https://developers.cloudflare.com/workers/) — runtime APIs
