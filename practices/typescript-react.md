# TypeScript + React Best Practices

Shared best practices for TypeScript/React stacks (Next.js, React Native, Tauri, Electron).

**Used by:**
- `cook` - Patterns to follow when building features
- `slop` - Patterns to detect and fix during cleanup

---

## Core Principles

| Principle | Description |
|-----------|-------------|
| **Atomic Design** | Hierarchical components: atoms → molecules → organisms → templates → pages |
| **Clean** | Simple, readable, maintainable code |
| **Immutability** | Predictable state and data flow |
| **Scalable** | Architecture that grows with your needs |
| **Single Source of Truth** | One authoritative source for each piece of data |
| **KISS** | Keep It Simple, Stupid |
| **YAGNI** | You Ain't Gonna Need It |

---

## TypeScript Patterns

### DO: Use Proper Types

```typescript
// ✅ Specific types
function getUser(id: string): Promise<User> { ... }

// ✅ Unknown for external data + validation
async function fetchUser(id: string): Promise<User> {
  const data: unknown = await fetch(`/api/users/${id}`).then(r => r.json());
  return userSchema.parse(data); // Zod validation
}

// ✅ Let inference work
const count = 0;                    // inferred as number
const users = getUsers();           // inferred from return type
const [state, setState] = useState(0); // inferred as number
```

### DON'T: Type Anti-Patterns

```typescript
// ❌ any type - disables type checking
function processData(data: any) { ... }

// ❌ Non-null assertion - lying to compiler
const user = users.find(u => u.id === id)!;

// ❌ Type assertion for external data
const data = await fetch('/api').then(r => r.json()) as User[];

// ❌ Redundant type annotations
const count: number = 0;
const name: string = "hello";

// ❌ Overly flexible props
interface Props {
  data: any;
  callback?: (...args: any[]) => any;
}
```

### DO: Handle Nullable Values

```typescript
// ✅ Explicit null handling
const user = users.find(u => u.id === id);
if (!user) throw new Error(`User ${id} not found`);

// ✅ Optional chaining with fallback
const name = user?.profile?.name ?? 'Anonymous';

// ✅ Narrowing with type guards
function isUser(value: unknown): value is User {
  return typeof value === 'object' && value !== null && 'id' in value;
}
```

### Enums: Prefer Const Objects

```typescript
// ❌ Enum with implicit values - brittle, order-dependent
enum Status {
  Pending,    // 0
  Active,     // 1
  Completed,  // 2
}

// ❌ String enum - verbose, can't iterate values easily
enum Status {
  Pending = 'PENDING',
  Active = 'ACTIVE',
  Completed = 'COMPLETED',
}

// ✅ Const object - better inference, iteration, tree-shaking
const Status = {
  Pending: 'pending',
  Active: 'active',
  Completed: 'completed',
} as const;

type Status = typeof Status[keyof typeof Status]; // 'pending' | 'active' | 'completed'

// ✅ Usage
const currentStatus: Status = Status.Active;

// ✅ Iteration works
Object.values(Status).forEach(status => console.log(status));
```

**When enums ARE acceptable:**
- Ambient enums in `.d.ts` files for external libraries
- When you need reverse mapping (number → string)

**If you must use enums, always use explicit values:**
```typescript
// ✅ Explicit values (if enum is required)
enum HttpStatus {
  OK = 200,
  NotFound = 404,
  ServerError = 500,
}
```

---

## React Patterns

### Server Components First (Next.js 13+)

Components are Server Components by default. Only add `"use client"` when you need:
- Event handlers (`onClick`, `onChange`)
- Browser APIs (`localStorage`, `window`)
- Hooks that use state (`useState`, `useReducer`)

```tsx
// ✅ Server Component (default) - fetch data directly
async function UserProfile({ userId }: { userId: string }) {
  const user = await db.users.find(userId);
  return <div>{user.name}</div>;
}

// ✅ Client Component - only when needed
"use client";
function LikeButton() {
  const [liked, setLiked] = useState(false);
  return <button onClick={() => setLiked(!liked)}>Like</button>;
}
```

### Data Fetching Hierarchy

| Layer | Tool | When |
|-------|------|------|
| Server Components | `async/await` | Initial page data, SEO-critical content |
| Client (streaming) | `use()` hook | Non-critical data passed as promise from server |
| Client (interactive) | TanStack Query | Mutations, polling, user-triggered fetches |

