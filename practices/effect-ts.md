# Effect-TS Best Practices

Opinionated patterns for Effect-TS codebases, optimizing for type safety, testability, observability, and maintainability.

**Used by:**
- `cook` - When building features with Effect services, errors, layers
- `slop` - Detects Effect anti-patterns during cleanup

**Applies when:** `bruhs.json` has `effect` in `stack.libraries`

---

## Quick Reference: Critical Rules

| Category | DO | DON'T |
|----------|-----|-------|
| Services | `Effect.Service` with `accessors: true` | `Context.Tag` for business logic |
| Dependencies | `dependencies: [Dep.Default]` in service | Manual `Layer.provide` at usage sites |
| Errors | `Schema.TaggedError` with `message` field | Plain classes or generic Error |
| Error Specificity | `UserNotFoundError`, `SessionExpiredError` | Generic `NotFoundError`, `BadRequestError` |
| Error Handling | `catchTag`/`catchTags` | `catchAll` or `mapError` |
| IDs | `Schema.UUID.pipe(Schema.brand("@App/EntityId"))` | Plain `string` for entity IDs |
| Functions | `Effect.fn("Service.method")` | Anonymous generators |
| Logging | `Effect.log` with structured data | `console.log` |
| Config | `Config.*` with validation | `process.env` directly |
| Options | `Option.match` with both cases | `Option.getOrThrow` |
| Nullability | `Option<T>` in domain types | `null`/`undefined` |

---

## Service Definition Pattern

**Always use `Effect.Service`** for business logic services. This provides automatic accessors, built-in `Default` layer, and proper dependency declaration.

```typescript
import { Effect } from "effect"

export class UserService extends Effect.Service<UserService>()("UserService", {
    accessors: true,
    dependencies: [UserRepo.Default, CacheService.Default],
    effect: Effect.gen(function* () {
        const repo = yield* UserRepo
        const cache = yield* CacheService

        const findById = Effect.fn("UserService.findById")(function* (id: UserId) {
            const cached = yield* cache.get(id)
            if (Option.isSome(cached)) return cached.value

            const user = yield* repo.findById(id)
            yield* cache.set(id, user)
            return user
        })

        const create = Effect.fn("UserService.create")(function* (data: CreateUserInput) {
            const user = yield* repo.create(data)
            yield* Effect.log("User created", { userId: user.id })
            return user
        })

        return { findById, create }
    }),
}) {}

// Usage - dependencies are already wired
const program = Effect.gen(function* () {
    const user = yield* UserService.findById(userId)
    return user
})

// At app root
const MainLive = Layer.mergeAll(UserService.Default, OtherService.Default)
```

**When `Context.Tag` is acceptable:**
- Infrastructure with runtime injection (Cloudflare KV, worker bindings)
- Factory patterns where resources are provided externally

---

## Error Definition Pattern

**Always use `Schema.TaggedError`** for errors. This makes them serializable (required for RPC) and provides consistent structure.

```typescript
import { Schema } from "effect"
import { HttpApiSchema } from "@effect/platform"

export class UserNotFoundError extends Schema.TaggedError<UserNotFoundError>()(
    "UserNotFoundError",
    {
        userId: UserId,
        message: Schema.String,
    },
    HttpApiSchema.annotations({ status: 404 }),
) {}

export class UserCreateError extends Schema.TaggedError<UserCreateError>()(
    "UserCreateError",
    {
        message: Schema.String,
        cause: Schema.optional(Schema.String),
    },
    HttpApiSchema.annotations({ status: 400 }),
) {}
```

**Error handling - use `catchTag`/`catchTags`:**

```typescript
// ✅ CORRECT - preserves type information
yield* repo.findById(id).pipe(
    Effect.catchTag("DatabaseError", (err) =>
        Effect.fail(new UserNotFoundError({ userId: id, message: "Lookup failed" }))
    ),
    Effect.catchTag("ConnectionError", (err) =>
        Effect.fail(new ServiceUnavailableError({ message: "Database unreachable" }))
    ),
)

// ✅ CORRECT - multiple tags at once
yield* effect.pipe(
    Effect.catchTags({
        DatabaseError: (err) => Effect.fail(new UserNotFoundError({ userId: id, message: err.message })),
        ValidationError: (err) => Effect.fail(new InvalidEmailError({ email: input.email, message: err.message })),
    }),
)
```

### Prefer Explicit Over Generic Errors

**Every distinct failure reason deserves its own error type.** Don't collapse multiple failure modes into generic HTTP errors.

```typescript
// ❌ WRONG - Generic errors lose information
export class NotFoundError extends Schema.TaggedError<NotFoundError>()(
    "NotFoundError",
    { message: Schema.String },
    HttpApiSchema.annotations({ status: 404 }),
) {}

// Then mapping everything to it:
Effect.catchTags({
    UserNotFoundError: (err) => Effect.fail(new NotFoundError({ message: "Not found" })),
    ChannelNotFoundError: (err) => Effect.fail(new NotFoundError({ message: "Not found" })),
})
// Frontend gets useless: { _tag: "NotFoundError", message: "Not found" }
```

