---
description: Deep codebase analysis and AI slop cleanup - acts as a nitpicky senior engineer
---

# slop - Clean Up AI Slop

Thoroughly analyze the entire codebase and clean up AI-generated code patterns. Acts as a local senior engineer with extreme attention to detail.

## Invocation

- `/bruhs:slop` - Full codebase analysis
- `/bruhs:slop src/components` - Analyze specific directory
- `/bruhs:slop --fix` - Auto-fix safe issues, prompt for others
- `/bruhs:slop --report` - Generate report only, no fixes

## Philosophy

> "AI slop is output that seems adequate on the surface but falls short in substance—code that appears syntactically correct but is missing depth, context, or relevance."

This command embodies the mindset of a senior engineer who:
- **Reads type signatures first** - Types are the primary documentation
- Values simplicity over cleverness
- Removes code rather than adds it
- Questions every abstraction
- Treats technical debt as a personal insult
- Knows that the best code is no code

## Best Practices Reference

Slop detects violations of the patterns defined in:

- **`practices/type-driven-design.md`** - **PRIMARY** - Type signatures, explicit errors, immutability
- **`practices/_common.md`** - Universal patterns (naming, git, errors, testing)
- **`practices/typescript-react.md`** - TypeScript + React (incl. TS 5.4+ + Next.js 16)
- **`practices/typescript-hono.md`** - Hono framework patterns (loaded when `framework: hono`)
- **`practices/python.md`** - Modern Python 3.13+ (loaded when `language: python` or Python framework)
- **`practices/python-fastapi.md`** - FastAPI specifics (loaded when `framework: fastapi`)
- **`practices/effect-ts.md`** - Effect-TS specific patterns (loaded when `effect` in `stack.libraries`)
- **`practices/rust.md`** - Idiomatic Rust patterns (loaded when `language: rust` or Rust framework in stack)
- **`practices/rust-references/`** - Deep refs (ownership, errors, async, type-state, leptos, gpui, axum) — loaded conditionally

**Read these files for the full pattern catalog.** The sections below summarize what slop detects.

## The Priority Hierarchy

**Type signatures are #1. Performance anti-patterns are real bugs, not style nits** — they rank above architecture and style because they're cheap to fix and expensive to leave in.

| Priority | Category | Why |
|----------|----------|-----|
| **1** | Type Signatures | Types ARE the documentation |
| **2** | Security | Can cause real damage |
| **3** | Performance Anti-Patterns | N+1, `await`-in-loop, sync-in-async, per-request clients — they're bugs, not optimizations |
| **4** | Error Handling | Errors hidden from types = signature lies |
| **5** | Architecture | Structural issues compound |
| **6** | Immutability | Mutations hidden from types = surprise side effects |
| **7** | Code Style | Nitpicks, but they add up |