```tsx
// Server Component - fetch critical data
async function ProductPage({ id }: { id: string }) {
  const product = await getProduct(id);           // Blocks render
  const reviewsPromise = getReviews(id);          // Start but don't await

  return (
    <div>
      <ProductDetails product={product} />
      <Suspense fallback={<Skeleton />}>
        <Reviews reviewsPromise={reviewsPromise} />
      </Suspense>
    </div>
  );
}

// Client Component - use() for streamed data
"use client";
function Reviews({ reviewsPromise }: { reviewsPromise: Promise<Review[]> }) {
  const reviews = use(reviewsPromise);
  return <ReviewList reviews={reviews} />;
}
```

### useEffect: Treat It as Obsolete

**useEffect is an escape hatch for edge cases. In modern React, virtually every common use has a better alternative. Default to never using it.**

| You want to... | Use instead |
|----------------|-------------|
| Transform data for render | Calculate during render |
| Cache expensive calculations | `useMemo` |
| Reset state when prop changes | `key` prop on component |
| Fetch data | Server Components, `use()`, or TanStack Query |
| Handle user events | Event handlers directly |
| Subscribe to external store | `useSyncExternalStore` |
| Run code once on mount | Ref flag or module-level code |
| Sync with URL params | `useSearchParams` or `nuqs` |
| Animate on mount/unmount | CSS transitions, Framer Motion lifecycle |
| Compute initial state | `useState` lazy initializer `useState(() => compute())` |

```tsx
// ❌ useEffect for derived state (causes double render)
const [fullName, setFullName] = useState('');
useEffect(() => {
  setFullName(`${firstName} ${lastName}`);
}, [firstName, lastName]);

// ✅ Derive during render
const fullName = `${firstName} ${lastName}`;
```

```tsx
// ❌ useEffect for data fetching
useEffect(() => {
  fetch('/api/user').then(r => r.json()).then(setUser);
}, []);

// ✅ TanStack Query (client)
const { data: user } = useQuery({
  queryKey: ['user'],
  queryFn: () => fetch('/api/user').then(r => r.json()),
});

// ✅ Server Component (even better)
async function UserProfile() {
  const user = await getUser();
  return <Profile user={user} />;
}
```

```tsx
// ❌ useEffect for event response
const [shouldSubmit, setShouldSubmit] = useState(false);
useEffect(() => {
  if (shouldSubmit) {
    submitForm();
    setShouldSubmit(false);
  }
}, [shouldSubmit]);

// ✅ Just call the function in the handler
const handleClick = () => {
  submitForm();
};
```

```tsx
// ❌ useEffect for prop sync
useEffect(() => {
  setInternalValue(prop);
}, [prop]);

// ✅ Use key to reset component
<Component key={prop} initialValue={prop} />
```

```tsx
// ❌ useEffect for URL sync
useEffect(() => {
  const params = new URLSearchParams(window.location.search);
  setFilter(params.get('filter'));
}, []);

// ✅ useSearchParams or nuqs
const [filter] = useQueryState('filter');
```

**The only remaining valid uses of useEffect:**
- Imperative sync with DOM-coupled third-party libraries (e.g. a non-React chart widget that needs a DOM node)
- WebSocket / EventSource connections that need cleanup
- `useSyncExternalStore` is unavailable and you must manually subscribe to an external store

If none of these apply, there's a better pattern. See the table above.

### State Anti-Patterns

```tsx
// ❌ Multiple booleans for state (impossible states possible)
const [isLoading, setIsLoading] = useState(false);
const [isError, setIsError] = useState(false);
const [isSuccess, setIsSuccess] = useState(false);

// ✅ Union type (only valid states possible)
const [status, setStatus] = useState<'idle' | 'loading' | 'error' | 'success'>('idle');
```

```tsx
// ❌ Storing derived data in state
const [items, setItems] = useState<Item[]>([]);
const [filteredItems, setFilteredItems] = useState<Item[]>([]);
const [itemCount, setItemCount] = useState(0);

useEffect(() => {
  setFilteredItems(items.filter(i => i.active));
  setItemCount(items.length);
}, [items]);

// ✅ Derive during render
const [items, setItems] = useState<Item[]>([]);
const filteredItems = items.filter(i => i.active);
const itemCount = items.length;
```

### State Management Hierarchy

