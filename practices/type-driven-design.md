# Type-Driven Design

Universal principles for writing code where types serve as the primary documentation. Derived from Scala's functional programming, Go's explicit error handling, and Rust's ownership model—applied to any typed language.

**Used by:**
- `cook` - Type-first design when building features
- `slop` - Primary lens for detecting slop (types are the #1 signal)

---

## The Core Principle

> **A function's type signature should tell you everything you need to know about what it does.**

If you have to read the implementation to understand the behavior, the types have failed.

```typescript
// ❌ Signature tells you nothing
function process(data: any): any

// ❌ Side effects hidden - signature lies
function getUser(id: string): User  // might throw, might log, might call API

// ✅ Signature tells the full story
function getUser(id: string): Promise<User | null>  // async, might not find user

// ✅ Even better - errors are explicit (using better-result or Effect)
function getUser(id: string): Promise<Result<User, NotFoundError | NetworkError>>
```

---

## The Type Signature Hierarchy

When reviewing code, type signatures are the **#1 priority**. Fix these before anything else.

| Priority | Issue | Why |
|----------|-------|-----|
| **1** | Missing/wrong type signatures | Types ARE the documentation |
| **2** | Side effects not in signature | Signature lies about behavior |
| **3** | Overly permissive types (`any`) | Type system disabled |
| **4** | Unsafe type operations (**as**, **!**) | Compiler trust violated |
| **5** | Fast-path violations | `await`-in-loop, N+1, sync-in-async, per-request clients — anti-patterns, not optimizations |
| **6** | Other implementation issues | Secondary to type correctness |

> **Note on performance**: we treat anti-patterns (5) as first-class bugs. Picking a fast-path pattern when it's equally correct is not "premature optimization" — it's just competent. Measurement is required to *claim* a speedup, not to *avoid* an anti-pattern. See `practices/_common.md` Performance section.

---

## Pillar 1: Signatures as Documentation

### Types Should Be Honest

From Scala FP: *"When a function is pure, its signature lets you make very strong guesses at what it does—even when you can't see the function name."*

```typescript
// ❌ Signature hides the truth
function setUserName(name: string): void
// What does this actually do? Database? State? Validation? Logging? All of the above?

// ✅ Signature reveals behavior
function validateUserName(name: string): ValidationResult
function updateUser(id: UserId, update: UserUpdate): Promise<User>
```

### Return Types Should Be Explicit

From Scala: *"Public functions SHOULD have explicit return types."*

```typescript
// ❌ Inference can mislead
const getUsers = async () => {
  const res = await fetch('/api/users');
  return res.json(); // Returns Promise<any> - lost type info
};

// ✅ Explicit return type documents intent
async function getUsers(): Promise<User[]> {
  const res = await fetch('/api/users');
  return userArraySchema.parse(await res.json());
}
```

### Unit/Void Returns Signal Side Effects

From Scala: *"Functions returning Unit must have side effects somewhere."*

```typescript
// This signature DEMANDS side effects - why else return nothing?
function logError(error: Error): void

// If a function has a concrete return type, it should be pure
function formatError(error: Error): string  // No side effects expected
```

---

## Pillar 2: Explicit Error Handling

### Errors Are Values, Not Exceptions

From Go: *"Go treats errors as values, which are handled explicitly through return values."*

**For TypeScript:** Use `better-result` for Result types (or `Effect` for full effect system).

```typescript
// ❌ Throws are invisible in types
function parseJson(text: string): Config {
  return JSON.parse(text); // throws on invalid JSON - signature lies
}

// ✅ Errors in return type (simple union)
function parseJson(text: string): Config | ParseError {
  try {
    return JSON.parse(text);
  } catch (e) {
    return new ParseError(e.message);
  }
}

// ✅ Result type (better-result)
import { Result } from 'better-result';

function parseJson(text: string): Result<Config, ParseError> {
  return Result.try({
    try: () => configSchema.parse(JSON.parse(text)),
    catch: (e) => new ParseError(e.message),
  });
}
```

### Handle Errors Immediately

From Go: *"When a function returns an error, check it right away."*

```typescript
// ❌ Error handling deferred/ignored
const result = riskyOperation();
// ... 50 lines later ...
if (result.error) { /* too late */ }

// ✅ Handle at call site (union type)
const result = riskyOperation();
if (result instanceof Error) {
  return handleError(result);
}
// Continue with result

// ✅ Handle at call site (better-result)
const result = riskyOperation();
if (result.isErr()) {
  return handleError(result.unwrapErr());
}
// Continue with result.unwrap()

// ✅ Or use match for exhaustive handling
result.match({
  ok: (value) => processValue(value),
  err: (error) => handleError(error),
});
```

### Chain Results with Generators (better-result)

For multiple fallible operations, use generator composition instead of nested conditionals:

```typescript
// ❌ Nested error checking
async function processOrder(orderId: string) {
  const orderResult = await fetchOrder(orderId);
  if (orderResult.isErr()) return orderResult;

  const userResult = await fetchUser(orderResult.unwrap().userId);
  if (userResult.isErr()) return userResult;

  const paymentResult = await processPayment(userResult.unwrap());
  if (paymentResult.isErr()) return paymentResult;

  return Result.ok(paymentResult.unwrap());
}

// ✅ Generator composition - linear, readable
async function processOrder(orderId: string) {
  return Result.gen(async function* () {
    const order = yield* Result.await(fetchOrder(orderId));
    const user = yield* Result.await(fetchUser(order.userId));
    const payment = yield* Result.await(processPayment(user));
    return Result.ok(payment);
  });
}
```

### Use Discriminated Unions for States

From Go's sentinel errors + TypeScript patterns:

```typescript
// ❌ Multiple booleans = impossible states possible
type FetchState = {
  isLoading: boolean;
  isError: boolean;
  data: User | null;
  error: Error | null;
};

// ✅ Discriminated union = only valid states
type FetchState =
  | { status: 'idle' }
  | { status: 'loading' }
  | { status: 'success'; data: User }
  | { status: 'error'; error: Error };
```

### Errors Should Be Typed, Not Strings

From Go: *"Custom error types allow you to encode more detail and give callers fine-grained control."*

```typescript
// ❌ String errors lose information
throw new Error('User not found');
throw new Error('Invalid input');

// ✅ Typed errors enable handling
class UserNotFoundError extends Error {
  constructor(public userId: string) {
    super(`User ${userId} not found`);
  }
}

class ValidationError extends Error {
  constructor(public field: string, public reason: string) {
    super(`${field}: ${reason}`);
  }
}

// Caller can handle specifically
if (error instanceof UserNotFoundError) {
  return redirect('/register');
}
```

---

## Pillar 3: Immutability by Default

### Prefer Immutable Data

From Rust: *"Rust manages memory without a garbage collector using ownership."*
From Scala: *"Immutable data structures reduce hidden side effects."*

```typescript
// ❌ Mutable state - signature doesn't reveal mutations
class UserService {
  private users: User[] = [];

  addUser(user: User): void {
    this.users.push(user); // Hidden mutation
  }
}

// ✅ Immutable - transformation is explicit in signature
function addUser(users: readonly User[], user: User): User[] {
  return [...users, user];
}
```

### Don't Mutate Parameters

From Rust: *"You can have either one mutable reference or any number of immutable references."*

```typescript
// ❌ Parameter mutation - caller's data silently changed
function sortUsers(users: User[]): User[] {
  return users.sort((a, b) => a.name.localeCompare(b.name)); // Mutates original!
}

// ✅ Create new array
function sortUsers(users: readonly User[]): User[] {
  return [...users].sort((a, b) => a.name.localeCompare(b.name));
}
```

### Use `readonly` to Document Intent

From Rust's borrowing: make immutability explicit in types.

```typescript
// ❌ Ambiguous - might mutate
function processItems(items: Item[]): void

// ✅ Clear contract - won't mutate
function processItems(items: readonly Item[]): Summary
```

### Avoid Unnecessary Cloning

From Rust: *"Borrowing data prevents performance overhead and hidden dependencies."*

```typescript
// ❌ Defensive copying everywhere
function getUserName(user: User): string {
  const copy = { ...user }; // Unnecessary
  return copy.name;
}

// ✅ Just read what you need
function getUserName(user: Readonly<User>): string {
  return user.name;
}
```

---

## Pillar 4: Type Safety Over Convenience

### Never Use `any`

`any` disables TypeScript. You've opted out of the type system.

```typescript
// ❌ Type system disabled
function process(data: any): any { ... }

// ✅ Use unknown for truly unknown data
function process(data: unknown): ProcessedData {
  const validated = schema.parse(data);
  return transform(validated);
}
```

### Never Use Non-Null Assertions (`!`)

You're telling the compiler "trust me" - the compiler's job is to not trust you.

```typescript
// ❌ Lying to the compiler
const user = users.find(u => u.id === id)!;

// ✅ Handle the null case
const user = users.find(u => u.id === id);
if (!user) {
  throw new UserNotFoundError(id);
}
```

### Never Use Type Assertions for External Data

External data has no guarantees. Validate, don't assume.

```typescript
// ❌ Trusting external data
const user = await fetch('/api/user').then(r => r.json()) as User;

// ✅ Validate at boundary
const user = userSchema.parse(await fetch('/api/user').then(r => r.json()));
```

### Avoid Type Widening

Keep types as narrow as possible.

```typescript
// ❌ Overly wide
function getStatus(): string { return 'active'; }

// ✅ Narrow and specific
function getStatus(): 'active' | 'inactive' | 'pending' { return 'active'; }
```

---

## Pillar 5: Functions as Contracts

### Pure Functions When Possible

From Scala: *"Pure functions always produce the same output for the same input and have no external side effects."*

```typescript
// ❌ Impure - depends on external state
function formatDate(date: Date): string {
  return date.toLocaleString(globalLocale); // Depends on global
}

// ✅ Pure - all dependencies in signature
function formatDate(date: Date, locale: string): string {
  return date.toLocaleString(locale);
}
```

### Make Dependencies Explicit

If a function needs something, put it in the signature.

```typescript
// ❌ Hidden dependencies
function saveUser(user: User): Promise<void> {
  return db.users.insert(user); // Where does db come from?
}

// ✅ Dependencies in signature
function saveUser(db: Database, user: User): Promise<void> {
  return db.users.insert(user);
}

// ✅ Or use dependency injection pattern
class UserRepository {
  constructor(private db: Database) {}

  save(user: User): Promise<void> {
    return this.db.users.insert(user);
  }
}
```

### Small Functions with Single Purpose

From all three traditions: functions should do one thing.

```typescript
// ❌ Does too much
function processCheckout(cart: Cart, user: User): Promise<Order> {
  // validates cart
  // calculates totals
  // processes payment
  // sends email
  // updates inventory
  // ... 200 lines
}

// ✅ Composed from focused functions
async function processCheckout(cart: Cart, user: User): Promise<Order> {
  const validatedCart = validateCart(cart);
  const totals = calculateTotals(validatedCart);
  const payment = await processPayment(totals, user);
  const order = createOrder(validatedCart, payment);

  await Promise.all([
    sendConfirmationEmail(user, order),
    updateInventory(order),
  ]);

  return order;
}
```

---

## Quick Reference

### Type Signature Checklist (Priority Order)

1. **Explicit return types** on all public functions
2. **No `any`** - use `unknown` + validation
3. **No `!`** - handle null cases explicitly
4. **No `as`** for external data - validate instead
5. **Errors in return type** - not thrown silently
6. **`readonly` parameters** - signal no mutation
7. **Discriminated unions** for state machines
8. **Narrow types** over wide strings/numbers

### Pure Function Checklist

- [ ] Output depends only on inputs
- [ ] No side effects (I/O, mutations, globals)
- [ ] All dependencies in signature
- [ ] Returns concrete type (not void/Unit unless intentionally side-effecting)

### Immutability Checklist

- [ ] Prefer `const` over `let`
- [ ] Use `readonly` arrays and objects
- [ ] Don't mutate parameters
- [ ] Return new objects instead of mutating
- [ ] Clone before mutating when necessary

### Error Handling Checklist

- [ ] Errors visible in return type
- [ ] Typed errors, not strings
- [ ] Handle at call site, not deferred
- [ ] No empty catch blocks
- [ ] No swallowed errors

---

---

## TypeScript Libraries

| Need | Library | When |
|------|---------|------|
| Result types | `better-result` | Lightweight, just Result<T, E> |
| Full effect system | `Effect` | Complex async, dependencies, streaming |
| Schema validation | `zod` | External data validation at boundaries |

**Choosing between better-result and Effect:**
- Use `better-result` for simple error-as-value patterns without runtime overhead
- Use `Effect` when you need dependency injection, retries, concurrency, or the full effect system

---

## References

Research and principles informing these guidelines:

- [Pure Function Signatures Tell All](https://alvinalexander.com/scala/fp-book/pure-function-signatures-tell-all/) - Scala FP
- [Scala Best Practices](https://github.com/alexandru/scala-best-practices) - Type safety principles
- [Go Error Handling](https://go.dev/blog/error-handling-and-go) - Errors as values
- [Go Error Handling Best Practices](https://www.jetbrains.com/guide/go/tutorials/handle_errors_in_go/best_practices/) - Explicit handling
- [Rust Ownership and Borrowing](https://doc.rust-lang.org/book/ch04-02-references-and-borrowing.html) - Immutability
- [Effective Scala](http://twitter.github.io/effectivescala/) - Twitter's guidelines
- [better-result](https://github.com/dmmulroy/better-result) - TypeScript Result type
