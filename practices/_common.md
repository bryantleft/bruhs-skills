# Common Best Practices

Universal patterns that apply across all stacks.

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

### Commit Messages

```
<type>: <description>

[optional body]

[optional footer]
```

Types:
- `feat` - New feature
- `fix` - Bug fix
- `refactor` - Code change that neither fixes bug nor adds feature
- `chore` - Maintenance, config, dependencies
- `docs` - Documentation
- `test` - Tests
- `style` - Formatting (no code change)

```
feat: add user authentication flow

- Implement login/logout with JWT
- Add protected route middleware
- Create auth context for client state

Fixes PROJ-123
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
- Framework versions change—what was best practice in 2024 may be outdated in 2026
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
