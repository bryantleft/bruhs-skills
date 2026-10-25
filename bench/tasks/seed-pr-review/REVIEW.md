# Review: feat/webhook-retries (#42, "Retry failed webhook deliveries")

Reviewer: Marta Koval, requested changes

---

### 1. `src/backoff.ts`, line 14

```ts
const exp = baseMs * 2 ** (retry - 1);
```

There's no ceiling on this. Fine at the default 5 attempts, but support already bumps
`maxAttempts` to 10 for some customers, and by then the last wait is 500ms · 2⁹ ≈ 4 min.
Please add a `maxDelayMs` delivery option (default 30s) that caps it.

---

### 2. `src/deliver.ts`, line 73

```ts
if (res.ok) {
  return { delivered: true, attempts: attempt + 1, status };
}
```

Anything that isn't 2xx gets retried, including 400/401/404/410. Those will fail exactly
the same way every time, and we end up hammering endpoints that are telling us to stop.
We should only retry 408, 429 and 5xx, and give up right away on any other 4xx.

---

### 3. `src/deliver.ts`, line 56

```ts
await sleep(backoffDelay(attempt, { baseMs: baseDelayMs, random }));
```

When a receiver rate-limits us (429, or 503 during maintenance) it usually sends
`Retry-After`. We should wait at least that long before the next attempt instead of
ignoring it. Note it can be either a number of seconds or an HTTP date.

---

### 4. `src/deliver.ts`, line 54

```ts
for (let attempt = 0; attempt <= maxAttempts; attempt++) {
```

With `maxAttempts: 3` this sends 4 requests, and the result reports `attempts: 4`. The
option is documented as total tries including the first.

---

### 5. `src/deliver.ts`, line 50

```ts
const idempotencyKey = randomUUID();
```

This is generated once, outside the loop, so every retry goes out with the same
`Idempotency-Key`. Receivers that log or index on the key will see duplicates. Move
`randomUUID()` into the loop so each request gets its own unique key.