> **Performance note**: slop flags *anti-patterns* aggressively (no benchmark required — they're just wrong). Slop flags *speculative optimizations* skeptically — "I refactored for performance" without measurement is slop of a different kind.

## The Analysis Pillars

Slop analyzes code through these lenses, **in priority order**:

| Pillar | Focus |
|--------|-------|
| **Type Signatures** | Do signatures tell the full story? Are errors explicit? |
| **Security** | SQL injection, XSS, hardcoded secrets, unbounded input? |
| **Performance** | N+1 queries, `await`-in-loop, sync-in-async, per-request clients, unbounded concurrency, missing cache headers, render waterfalls |
| **Error Handling** | Graceful failures? Errors in return types? |
| **Architecture** | Does it fit the system, or fight it? |
| **Immutability** | Are mutations visible? Is state predictable? |
| **Readability** | Can a human understand this in 30 seconds? |
| **Standards** | Consistent with codebase conventions? |

## AI Slop Patterns

> Full type-driven patterns in `practices/type-driven-design.md`
> Stack-specific patterns in `practices/typescript-react.md`

### Category 0: Type Signature Violations (HIGHEST PRIORITY)

**The most important category.** Types are documentation. Bad types = misleading documentation.

**0.1 Missing/Implicit Return Types**
```typescript
// SLOP: Return type inferred, readers must trace implementation
const getUsers = async () => {
  const res = await fetch('/api/users');
  return res.json(); // What type? Promise<any>?
};

// CLEAN: Explicit return type documents the contract
async function getUsers(): Promise<User[]> {
  const res = await fetch('/api/users');
  return userArraySchema.parse(await res.json());
}
```

**0.2 Errors Hidden from Types**
```typescript
// SLOP: Throws are invisible - signature lies
function parseConfig(text: string): Config {
  return JSON.parse(text); // Can throw, but signature doesn't say so
}

// CLEAN: Error possibility explicit in return type
function parseConfig(text: string): Config | ParseError {
  try {
    return configSchema.parse(JSON.parse(text));
  } catch (e) {
    return new ParseError(e.message);
  }
}

// CLEAN: Or use Result type (better-result)
function parseConfig(text: string): Result<Config, ParseError> {
  return Result.try({
    try: () => configSchema.parse(JSON.parse(text)),
    catch: (e) => new ParseError(e.message),
  });
}
```

**0.3 Side Effects Hidden from Types**
```typescript
// SLOP: Signature doesn't reveal side effects
function getUser(id: string): User {
  logger.info(`Fetching user ${id}`);  // Hidden side effect
  metrics.increment('user.fetch');      // Hidden side effect
  return cache.get(id) ?? db.get(id);   // Hidden I/O
}

// CLEAN: Async signals I/O, name signals retrieval
async function fetchUser(id: string): Promise<User | null> {
  return userRepository.findById(id);
}
```

**0.4 Overly Wide Types**
```typescript
// SLOP: String is too wide - loses information
function getStatus(user: User): string {
  return user.active ? 'active' : 'inactive';
}

// CLEAN: Narrow union type documents possibilities
function getStatus(user: User): 'active' | 'inactive' {
  return user.active ? 'active' : 'inactive';
}
```

**0.5 Mutable Parameters Without Signal**
```typescript
// SLOP: Signature doesn't reveal mutation
function sortUsers(users: User[]): User[] {
  return users.sort((a, b) => a.name.localeCompare(b.name)); // Mutates input!
}

// CLEAN: readonly signals no mutation, returns new array
function sortUsers(users: readonly User[]): User[] {
  return [...users].sort((a, b) => a.name.localeCompare(b.name));
}
```

### Category 1: Over-Engineering (YAGNI Violations)

**1.1 Unnecessary Abstractions**
```typescript
// SLOP: Interface with single implementation
interface IUserService {
  getUser(id: string): Promise<User>;
}
class UserService implements IUserService {
  getUser(id: string): Promise<User> { ... }
}

// CLEAN: Just use the class directly
class UserService {
  getUser(id: string): Promise<User> { ... }
}
```

**1.2 Premature Generalization**
```typescript
// SLOP: Config for things that will never change
const config = {
  maxRetries: 3,
  retryDelay: 1000,
  enableLogging: true,
  logLevel: 'info',
  ...
};

// CLEAN: Just use the values inline if they're not user-configurable
const MAX_RETRIES = 3;
```

**1.3 Factory Pattern Abuse**
```typescript
// SLOP: Factory for a single type
function createButtonFactory(type: 'primary') {
  return function createButton(props: ButtonProps) {
    return <Button variant={type} {...props} />;
  };
}

// CLEAN: Just use the component
<Button variant="primary" {...props} />
```

**1.4 Wrapper Functions That Add Nothing**
```typescript
// SLOP
const handleClick = () => {
  onClick();
};

// CLEAN
onClick // just pass the function directly
```

### Category 2: TypeScript Anti-Patterns

**2.1 `any` Type Usage**
```typescript
// SLOP
function processData(data: any) { ... }

// CLEAN: Use proper types or unknown
function processData(data: unknown) {
  if (isValidData(data)) { ... }
}
```

**2.2 Non-Null Assertions (`!`)**
```typescript
// SLOP: Lying to the compiler
const user = users.find(u => u.id === id)!;

// CLEAN: Handle the undefined case
const user = users.find(u => u.id === id);
if (!user) throw new Error(`User ${id} not found`);
```

**2.3 Type Assertions for External Data**
```typescript
// SLOP: Trusting external data
const data = await fetch('/api/users').then(r => r.json()) as User[];

// CLEAN: Validate with Zod or similar
const data = userArraySchema.parse(await fetch('/api/users').then(r => r.json()));
```

**2.4 Redundant Type Annotations**
```typescript
// SLOP: TypeScript already infers this
const count: number = 0;
const name: string = "hello";
const users: User[] = getUsers(); // if getUsers returns User[]

// CLEAN: Let inference work
const count = 0;
const name = "hello";
const users = getUsers();
```

**2.5 Overly Flexible Props**
```typescript
// SLOP
interface Props {
  data: any;
  options?: Record<string, unknown>;
  callback?: (...args: any[]) => any;
}

// CLEAN: Be specific
interface Props {
  user: User;
  onSave: (user: User) => void;
}
```

### Category 3: React Anti-Patterns

**3.1 State That Should Be Derived**
```typescript
// SLOP: Double render, state sync bugs
const [fullName, setFullName] = useState('');
useEffect(() => {
  setFullName(`${firstName} ${lastName}`);
}, [firstName, lastName]);

// CLEAN: Derive during render
const fullName = `${firstName} ${lastName}`;
```

**3.2 Multiple Booleans for State**
```typescript
// SLOP: Impossible states possible
const [isLoading, setIsLoading] = useState(false);
const [isError, setIsError] = useState(false);
const [isSuccess, setIsSuccess] = useState(false);

// CLEAN: Union type
const [status, setStatus] = useState<'idle' | 'loading' | 'error' | 'success'>('idle');
```

**3.3 useEffect for Event Handlers**
```typescript
// SLOP
useEffect(() => {
  if (shouldSubmit) {
    submitForm();
    setShouldSubmit(false);
  }
}, [shouldSubmit]);

// CLEAN: Just call the function
const handleSubmit = () => {
  submitForm();
};
```

**3.4 Prop Drilling with Context Overkill**
```typescript
// SLOP: Context for 2-level prop passing
const ThemeContext = createContext();
// ... 50 lines of provider/consumer setup

// CLEAN: Just pass the prop
<Button theme={theme} />
```

**3.5 Unnecessary Memoization**
```typescript
// SLOP: Premature optimization
const value = useMemo(() => items.length, [items]);
const handleClick = useCallback(() => onClick(), [onClick]);

// CLEAN: Just compute it
const value = items.length;
```

### Category 4: Code Noise

**4.1 Over-Commenting**
```typescript
// SLOP: Comments that explain what code does
// Get the user from the database
const user = await db.getUser(id);
// Check if user exists
if (!user) {
  // Throw an error if user not found
  throw new Error('User not found');
}

// CLEAN: Self-documenting code needs no comments
const user = await db.getUser(id);
if (!user) throw new Error('User not found');
```

**4.2 Verbose Variable Names**
```typescript
// SLOP: Names that add no information
const userDataFromDatabase = await getUser(id);
const isUserCurrentlyLoggedIn = user.loggedIn;
const arrayOfUserIds = users.map(u => u.id);

// CLEAN: Concise but clear
const user = await getUser(id);
const isLoggedIn = user.loggedIn;
const userIds = users.map(u => u.id);
```

**4.3 Dead Code / Unused Imports**
```typescript
// SLOP
import { useState, useEffect, useMemo, useCallback } from 'react'; // only useState used
import { User, Admin, Guest } from './types'; // only User used

function oldFunction() { /* never called */ }
const DEPRECATED_CONSTANT = 'old'; // never used
```

**4.4 TODO Comments as Permanent Fixtures**
```typescript
// SLOP: TODOs that will never be done
// TODO: Add error handling
// TODO: Optimize this later
// TODO: Fix this hack
// FIXME: This is a workaround
```

**4.5 Console Logs Left Behind**
```typescript
// SLOP
console.log('data:', data);
console.log('debugging here');
console.log('TODO: remove this');
```

### Category 5: Copy-Paste Duplication

**5.1 Slightly Different Implementations**
```typescript
// SLOP: Three retry implementations with different bugs
// In file A:
const fetchWithRetry = async (url) => { /* version 1 */ };
// In file B:
const retryFetch = async (url) => { /* version 2, different timeout */ };
// In file C:
const fetchRetrying = async (url) => { /* version 3, missing error case */ };

// CLEAN: One implementation, shared
```

**5.2 Repeated Patterns Without Abstraction**
```typescript
// SLOP: Same 5 lines repeated 10 times
const handleUserClick = () => {
  setLoading(true);
  try {
    await fetchUser();
  } catch (e) {
    setError(e);
  } finally {
    setLoading(false);
  }
};
// ... same pattern for handleOrderClick, handleProductClick, etc.
```

### Category 6: Security Smells

**6.1 Hardcoded Secrets**
```typescript
// SLOP
const API_KEY = 'sk-1234567890abcdef';
const password = 'admin123';
```

**6.2 Unsafe Patterns**
```typescript
// SLOP: SQL injection
const query = `SELECT * FROM users WHERE id = ${id}`;

// SLOP: XSS
element.innerHTML = userInput;

// SLOP: eval
eval(userCode);
```

**6.3 Disabled Security**
```typescript
// SLOP
// @ts-ignore
// eslint-disable-next-line
process.env.NODE_TLS_REJECT_UNAUTHORIZED = '0';
```

### Category 7: Performance Anti-Patterns

These are **bugs, not optimizations.** Flag them regardless of benchmark — the fast path is the correct path.

**7.1 N+1 Queries**
```typescript
// SLOP
const users = await db.getUsers();
for (const user of users) {
  user.orders = await db.getOrders(user.id); // N queries
}

// CLEAN: Single query with join or batch
const users = await db.getUsersWithOrders();
```

**7.2 `await` Inside a Loop Over Independent Items**
```typescript
// SLOP: Serial I/O dressed as async
const results = [];
for (const id of ids) {
  results.push(await fetchOne(id));
}

// CLEAN: Parallel with bounded concurrency
import pLimit from "p-limit";
const limit = pLimit(20);
const results = await Promise.all(ids.map(id => limit(() => fetchOne(id))));
```

**7.3 Per-Request Client Construction**
```typescript
// SLOP: No connection pool, new TLS every call
app.get("/users", async () => {
  const client = new PrismaClient();
  return client.user.findMany();
});

// CLEAN: Singleton at module scope
const db = new PrismaClient();
app.get("/users", async () => db.user.findMany());
```

**7.4 Sync I/O in Async Handlers**
```typescript
// SLOP: Blocks the entire event loop
const data = fs.readFileSync(path);

// CLEAN
const data = await fs.promises.readFile(path);
```

**7.5 Unbounded Concurrency on User Input**
```typescript
// SLOP: User sends 10,000 ids → 10,000 concurrent connections → OOM
await Promise.all(ids.map(fetchOne));

// CLEAN: Bounded
const limit = pLimit(20);
await Promise.all(ids.map(id => limit(() => fetchOne(id))));
```

**7.6 Fetch Waterfall Instead of Parallel**
```typescript
// SLOP: 2× the latency
const user = await getUser(id);
const posts = await getPosts(id);

// CLEAN
const [user, posts] = await Promise.all([getUser(id), getPosts(id)]);
```

**7.7 Unstable References → Unnecessary Re-renders**
```typescript
// SLOP: New object reference every render
<Component style={{ color: 'red' }} />

// CLEAN: Hoist static values out
const RED = { color: 'red' };
<Component style={RED} />
```

**7.8 Defensive Memoization**
```typescript
// SLOP: Memoizing primitives or cheap expressions (pure overhead)
const value = useMemo(() => items.length, [items]);
const handleClick = useCallback(() => onClick(), [onClick]);

// CLEAN: Just compute. Memoize only with measured re-render problem.
const value = items.length;
```

**7.9 N+1 HTTP / Fetch-In-Map**
```typescript
// SLOP: Per-item API call
const enriched = await Promise.all(ids.map(id => fetch(`/api/user/${id}`)));

// CLEAN: Batch endpoint
const enriched = await fetch("/api/users", { method: "POST", body: JSON.stringify({ ids }) });
```

**7.10 Full-Body Request/Response Logging**
```typescript
// SLOP: JSON.stringify dominates CPU under load
logger.info({ req: JSON.stringify(req), res: JSON.stringify(res) });

// CLEAN: Structured fields, sampled bodies
logger.info({ path: req.path, status: res.status, durationMs });
```

### Category 8: Architectural Violations

**8.1 Circular Dependencies**
```
// SLOP
// utils.ts imports from components/Button.tsx
// components/Button.tsx imports from utils.ts
```

**8.2 Business Logic in UI**
```typescript
// SLOP: Calculation in component
function PriceDisplay({ items }) {
  const subtotal = items.reduce((sum, i) => sum + i.price * i.qty, 0);
  const tax = subtotal * 0.0825;
  const shipping = subtotal > 100 ? 0 : 9.99;
  const total = subtotal + tax + shipping;
  // ...
}

// CLEAN: Extract to domain logic
function PriceDisplay({ items }) {
  const { subtotal, tax, shipping, total } = calculatePricing(items);
  // ...
}
```

**8.3 Mixed Abstraction Levels**
```typescript
// SLOP: HTTP details mixed with business logic
async function processOrder(order: Order) {
  const response = await fetch('/api/inventory', {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({ sku: order.sku }),
  });
  if (response.status === 409) {
    // handle conflict
  }
  // ... business logic continues
}
```

## Workflow

### Step 1: Load Configuration

```bash
# Read bruhs.json for stack context
cat .claude/bruhs.json
```

Understand the stack to apply relevant rules:
- TypeScript strictness expectations
- React version and patterns
- Database/ORM conventions
- Testing framework

### Step 2: Gather Codebase Metrics

```bash
# File counts by type
find src -name "*.ts" -o -name "*.tsx" | wc -l

# Lines of code
cloc src --json

# Dependency count
jq '.dependencies | length' package.json
```

### Step 3: Run Static Analysis

**TypeScript Strict Checks:**
```bash
# Check for any types
grep -rn ": any" src/ --include="*.ts" --include="*.tsx"

# Check for non-null assertions
grep -rn "!\." src/ --include="*.ts" --include="*.tsx"
grep -rn "!;" src/ --include="*.ts" --include="*.tsx"

# Check for ts-ignore
grep -rn "@ts-ignore" src/ --include="*.ts" --include="*.tsx"
grep -rn "@ts-expect-error" src/ --include="*.ts" --include="*.tsx"
```

**Dead Code Detection:**
```bash
# Unused exports (if using knip or similar)
npx knip --no-exit-code 2>/dev/null || echo "knip not installed"

# Unused dependencies
npx depcheck --json 2>/dev/null || echo "depcheck not installed"
```

**React Health Check (if React project):**
```bash
# Run react-doctor for React-specific diagnostics
npx -y react-doctor@latest .
```

**Security Scan:**
```bash
# Check for hardcoded secrets patterns
grep -rn "password\s*=" src/ --include="*.ts" --include="*.tsx"
grep -rn "secret\s*=" src/ --include="*.ts" --include="*.tsx"
grep -rn "api_key\s*=" src/ --include="*.ts" --include="*.tsx"
grep -rn "sk-" src/ --include="*.ts" --include="*.tsx"

# Check for dangerous patterns
grep -rn "innerHTML" src/ --include="*.tsx"
grep -rn "dangerouslySetInnerHTML" src/ --include="*.tsx"
grep -rn "eval(" src/ --include="*.ts" --include="*.tsx"
```

### Step 4: Deep Code Analysis

**Load practices in priority order:**

```javascript
// ALWAYS load type-driven design first - it's the primary lens
typePractices = Read('practices/type-driven-design.md');

// Load common practices
commonPractices = Read('practices/_common.md');

// Determine stack from bruhs.json and load stack-specific practices
const stack = config.stack?.framework || 'typescript';
const language = config.stack?.language;
const libs = config.stack?.libraries || [];

if (['nextjs', 'next.js', 'react-native', 'tauri', 'electron'].includes(stack)) {
  stackPractices = Read('practices/typescript-react.md');
} else if (stack === 'hono') {
  stackPractices = Read('practices/typescript-hono.md');
} else if (language === 'python' || ['fastapi', 'django', 'flask', 'starlette'].includes(stack)) {
  // Always load the Python base
  stackPractices = Read('practices/python.md');
  // Load framework-specific on top
  if (stack === 'fastapi') {
    stackPractices += Read('practices/python-fastapi.md');
  }
} else if (
  language === 'rust' ||
  ['leptos', 'axum', 'actix', 'rocket', 'tauri-rust', 'gpui'].includes(stack)
) {
  stackPractices = Read('practices/rust.md');

  // Load deep refs only for the frameworks/runtimes actually in use
  rustRefs = [];
  if (libs.includes('tokio') || libs.includes('async-std') || stack === 'axum') {
    rustRefs.push(Read('practices/rust-references/async-patterns.md'));
  }
  if (stack === 'leptos') {
    rustRefs.push(Read('practices/rust-references/leptos-patterns.md'));
  }
  if (stack === 'gpui') {
    rustRefs.push(Read('practices/rust-references/gpui-patterns.md'));
  }
  if (stack === 'axum') {
    rustRefs.push(Read('practices/rust-references/axum-patterns.md'));
  }
  // Always-useful refs for Rust work
  rustRefs.push(Read('practices/rust-references/ownership-and-borrowing.md'));
  rustRefs.push(Read('practices/rust-references/error-design.md'));
  rustRefs.push(Read('practices/rust-references/type-state-and-newtypes.md'));
}

// Load Effect practices if stack uses Effect
if (config.stack?.libraries?.includes('effect')) {
  effectPractices = Read('practices/effect-ts.md');
}
```

For each file, analyze using the Task tool with code-explorer agent:

```
Analyze this file for AI slop patterns, IN PRIORITY ORDER:

**PRIORITY 1 - Type Signatures (most important):**
- Missing/implicit return types on public functions
- Errors hidden from types (throws without return type signal)
- Side effects hidden from types
- Overly wide types (string when union would be specific)
- Mutable parameters without readonly

**PRIORITY 2 - Error Handling:**
- Errors not in return types
- String errors instead of typed errors
- Empty catch blocks / swallowed errors
- Deferred error handling

**PRIORITY 3 - Immutability:**
- Parameter mutation
- Hidden state changes
- Unnecessary cloning vs proper borrowing

**PRIORITY 4 - Other Issues:**
- Over-engineering (unnecessary abstractions, premature generalization)
- TypeScript anti-patterns (any, !, as, redundant types)
- React anti-patterns (derived state, multiple booleans, unnecessary effects)
- Code noise (over-commenting, verbose names, dead code)
- Duplication (copy-paste, inconsistent patterns)
- Security smells
- Performance issues
- Architectural violations

Be extremely nitpicky. Type signature issues are the highest priority.
```

### Step 5: Pattern Correlation

Look for codebase-wide patterns:

**Inconsistency Detection:**
- Multiple error handling approaches
- Different naming conventions across files
- Inconsistent file/folder structure
- Mixed import styles (default vs named)

**Duplication Detection:**
- Similar functions with different names
- Repeated utility code
- Copy-pasted components with minor variations

### Step 6: Generate Report

Group findings by severity:

```
# AI Slop Analysis Report

## Critical (Must Fix)
Security vulnerabilities, data loss risks, broken functionality

## High (Should Fix)
Performance issues, architectural violations, maintainability blockers

## Medium (Consider Fixing)
Code smells, minor anti-patterns, inconsistencies

## Low (Nitpicks)
Style issues, naming suggestions, minor improvements

---

## Summary

| Category | Critical | High | Medium | Low |
|----------|----------|------|--------|-----|
| Over-engineering | 0 | 3 | 12 | 5 |
| TypeScript | 2 | 8 | 15 | 3 |
| React | 0 | 5 | 20 | 10 |
| Code Noise | 0 | 2 | 8 | 25 |
| Duplication | 0 | 4 | 6 | 2 |
| Security | 1 | 2 | 0 | 0 |
| Performance | 0 | 3 | 5 | 2 |
| Architecture | 0 | 2 | 4 | 1 |

Total Issues: 143
Estimated Cleanup: ~2-3 focused sessions
```

### Step 7: Interactive Fixing (if --fix)

For each issue, in order of severity:

```
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
[1/143] HIGH | TypeScript | src/lib/api.ts:45
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

Issue: Using `any` type for API response

Current:
```typescript
async function fetchUser(id: string): Promise<any> {
  const res = await fetch(`/api/users/${id}`);
  return res.json();
}
```

Suggested fix:
```typescript
async function fetchUser(id: string): Promise<User> {
  const res = await fetch(`/api/users/${id}`);
  return userSchema.parse(await res.json());
}
```
```

Then use `AskUserQuestion`:

```javascript
AskUserQuestion({
  questions: [{
    question: "How would you like to handle this issue?",
    header: "Action",
    multiSelect: false,
    options: [
      { label: "Apply fix", description: "Apply the suggested fix" },
      { label: "Skip", description: "Address later" },
      { label: "Mark intentional", description: "Add comment explaining why" },
      { label: "Show context", description: "See more surrounding code" },
    ]
  }]
})

**Auto-fixable issues (applied without prompt):**
- Unused imports
- Console.log removal
- Redundant type annotations
- Simple formatting

**Prompt for:**
- Type changes
- Logic modifications
- Architectural refactors
- Anything that could change behavior

### Step 8: Verification

After fixes:

```bash
# Type check
pnpm tsc --noEmit

# Lint
pnpm lint

# Tests
pnpm test

# Build
pnpm build
```

### Step 9: Summary

```
# Slop Cleanup Complete

## Changes Made
- Removed 23 unused imports
- Fixed 8 `any` type usages
- Simplified 5 over-engineered abstractions
- Removed 12 unnecessary comments
- Consolidated 3 duplicate utility functions
- Fixed 2 security issues

## Files Modified
- src/lib/api.ts (5 changes)
- src/components/UserCard.tsx (3 changes)
- src/hooks/useAuth.ts (2 changes)
- ...

## Remaining Issues (skipped)
- 15 low-priority nitpicks
- 3 issues marked as intentional

## Recommendations
1. Enable stricter TypeScript settings in tsconfig.json
2. Add knip to CI for dead code detection
3. Consider extracting src/lib/utils.ts patterns into shared package

Ready to commit? Run /bruhs:yeet
```

## Configuration

Add slop settings to `.claude/bruhs.json`:

```json
{
  "slop": {
    "severity": "nitpicky",  // "relaxed" | "balanced" | "nitpicky" | "brutal"
    "autoFix": ["unused-imports", "console-logs", "redundant-types"],
    "ignore": [
      "src/generated/**",
      "**/*.test.ts",
      "**/*.d.ts"
    ],
    "rules": {
      "no-any": "error",
      "no-non-null-assertion": "warn",
      "max-function-lines": 50,
      "max-file-lines": 300
    }
  }
}
```

**Severity levels:**
- `relaxed` - Only critical issues
- `balanced` - Critical + high
- `nitpicky` - Critical + high + medium (default)
- `brutal` - Everything, no mercy

## Examples

### Full Codebase Scan

```
> /bruhs:slop

Scanning codebase...
├── src/app/ (24 files)
├── src/components/ (45 files)
├── src/lib/ (18 files)
├── src/hooks/ (12 files)
└── src/stores/ (6 files)

Running static analysis...
✓ TypeScript strict checks
✓ Dead code detection
✓ Security scan
✓ Dependency audit

Deep analysis in progress...
[████████████████████████████████] 100%

# AI Slop Analysis Report

## Critical (2)
1. [SECURITY] Hardcoded API key in src/lib/api.ts:12
2. [SECURITY] SQL injection vulnerability in src/lib/db.ts:45

## High (15)
...
```

Then use `AskUserQuestion`:

```javascript
AskUserQuestion({
  questions: [{
    question: "Would you like to view the full report?",
    header: "Report",
    multiSelect: false,
    options: [
      { label: "Yes", description: "Show all issues by category" },
      { label: "No", description: "Continue to fixing" },
    ]
  }]
})

### Targeted Directory

```
> /bruhs:slop src/components

Scanning src/components/ (45 files)...

## High (3)
1. UserCard.tsx - Derived state anti-pattern (lines 23-28)
2. Modal.tsx - Multiple boolean state (lines 15-18)
3. Form.tsx - Over-engineered validation factory (lines 45-120)

## Medium (12)
...
```

Then use `AskUserQuestion`:

```javascript
AskUserQuestion({
  questions: [{
    question: "Fix issues interactively?",
    header: "Fix",
    multiSelect: false,
    options: [
      { label: "Yes", description: "Go through each issue" },
      { label: "No", description: "Generate report only" },
    ]
  }]
})

### Auto-Fix Mode

```
> /bruhs:slop --fix

Auto-fixing safe issues...
✓ Removed 23 unused imports
✓ Removed 8 console.log statements
✓ Removed 15 redundant type annotations

Interactive fixes remaining: 28
```

Then use `AskUserQuestion`:

```javascript
AskUserQuestion({
  questions: [{
    question: "Continue with interactive fixes?",
    header: "Continue",
    multiSelect: false,
    options: [
      { label: "Yes", description: "Address remaining issues one by one" },
      { label: "No", description: "Stop here" },
    ]
  }]
})

## Tips

- **Run regularly** - Weekly slop checks prevent accumulation
- **Start with --report** - Understand scope before fixing
- **Fix by category** - Do all TypeScript issues, then React, etc.
- **Trust the nitpicks** - Small issues compound into big problems
- **Update bruhs.json** - Tune rules based on your codebase
- **Pair with tests** - Run tests after each batch of fixes

## References

Research and best practices informing this command:

- [AI Code Quality State 2025](https://www.qodo.ai/reports/state-of-ai-code-quality/)
- [Era of AI Slop Cleanup](https://bytesizedbets.com/p/era-of-ai-slop-cleanup-has-begun)
- [Copilot Code Smells Research](https://arxiv.org/html/2401.14176v2)
- [React TypeScript Code Smells](https://www.sciencedirect.com/science/article/abs/pii/S0950584925001740)
- [Over-Engineering Anti-Patterns](https://medium.com/@srinathperera/a-deeper-look-at-software-architecture-anti-patterns-9ace30f59354)
- [Code Review Best Practices 2026](https://www.codeant.ai/blogs/code-review-best-practices)
