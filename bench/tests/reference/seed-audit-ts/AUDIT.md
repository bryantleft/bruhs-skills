# Audit: orderdesk-api

Each finding is `### [severity] file:lines`.

## Security

### [critical] src/routes/orders.ts:46-52
`GET /orders/search` builds its SQL with template interpolation of `q` (and the user id).
`q=' OR 1=1 --` returns every customer's orders; worse payloads can modify data. Use bound
parameters: `note LIKE ? ESCAPE '\'` with the wildcards escaped.

### [high] src/auth.ts:7-9
Passwords are hashed with one unsalted SHA-256. That is fast to brute-force and identical
passwords produce identical hashes. Use `crypto.scrypt` (or argon2/bcrypt) with a per-user salt.

### [high] src/auth.ts:24-30
Session tokens are built from `Math.random()` and `Date.now()`, which are predictable. Use
`randomBytes(32).toString("base64url")`.

### [high] src/routes/orders.ts:56-63
`GET /orders/:id` doesn't check the order belongs to `req.user`, so any logged-in customer
can read anyone's order (IDOR). Add `AND user_id = ?` and return 404 otherwise.

### [high] src/routes/admin.ts:14-32
`/admin/stats` is registered before `router.use(requireAdmin(...))`, so it is reachable
without the admin key and exposes revenue and the top customers' names and emails. Move the
`router.use` above every route.

### [high] src/routes/users.ts:51-60
`/me/stats` is cached under `req.originalUrl`, which is the same for every user: whoever
hits it second sees the first user's stats. Key the cache by user id.

### [medium] src/routes/users.ts:25-28
Signup returns `SELECT *` of the user row, including `password_hash`. Return the public fields.

### [low] src/app.ts:16
The 500 handler sends `err.stack` to clients. Log it, return a generic message.

## Correctness

### [high] src/lib/validate.ts:26-37
`parseOrderInput` only casts the body. Item quantities and product ids aren't validated, so
`quantity: -5` passes the stock check, adds stock back and produces a negative total.
Require positive integers.

### [medium] src/lib/pagination.ts:23
Pages are 1-based (default 1, README says so) but `offset = page * pageSize`, so page 1
skips the first page. Use `(page - 1) * pageSize`.

### [medium] src/lib/stats.ts:22
`median` uses the default `sort()`, which compares numbers as strings (`[1000, 200, 30]`
sorts as `1000, 200, 30`). Use `sort((a, b) => a - b)`.

## Error handling

### [high] src/routes/admin.ts:66-78
The refund handler is `async` on Express 4, which doesn't handle rejected promises. The
404/409 `throw`s and a failing `refundPayment` become unhandled rejections: the request
hangs and Node may exit. Catch and call `next(err)` (or move to Express 5).

### [medium] src/routes/admin.ts:44-52
CSV import swallows every row error and still reports `lines.length - 1` imported. Collect
the failed rows and report them.

## Performance

### [medium] src/routes/admin.ts:55-62
The orders export runs one `order_items` query per order (N+1) across the whole table.
Load the items in one query and group them in memory.

### [medium] src/lib/cache.ts:6-23
`TtlCache` takes `maxEntries` but never enforces it and never deletes expired entries, so
memory grows without bound. Its keys come from request URLs, so clients can grow it at will.

## Types

### [medium] tsconfig.json:8
`strict` is off, which hides real bugs here (e.g. `req.user` is optional but used unchecked
in every handler). Turn it on and fix the fallout.
