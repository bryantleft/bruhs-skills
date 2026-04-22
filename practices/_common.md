# Common Best Practices

Universal patterns that apply across all stacks.

## Contents

- [Naming Conventions](#naming-conventions)
- [Code Organization](#code-organization)
- [Error Handling](#error-handling)
- [Git Practices](#git-practices)
- [Comments](#comments)
- [Testing](#testing)
- [Dependencies](#dependencies)
- [External Searches](#external-searches)
- [Performance](#performance)
- [Quick Reference](#quick-reference)

---

## Naming Conventions

### Files & Folders

| Type | Convention | Example |
|------|------------|---------|
| Components | PascalCase | `UserCard.tsx` |
| Hooks | camelCase with `use` prefix | `useAuth.ts` |
| Utilities | camelCase | `formatDate.ts` |
| Constants | SCREAMING_SNAKE or camelCase | `MAX_RETRIES` or `maxRetries` |
| Types/Interfaces | PascalCase | `User.ts`, `ApiResponse.ts` |
| Test files | `.test.ts` or `.spec.ts` suffix | `auth.test.ts` |

### Variables & Functions

```typescript
// ✅ Descriptive but concise
const user = await getUser(id);
const isActive = user.status === 'active';
const userIds = users.map(u => u.id);

// ❌ Too verbose
const userDataFromDatabase = await getUser(id);
const isUserCurrentlyActive = user.status === 'active';
const arrayOfAllUserIds = users.map(u => u.id);

// ❌ Too cryptic
const u = await getUser(id);
const a = user.status === 'active';
const ids = users.map(u => u.id);
```

### Boolean Naming

```typescript
// ✅ Question form (is, has, can, should)
const isLoading = true;
const hasPermission = user.role === 'admin';
const canEdit = hasPermission && !isLocked;
const shouldRefetch = staleTime > 30000;

// ❌ Ambiguous
const loading = true;
const permission = user.role === 'admin';
const edit = hasPermission && !isLocked;
```

### Function Naming

```typescript
// ✅ Verb + noun (action + target)
function getUser(id: string) { ... }
function createOrder(items: Item[]) { ... }
function validateEmail(email: string) { ... }
function formatCurrency(amount: number) { ... }

// ✅ Handle/on prefix for event handlers
function handleSubmit() { ... }
function onUserClick() { ... }

// ❌ Vague
function process(data) { ... }
function doStuff() { ... }
function manager() { ... }
```

---

## Code Organization

### Single Responsibility

```typescript
// ❌ Function doing too much
async function handleCheckout(cart: Cart, user: User) {
  // Validate cart
  // Calculate totals
  // Process payment
  // Send confirmation email
  // Update inventory
  // Log analytics
}

// ✅ Separate concerns
async function handleCheckout(cart: Cart, user: User) {
  const validatedCart = validateCart(cart);
  const order = await createOrder(validatedCart, user);
  await processPayment(order);
  await Promise.all([
    sendConfirmationEmail(order),
    updateInventory(order),
    logCheckoutAnalytics(order),
  ]);
  return order;
}
```

### Function Length

- Functions should do ONE thing
- If you need comments to separate sections, extract functions
- Target: 20-30 lines max (with exceptions for switch statements, etc.)

### File Length

- Files should have ONE purpose
- If a file has multiple unrelated exports, split it
- Target: 200-300 lines max

---

## Error Handling

### Be Specific

```typescript
// ❌ Generic errors
throw new Error('Something went wrong');
throw new Error('Invalid input');

// ✅ Specific, actionable errors
throw new Error(`User with id "${id}" not found`);
throw new Error(`Invalid email format: ${email}`);
throw new Error(`Payment failed: ${paymentError.code} - ${paymentError.message}`);
```

### Fail Fast

```typescript
// ✅ Validate at boundaries, trust internal code
async function createUser(input: unknown) {
  const data = createUserSchema.parse(input); // Validate once at entry

  // Internal code can trust data is valid
  const user = await db.users.create(data);
  await sendWelcomeEmail(user); // Don't re-validate user
  return user;
}
```

### Don't Swallow Errors

```typescript
// ❌ Silent failure
try {
  await sendEmail(user);
} catch (e) {
  // do nothing
}

// ❌ Logging but still hiding the problem
try {
  await sendEmail(user);
} catch (e) {
  console.error(e);
}

// ✅ Handle appropriately
try {
  await sendEmail(user);
} catch (e) {
  // Either rethrow, return error state, or have explicit fallback
  logger.error('Failed to send email', { userId: user.id, error: e });
  throw new EmailDeliveryError(user.id, e);
}
```

---

## Git Practices

### Commit Messages (Conventional Commits)

Follow the [Conventional Commits](https://www.conventionalcommits.org/) specification:

```
<type>(<scope>): <description>

[optional body]

[optional footer]
```

**Format rules:**
- Type and description are **required**
- Scope is optional but recommended for larger codebases
- Description should be lowercase, imperative mood ("add" not "added" or "adds")
- No period at end of description
- Body provides context on the "why" (wrap at 72 chars)

**Types:**

| Type | Description | Example |
|------|-------------|---------|
| `feat` | New feature | `feat(auth): add OAuth2 login flow` |
| `fix` | Bug fix | `fix(api): handle null response from server` |
| `refactor` | Code restructuring (no behavior change) | `refactor(utils): extract date formatting` |
| `chore` | Maintenance, config, deps | `chore(deps): update effect to 3.15` |
| `docs` | Documentation only | `docs(readme): add setup instructions` |
| `test` | Adding/updating tests | `test(auth): add login edge case coverage` |
| `style` | Formatting, whitespace (no logic change) | `style: fix indentation in config files` |
| `perf` | Performance improvement | `perf(query): add database index for users` |
| `ci` | CI/CD changes | `ci: add automated release workflow` |
| `build` | Build system changes | `build: update webpack config` |

**Breaking changes:**
- Add `!` after type/scope: `feat(api)!: change response format`
- Or add `BREAKING CHANGE:` in footer

**Examples:**

```
feat(scouts): add parallel action space mapping

Implement Scout System to map web page elements before agent acts:
- 4 parallel scouts (interactive, modal, form, navigation)
- XSS-safe selector generation with CSS.escape
- Visibility filtering and 200 element limit

Closes #123
```

```
fix(auth): prevent session fixation on login

Regenerate session ID after successful authentication to prevent
session fixation attacks.

BREAKING CHANGE: existing sessions will be invalidated
```

```
chore(deps): update effect-ts to 3.15

- Adds new Schema.TaggedError features
- Fixes layer composition edge case
```

### Branch Names

```
<type>/<ticket-id>-<short-description>

feat/proj-123-user-auth
fix/proj-456-login-redirect
chore/update-dependencies
```

### PR Size

- **Small PRs** are easier to review and less likely to have bugs
- Target: 200-400 lines changed
- If larger, consider splitting into stacked PRs

---

## Comments

### When to Comment

```typescript
// ✅ WHY, not WHAT
// Using binary search because dataset exceeds 10k items
const index = binarySearch(sortedItems, target);

// ✅ Non-obvious business logic
// Tax exempt for orders over $500 per state regulation ABC-123
const tax = subtotal > 500 ? 0 : subtotal * 0.0825;

// ✅ Workarounds with context
// Safari doesn't support this API, using polyfill
// See: https://bugs.webkit.org/show_bug.cgi?id=12345

// ✅ TODO with ticket reference
// TODO(PROJ-789): Replace with native API when Safari support lands
```

### When NOT to Comment

```typescript
// ❌ Explaining what code does
// Get the user from database
const user = await db.getUser(id);

// ❌ Translating code to English
// If user is not found, throw error
if (!user) throw new Error('User not found');

// ❌ Changelog in code
// Added by John on 2024-01-15
// Modified by Jane on 2024-02-20

// ❌ Commented-out code
// const oldImplementation = () => { ... };
```

---

## Testing

### Test Structure

```typescript
describe('calculatePricing', () => {
  it('calculates subtotal from item prices and quantities', () => {
    const items = [
      { price: 10, qty: 2 },
      { price: 5, qty: 3 },
    ];
    expect(calculatePricing(items).subtotal).toBe(35);
  });

  it('applies free shipping for orders over $100', () => {
    const items = [{ price: 150, qty: 1 }];
    expect(calculatePricing(items).shipping).toBe(0);
  });

  it('charges $9.99 shipping for orders under $100', () => {
    const items = [{ price: 50, qty: 1 }];
    expect(calculatePricing(items).shipping).toBe(9.99);
  });
});
```

### Test Naming

```typescript
// ✅ Describes behavior
it('returns empty array when no users match filter', () => {});
it('throws error when user id is invalid', () => {});
it('retries failed requests up to 3 times', () => {});

// ❌ Describes implementation
it('calls the filter function', () => {});
it('uses the error class', () => {});
it('has retry logic', () => {});
```

### What to Test

- **Do test**: Business logic, edge cases, error conditions
- **Don't test**: Implementation details, third-party code, trivial getters/setters

---

## Dependencies

### Audit Regularly

```bash
# Check for vulnerabilities
npm audit
pnpm audit

# Check for outdated packages
npm outdated
pnpm outdated
```

### Minimize Dependencies

- Before adding a package, check if it's necessary
- Prefer smaller, focused packages over large frameworks
- Consider maintenance status (last update, open issues, bus factor)

### Lock Versions

- Use lockfiles (`pnpm-lock.yaml`, `package-lock.json`)
- Commit lockfiles to version control
- Don't use `*` or `latest` in version ranges

---

## External Searches

### Always Include Current Date

When using `WebSearch` or `WebFetch` for documentation, best practices, or any external information, **always include the current year** in the query to get up-to-date results.

```javascript
// ✅ Include current date for fresh results
const currentYear = new Date().getFullYear();

WebSearch({ query: `React Server Components best practices ${currentYear}` })
WebSearch({ query: `Next.js app router documentation ${currentYear}` })
WebSearch({ query: `TypeScript latest features ${currentYear}` })

// ✅ For WebFetch prompts, mention recency
WebFetch({
  url: "https://docs.example.com/api",
  prompt: `Extract the latest API changes as of ${currentYear}`
})

// ❌ Queries without date context may return stale results
WebSearch({ query: `React Server Components best practices` })
WebSearch({ query: `Next.js app router documentation` })
```

### Why This Matters

- Documentation and best practices evolve rapidly
- Search results without date context may prioritize older, higher-ranked content
- Framework versions change — best practice drifts over time as APIs evolve
- Libraries deprecate features and introduce breaking changes

### When to Include Date

| Scenario | Include Date? |
|----------|---------------|
| Documentation lookups | ✅ Yes |
| Best practices research | ✅ Yes |
| Framework/library guides | ✅ Yes |
| API references | ✅ Yes |
| Error message lookups | ✅ Yes (bugs get fixed) |
| General knowledge (math, algorithms) | ❌ No |

---

## Performance

> Pick the fast path by default. Obvious perf wins don't need a benchmark to justify.

### Philosophy

Performance is a first-class concern, not "premature optimization." The canonical Knuth quote has a caveat most people skip: *"Yet we should not pass up our opportunities in that critical 3%."* Anti-patterns like N+1 queries, `await`-in-loop, and per-request client construction are in the 3% — they're not optimizations, they're mistakes.

- **Correctness first, but when two patterns are equally correct, pick the faster one.**
- **Benchmarks are required to claim a win, not to avoid an anti-pattern.**
- **Measure at boundaries** (ingress/egress p50/p95/p99). Internal timers lie about contention.
- **Complexity budget**: if the fast path costs significant readability, fall back to the clear path and note the tradeoff. If costs are comparable, fast wins.

### Universal Fast-Path Defaults

```typescript
// ❌ Sequential I/O pretending to be async
for (const id of ids) {
  await processUser(id);
}

// ✅ Parallel with bounded concurrency
import pLimit from "p-limit";
const limit = pLimit(10);
await Promise.all(ids.map(id => limit(() => processUser(id))));
```

```typescript
// ❌ Per-request client construction — no pooling, cold TLS every call
app.get("/users", async () => {
  const db = new PrismaClient();
  return db.user.findMany();
});

// ✅ Singleton, initialized once at boot
const db = new PrismaClient();
app.get("/users", async () => db.user.findMany());
```

```typescript
// ❌ N+1 — one query per user
const users = await db.user.findMany();
for (const u of users) {
  u.posts = await db.post.findMany({ where: { userId: u.id } });
}

// ✅ One query with eager load
const users = await db.user.findMany({ include: { posts: true } });
```

### Batch at Boundaries

One round-trip of N items beats N round-trips. Applies to DB, HTTP, IPC, queue publishes, GPU dispatch.

```typescript
// ❌ One insert per record
for (const row of rows) await db.insert(table).values(row);

// ✅ Batched insert
await db.insert(table).values(rows);
```

### Stream, Don't Buffer

Start bytes moving before you have them all — SSR, JSON, file I/O, LLM tokens. Especially important at the edge where memory is tight.

### Don't Block the Hot Loop

- Event loop / render thread / request handler: push CPU work off, I/O async, never sync-in-async.
- Sync crypto (bcrypt, big hashes) in the request path → worker / threadpool.
- Full-body logging in hot paths → structured fields, sampled.

### Bound Concurrency on User Input

```typescript
// ❌ DoS vector — user can send 1M ids
await Promise.all(ids.map(fetchOne));

// ✅ Bounded
const limit = pLimit(20);
await Promise.all(ids.map(id => limit(() => fetchOne(id))));
```

### Common LLM Traps

Patterns that *look* clean but quietly destroy performance — flag these in review:

1. `await` inside a `for` loop over independent items → `Promise.all` / `asyncio.gather` / `try_join!`
2. `.map().filter().reduce()` chains over large arrays → one pass or lazy iterator
3. N+1 ORM access dressed as idiomatic code → eager loading / `selectinload` / `include`
4. `useMemo` / `useCallback` on primitives or cheap expressions
5. `JSON.parse(JSON.stringify(x))` for deep clone → `structuredClone`
6. Unbounded `Promise.all` / recursion over user input
7. Synchronous hashing/crypto in request path
8. Per-request client construction (`new PrismaClient()`, `httpx.AsyncClient()`, `reqwest::Client::new()`)
9. Full-body JSON logging in hot paths
10. Parsing config / reading env per request instead of once at boot

### Measurement Discipline

You need evidence to claim *"this is X% faster"*. You do not need evidence to fix an anti-pattern.

```
✅ "Removed N+1 — reduced 50 queries per request to 2."       (anti-pattern — obvious)
✅ "Added prepared statement — p95 dropped 40ms → 12ms."       (claim — measured)
❌ "Refactored for performance."                               (vague, unmeasured, likely no-op)
❌ "Memoized for performance."                                 (without evidence, probably pure overhead)
```

### Per-Stack Playbooks

For concrete patterns in your stack → see the Performance section of:
- `practices/typescript-react.md`
- `practices/typescript-hono.md`
- `practices/python.md` / `practices/python-fastapi.md`
- `practices/rust.md`
- `practices/effect-ts.md`

---

## Quick Reference

### Universal Checklist
- [ ] Clear, concise naming
- [ ] Single responsibility functions
- [ ] Specific error messages
- [ ] No swallowed errors
- [ ] Conventional commits
- [ ] Comments explain WHY, not WHAT
- [ ] No commented-out code
- [ ] No TODO without ticket reference
- [ ] Dependencies audited
- [ ] Lockfile committed

### Performance Checklist
- [ ] No `await` in loops over independent items
- [ ] No N+1 ORM access
- [ ] Clients (DB, HTTP, Redis) constructed once, not per request
- [ ] Concurrency bounded when driven by user input
- [ ] No sync I/O on async event loop
- [ ] Streaming over buffering for large payloads
- [ ] Batched writes at boundaries (DB, HTTP, queue)
- [ ] Config/env loaded once at boot