| Need | Tool |
|------|------|
| Server state (fetched data) | TanStack Query |
| URL state (filters, pagination) | `useSearchParams`, `nuqs` |
| Form state | `useActionState` (React 19) |
| Local UI state | `useState` |
| Shared client state | Zustand (simple) or Jotai (atomic) |

**Avoid:**
- Redux for new projects (unless team already uses it)
- `useContext` for frequently-updating values (causes re-renders)
- Prop drilling more than 2 levels

### Form Handling (React 19)

```tsx
"use client";
import { useActionState } from "react";
import { useFormStatus } from "react-dom";

function SubmitButton() {
  const { pending } = useFormStatus();
  return <button disabled={pending}>{pending ? "Saving..." : "Save"}</button>;
}

function ProfileForm() {
  const [state, formAction, isPending] = useActionState(updateProfile, null);

  return (
    <form action={formAction}>
      <input name="name" />
      {state?.error && <p className="text-red-500">{state.error}</p>}
      <SubmitButton />
    </form>
  );
}

// Server Action
async function updateProfile(prevState: any, formData: FormData) {
  "use server";
  const name = formData.get("name");
  return { success: true };
}
```

### Optimistic Updates

```tsx
"use client";
function TodoList({ todos }: { todos: Todo[] }) {
  const [optimisticTodos, addOptimistic] = useOptimistic(
    todos,
    (state, newTodo: Todo) => [...state, newTodo]
  );

  async function addTodo(formData: FormData) {
    const newTodo = { id: crypto.randomUUID(), text: formData.get("text") };
    addOptimistic(newTodo);
    await createTodoOnServer(newTodo);
  }

  return (
    <form action={addTodo}>
      <input name="text" />
      <button>Add</button>
      <ul>
        {optimisticTodos.map(todo => <li key={todo.id}>{todo.text}</li>)}
      </ul>
    </form>
  );
}
```

### Performance Patterns

```tsx
// ✅ Fetch in parallel, not waterfall
const [user, posts] = await Promise.all([getUser(id), getPosts(id)]);

// ✅ Pass only needed props to client components
<ClientComponent name={user.name} />  // Not the whole user object

// ✅ Use Suspense boundaries strategically
<Suspense fallback={<Skeleton />}>
  <SlowComponent />
</Suspense>

// ✅ Stable references for objects/arrays passed to children
const style = useMemo(() => ({ color: 'red' }), []);
const activeItems = useMemo(() => items.filter(i => i.active), [items]);
```

### DON'T: Unnecessary Memoization

```tsx
// ❌ Memoizing primitives or cheap operations
const value = useMemo(() => items.length, [items]);
const doubled = useMemo(() => count * 2, [count]);

// ❌ useCallback for functions that don't need stable identity
const handleClick = useCallback(() => onClick(), [onClick]);

// ✅ Just compute it
const value = items.length;
const doubled = count * 2;

// ✅ Only memoize when:
// - Passed to memoized child components
// - Used as useEffect dependency
// - Actually expensive to compute
```

---

## Architecture Patterns

### DO: Separate Concerns

```typescript
// ✅ Business logic in domain layer
// lib/pricing.ts
export function calculatePricing(items: Item[]) {
  const subtotal = items.reduce((sum, i) => sum + i.price * i.qty, 0);
  const tax = subtotal * 0.0825;
  const shipping = subtotal > 100 ? 0 : 9.99;
  return { subtotal, tax, shipping, total: subtotal + tax + shipping };
}

// ✅ Component just renders
function PriceDisplay({ items }: { items: Item[] }) {
  const { subtotal, tax, shipping, total } = calculatePricing(items);
  return <div>Total: ${total}</div>;
}
```

### DON'T: Over-Engineering

```typescript
// ❌ Interface with single implementation
interface IUserService {
  getUser(id: string): Promise<User>;
}
class UserService implements IUserService { ... }

// ✅ Just use the class/function directly
class UserService {
  getUser(id: string): Promise<User> { ... }
}

// ❌ Factory for single type
function createButtonFactory(type: 'primary') {
  return (props: ButtonProps) => <Button variant={type} {...props} />;
}

// ✅ Just use the component
<Button variant="primary" {...props} />

// ❌ Config for values that never change
const config = { maxRetries: 3, retryDelay: 1000 };

// ✅ Constants if not user-configurable
const MAX_RETRIES = 3;
const RETRY_DELAY = 1000;
```

### DON'T: Mix Abstraction Levels