```typescript
// ✅ CORRECT - Explicit domain errors with rich context
export class UserNotFoundError extends Schema.TaggedError<UserNotFoundError>()(
    "UserNotFoundError",
    { userId: UserId, message: Schema.String },
    HttpApiSchema.annotations({ status: 404 }),
) {}

export class ChannelNotFoundError extends Schema.TaggedError<ChannelNotFoundError>()(
    "ChannelNotFoundError",
    { channelId: ChannelId, message: Schema.String },
    HttpApiSchema.annotations({ status: 404 }),
) {}

// Frontend can now show specific UI per error type
```

---

## Schema & Branded Types Pattern

**Brand all entity IDs** for type safety across service boundaries:

```typescript
import { Schema } from "effect"

// Entity IDs - always branded
export const UserId = Schema.UUID.pipe(Schema.brand("@App/UserId"))
export type UserId = Schema.Schema.Type<typeof UserId>

export const OrganizationId = Schema.UUID.pipe(Schema.brand("@App/OrganizationId"))
export type OrganizationId = Schema.Schema.Type<typeof OrganizationId>

// Domain types - use Schema.Struct
export const User = Schema.Struct({
    id: UserId,
    email: Schema.String,
    name: Schema.String,
    organizationId: OrganizationId,
    createdAt: Schema.DateTimeUtc,
})
export type User = Schema.Schema.Type<typeof User>

// Input types for mutations
export const CreateUserInput = Schema.Struct({
    email: Schema.String.pipe(Schema.pattern(/^[^\s@]+@[^\s@]+\.[^\s@]+$/)),
    name: Schema.String.pipe(Schema.minLength(1)),
    organizationId: OrganizationId,
})
export type CreateUserInput = Schema.Schema.Type<typeof CreateUserInput>
```

**When NOT to brand:**
- Simple strings that don't cross service boundaries (URLs, file paths)
- Primitive config values

---

## Function Pattern with Effect.fn

**Always use `Effect.fn`** for service methods. This provides automatic tracing with proper span names:

```typescript
// ✅ CORRECT - Effect.fn with descriptive name
const findById = Effect.fn("UserService.findById")(function* (id: UserId) {
    yield* Effect.annotateCurrentSpan("userId", id)
    const user = yield* repo.findById(id)
    return user
})

// ✅ CORRECT - Effect.fn with multiple parameters
const transfer = Effect.fn("AccountService.transfer")(
    function* (fromId: AccountId, toId: AccountId, amount: number) {
        yield* Effect.annotateCurrentSpan("fromId", fromId)
        yield* Effect.annotateCurrentSpan("toId", toId)
        yield* Effect.annotateCurrentSpan("amount", amount)
        // ...
    }
)
```

---

## Layer Composition

**Declare dependencies in the service**, not at usage sites:

```typescript
// ✅ CORRECT - dependencies in service definition
export class OrderService extends Effect.Service<OrderService>()("OrderService", {
    accessors: true,
    dependencies: [
        UserService.Default,
        ProductService.Default,
        PaymentService.Default,
    ],
    effect: Effect.gen(function* () {
        const users = yield* UserService
        const products = yield* ProductService
        const payments = yield* PaymentService
        // ...
    }),
}) {}

// At app root - simple merge
const AppLive = Layer.mergeAll(
    OrderService.Default,
    // Infrastructure layers (intentionally not in dependencies)
    DatabaseLive,
    RedisLive,
)
```

---

## Option Handling

**Never use `Option.getOrThrow`**. Always handle both cases explicitly:

```typescript
// ✅ CORRECT - explicit handling
yield* Option.match(maybeUser, {
    onNone: () => Effect.fail(new UserNotFoundError({ userId, message: "Not found" })),
    onSome: (user) => Effect.succeed(user),
})

// ✅ CORRECT - with getOrElse for defaults
const name = Option.getOrElse(maybeName, () => "Anonymous")

// ✅ CORRECT - Option.map for transformations
const upperName = Option.map(maybeName, (n) => n.toUpperCase())
```

---

## Observability

```typescript
// ✅ Structured logging
yield* Effect.log("Processing order", { orderId, userId, amount })

// ✅ Metrics
const orderCounter = Metric.counter("orders_processed")
yield* Metric.increment(orderCounter)

// ✅ Config with validation
const config = Config.all({
    port: Config.integer("PORT").pipe(Config.withDefault(3000)),
    apiKey: Config.secret("API_KEY"),
    maxRetries: Config.integer("MAX_RETRIES").pipe(
        Config.validate({ message: "Must be positive", validation: (n) => n > 0 })
    ),
})
```

---

## Anti-Patterns (Forbidden)

These patterns are **never acceptable**:

| Anti-Pattern | Why | Fix |
|--------------|-----|-----|
| `Effect.runSync`/`runPromise` in services | Breaks Effect composition | Return Effect, run at edge |
| `throw` inside `Effect.gen` | Bypasses error channel | Use `Effect.fail` |
| `catchAll` losing type info | Obscures failure causes | Use `catchTag`/`catchTags` |
| `console.log` | No structure, no levels | Use `Effect.log` |
| `process.env` directly | No validation, no defaults | Use `Config.*` |
| `Option.getOrThrow` | Throws on None | Use `Option.match` |
| `null`/`undefined` in domain | Nullability unclear | Use `Option<T>` |
| Generic errors | Loses context | Specific error per failure |