```typescript
// ❌ HTTP details mixed with business logic
async function processOrder(order: Order) {
  const response = await fetch('/api/inventory', {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({ sku: order.sku }),
  });
  if (response.status === 409) { /* ... */ }
}

// ✅ Separate transport from domain
async function processOrder(order: Order) {
  const inventory = await inventoryApi.check(order.sku);
  if (!inventory.available) { /* ... */ }
}
```

---

## Code Quality

### DO: Self-Documenting Code

```typescript
// ✅ Clear names, no comments needed
const user = await db.getUser(id);
if (!user) throw new Error('User not found');

// ✅ Comments only for "why", not "what"
// Using binary search because dataset exceeds 10k items
const index = binarySearch(sortedItems, target);
```

### DON'T: Code Noise

```typescript
// ❌ Over-commenting
// Get the user from the database
const user = await db.getUser(id);
// Check if user exists
if (!user) {
  // Throw an error if user not found
  throw new Error('User not found');
}

// ❌ Verbose variable names
const userDataFromDatabase = await getUser(id);
const isUserCurrentlyLoggedIn = user.loggedIn;
const arrayOfUserIds = users.map(u => u.id);

// ✅ Concise but clear
const user = await getUser(id);
const isLoggedIn = user.loggedIn;
const userIds = users.map(u => u.id);
```

### DON'T: Leave Artifacts

```typescript
// ❌ Dead code
import { useState, useEffect, useMemo } from 'react'; // only useState used

function oldFunction() { /* never called */ }

// ❌ TODO graveyards
// TODO: Add error handling
// TODO: Optimize this later
// FIXME: This is a workaround

// ❌ Console logs
console.log('data:', data);
console.log('debugging here');
```

---

## Security

### DON'T: Security Smells

```typescript
// ❌ Hardcoded secrets
const API_KEY = 'sk-1234567890abcdef';

// ❌ SQL injection
const query = `SELECT * FROM users WHERE id = ${id}`;

// ❌ XSS
element.innerHTML = userInput;

// ❌ Eval
eval(userCode);

// ❌ Disabled security
// @ts-ignore
process.env.NODE_TLS_REJECT_UNAUTHORIZED = '0';
```

### DO: Validate External Data

```typescript
// ✅ Zod schema for API responses
const userSchema = z.object({
  id: z.string(),
  name: z.string(),
  email: z.string().email(),
});

const user = userSchema.parse(await fetch('/api/user').then(r => r.json()));

// ✅ Parameterized queries
const user = await db.query.users.findFirst({
  where: eq(users.id, id),
});
```

---

## Performance

### DON'T: N+1 Queries

```typescript
// ❌ Query per item
const users = await db.getUsers();
for (const user of users) {
  user.orders = await db.getOrders(user.id);
}

// ✅ Single query with join
const users = await db.query.users.findMany({
  with: { orders: true },
});
```

### DON'T: Blocking Operations

```typescript
// ❌ Sync file operations in request handler
const data = fs.readFileSync(path);

// ✅ Async
const data = await fs.promises.readFile(path);
```

### DON'T: Unstable References

```tsx
// ❌ New object every render
<Component style={{ color: 'red' }} />
<Component data={data.filter(x => x.active)} />

// ✅ Stable references
const style = useMemo(() => ({ color: 'red' }), []);
// or define outside component if truly static
const redStyle = { color: 'red' };
```

---

## Quick Reference

### TypeScript Checklist
- [ ] No `any` types (use `unknown` + validation)
- [ ] No non-null assertions (`!`)
- [ ] No `as` for external data
- [ ] Const objects over enums
- [ ] Let inference work (no redundant annotations)
- [ ] Explicit enum values if enums are required

### React Checklist
- [ ] Server Components by default
- [ ] No useEffect (treat as obsolete — use the alternatives table)
- [ ] If useEffect appears, justify it against the 3 valid use cases
- [ ] No useEffect for derived state, data fetching, or event responses
- [ ] Union types for state machines
- [ ] TanStack Query for server state
- [ ] URL state with useSearchParams/nuqs

### Code Quality Checklist
- [ ] No dead code/unused imports
- [ ] No TODO/FIXME graveyards
- [ ] No console.log artifacts
- [ ] No over-commenting
- [ ] No verbose variable names
- [ ] Business logic separated from UI

### Security Checklist
- [ ] No hardcoded secrets
- [ ] Parameterized queries
- [ ] No innerHTML with user input
- [ ] No eval()
- [ ] External data validated with Zod