```typescript
// ❌ FORBIDDEN - runSync inside service
const result = Effect.runSync(someEffect)

// ❌ FORBIDDEN - throw inside Effect.gen
yield* Effect.gen(function* () {
    if (bad) throw new Error("No!") // Use Effect.fail instead
})

// ❌ FORBIDDEN - catchAll losing type info
yield* effect.pipe(Effect.catchAll(() => Effect.fail(new GenericError())))

// ❌ FORBIDDEN - console.log
console.log("debug")

// ❌ FORBIDDEN - process.env directly
const key = process.env.API_KEY
```

---

## Slop Detection Checklist

When `slop` runs on Effect code, it checks for:

1. **Services using `Context.Tag` instead of `Effect.Service`**
2. **Missing `Effect.fn` wrappers on service methods**
3. **`Data.TaggedError` instead of `Schema.TaggedError`**
4. **`catchAll` usage (should be `catchTag`/`catchTags`)**
5. **Plain string IDs that should be branded**
6. **`console.log` instead of `Effect.log`**
7. **Direct `process.env` access**
8. **`Option.getOrThrow` calls**
9. **Generic error types collapsing specific errors**
10. **`runSync`/`runPromise` in service code**

---

## Performance

> **Effect gives you structured concurrency for free — use it.** Sequential `yield*` over independent effects is the same bug as `await`-in-loop.

### Parallel over sequential

```typescript
// ❌ Sequential — each effect waits for the last
const program = Effect.gen(function* () {
  const user = yield* fetchUser(id)
  const orders = yield* fetchOrders(id)   // waits for user unnecessarily
  const prefs = yield* fetchPrefs(id)
  return { user, orders, prefs }
})

// ✅ Parallel via Effect.all
const program = Effect.all(
  { user: fetchUser(id), orders: fetchOrders(id), prefs: fetchPrefs(id) },
  { concurrency: "unbounded" }
)

// ✅ Bounded concurrency for user-driven fan-out
const results = Effect.all(
  ids.map(fetchOne),
  { concurrency: 10 }
)
```

### `RequestResolver` for automatic batching / N+1 elimination

Effect's `RequestResolver` is Dataloader-shaped — multiple requests for the same resource in the same fiber window collapse into a single batched call.

### Cache expensive effects

```typescript
// ✅ Memoize an effect — runs once, caches forever
const config = Effect.cached(loadConfig)

// ✅ TTL-bounded cache
const rates = Effect.cachedWithTTL(fetchRates, "5 minutes")
```

### `Stream` for backpressured pipelines

Don't materialize arrays when you're piping DB → transform → HTTP. Use `Stream` for native backpressure and memory bounds.

### Build layers once, not per request

```typescript
// ❌ Layer rebuilt per request — destroys the DI caching win
app.get("/", (req) => {
  const layer = Layer.mergeAll(DbLive, RedisLive)
  return program.pipe(Effect.provide(layer), Effect.runPromise)
})

// ✅ Layer built once at app boot
const AppLayer = Layer.mergeAll(DbLive, RedisLive)
const runtime = ManagedRuntime.make(AppLayer)
app.get("/", (req) => runtime.runPromise(program))
```

### Traps

- **Sequential `yield*` over independent effects** — same class of bug as `await`-in-loop.
- **Rebuilding `Layer`s per request.**
- **`Effect.runPromise` buried inside business logic** — keep runtime boundaries at app edges.
- **Unbounded `concurrency: "unbounded"` on user input.** Pick a number.

### Performance Checklist

- [ ] `Effect.all` with explicit `concurrency` for independent effects
- [ ] `RequestResolver` where the same data is requested by many fibers
- [ ] `Effect.cached` / `cachedWithTTL` for expensive, reusable computations
- [ ] `Stream` over arrays for large pipelines
- [ ] Layers built once; `ManagedRuntime` reused across requests
- [ ] Bounded concurrency on user-driven fan-out

---

## Detailed Reference Files

For in-depth patterns and examples, see the reference files in `effect-references/`:

| File | Description |
|------|-------------|
| `service-patterns.md` | Effect.Service, dependencies, testing |
| `error-patterns.md` | Schema.TaggedError, error naming, catchTag |
| `schema-patterns.md` | Branded types, transforms, unions |
| `layer-patterns.md` | Layer composition, testing layers |
| `anti-patterns.md` | Forbidden patterns with fixes |
| `observability-patterns.md` | Logging, tracing, metrics |
| `rpc-cluster-patterns.md` | RpcGroup, Workflow, ClusterCron |
| `effect-atom-patterns.md` | Frontend state with Effect Atom |

---

## Resources

- [Effect Documentation](https://effect.website/docs)
- [Effect API Reference](https://effect-ts.github.io/effect/)
- [Effect GitHub](https://github.com/Effect-TS/effect)
- [Effect Discord](https://discord.gg/effect-ts)
