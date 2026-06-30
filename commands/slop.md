---
description: Deep codebase audit — types, security, performance, errors, architecture — acting as a nitpicky senior engineer with severity levels (relaxed/balanced/nitpicky/brutal). Use when cleaning up AI-generated code, preparing for review, or auditing a module.
---

# slop - Clean Up AI Slop

Thoroughly analyze the entire codebase and clean up AI-generated code patterns. Acts as a local senior engineer with extreme attention to detail.

## Contents

- [Invocation](#invocation)
- [Philosophy](#philosophy)
- [Best Practices Reference](#best-practices-reference)
- [The Priority Hierarchy](#the-priority-hierarchy)
- [The Analysis Pillars](#the-analysis-pillars)
- [AI Slop Patterns](#ai-slop-patterns)
- [Workflow](#workflow)
- [Configuration](#configuration)
- [Examples](#examples)
- [Tips](#tips)
- [References](#references)

---

## Invocation

- `/bruhs:slop` - Full codebase analysis
- `/bruhs:slop src/components` - Analyze specific directory
- `/bruhs:slop --quick` - **Branch-diff-only fast pass** — only look at lines this branch added vs `origin/<base>`. See [Quick Mode](#quick-mode).
- `/bruhs:slop --fix` - Auto-fix safe issues, prompt for others
- `/bruhs:slop --report` - Generate report only, no fixes
- `/bruhs:slop --severity relaxed|balanced|nitpicky|brutal` - Override the default severity (default: balanced)

## Quick Mode

`--quick` runs slop only against **lines the current branch added or changed vs the base branch**. It's the lightest tier: catches AI patterns introduced on this branch without re-auditing the whole codebase.

### When to use

- Right before `/bruhs:yeet` to catch slop you wrote in the last 30 minutes.
- After `/bruhs:cook` to clean up a fresh feature branch before opening a PR.
- When the full slop pass would be too noisy and you only care about *this branch's* contributions.
- Pre-commit hook context — fast enough to run on every commit.

### What it checks (subset of full slop)

Quick mode focuses on the AI-slop patterns that are most likely to be **introduced by this branch's diff**, not codebase-wide structural issues:

- Extra comments inconsistent with surrounding file style
- Defensive `try/catch` blocks around trusted internal calls
- `as any` / `as unknown as X` casts used to bypass real type issues
- Deeply nested conditionals that should be early returns
- Re-exported types or `// removed` placeholder comments for deleted code
- Backwards-compat shims for code paths that no longer exist
- Test descriptions that restate the function name (`describe('drawCard', () => it('drawCard', …))`)
- Comments that explain WHAT the code does (the code already shows that), instead of WHY
- UI/motion slop in added visible-surface code: `transition: all`,
  `ease-in` on UI, `scale(0)` entrances, layout-property animation, missing
  `prefers-reduced-motion`, ungated hover motion

### What it skips

- Architecture / abstraction quality (use full `/bruhs:slop` or `/bruhs:deepen`)
- Cross-file consistency or naming patterns
- Performance anti-patterns introduced outside the diff
- Type-driven-design violations in files this branch didn't touch
- File-size thresholds (`/bruhs:slop --severity brutal` for that)

### Workflow

```bash
# 1. Get the diff vs the upstream/base branch
BASE=$(git merge-base HEAD origin/main)
git diff --unified=0 "$BASE"...HEAD > /tmp/slop-quick-diff.patch

# 2. Extract the added/changed line ranges per file
git diff --name-only "$BASE"...HEAD
```

For each file in the diff:

1. Read the file.
2. For each `@@ … +<start>,<count> @@` hunk, look at the **added** lines (and a small window of surrounding context).
3. Apply the quick-mode pattern checks above.
4. Emit findings only when the *added* code is responsible — don't flag patterns that pre-existed.

### Guardrails

- **Behavior must stay unchanged.** Quick mode is style and AI-slop cleanup, not refactoring.
- **Prefer minimal, focused edits** over broad rewrites. If a fix would touch lines this branch didn't change, surface it as a follow-up — don't widen the diff.
- **Keep the summary concise** (1-3 sentences). Quick mode's job is to be fast, not exhaustive.

### Example

```
> /bruhs:slop --quick

Diffing son-m7-api-sdk against origin/main…
  9 files changed, +423 / -287, scanning 67 added hunks

apps/web/src/app/api/v1/route.ts
  L42: unnecessary try/catch around `parseBody()` — Zod already throws a typed error
  L78: comment "// validate input" restates obvious code — drop
  L104: `as any` to silence rate-limit return type — let me fix that

packages/sdk/src/client.ts
  L23: deep nesting around fetch retry — flatten with early-return on `!response.ok`

Recommended fixes (3 of 4 auto-safe):
  ✓ Remove try/catch at route.ts:42
  ✓ Drop comment at route.ts:78
  ✓ Flatten retry block at client.ts:23
  ⚠ Replace `as any` at route.ts:104 — needs a real return type, suggesting `Result<RateLimitInfo, RateLimitError>`

Apply auto-safe fixes? [Y/n]
```

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
- **`practices/source-ground-truth.md`** - Before flagging "misuse of `<library>`", confirm against that library's real source (`opensrc`) — a slop finding that misreads a dependency's API is itself slop
- **`practices/typescript-react.md`** - TypeScript + React (incl. TS 5.4+ + Next.js 16)
- **`practices/typescript-hono.md`** - Hono framework patterns (loaded when `framework: hono`)
- **`practices/python.md`** - Modern Python 3.13+ (loaded when `language: python` or Python framework)
- **`practices/python-fastapi.md`** - FastAPI specifics (loaded when `framework: fastapi`)
- **`practices/effect-ts.md`** - Effect-TS specific patterns (loaded when `effect` in `stack.libraries`)
- **`practices/rust.md`** - Idiomatic Rust patterns (loaded when `language: rust` or Rust framework in stack)
- **`practices/rust-*.md`** - Deep Rust refs (`rust-ownership-and-borrowing`, `rust-error-design`, `rust-async-patterns`, `rust-type-state-and-newtypes`, `rust-leptos-patterns`, `rust-gpui-patterns`, `rust-axum-patterns`) — loaded conditionally
- **`practices/ui-design.md`** - UI quality lens for visible product surfaces
- **`practices/design-engineering.md`** - Emil-derived motion/component polish standards; load when reviewing UI, animation, gestures, popovers, drawers, tooltips, tabs, toasts, loading states, or component feel

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

## Brutal Mode (Thermo-Nuclear)

`--severity brutal` is the strictest review tier. Beyond reporting every finding the other tiers would catch, it applies an additional set of **structural** rules with one overarching mandate:

> **Be ambitious about structural simplification.** Don't stop at "this could be a bit cleaner." Look for restructurings that delete whole branches, helpers, conditionals, or layers entirely. Prefer the solution that makes the code feel inevitable in hindsight.

### Code-Judo Mandate

For every meaningful change in the diff, ask:

- Is there a reframing that deletes whole categories of complexity, not just rearranges them?
- Can this change use the existing architecture more effectively, so fewer concepts are introduced?
- Is there a clear path to **delete** complexity rather than centralize it?

Refactors that merely move complexity around but fail to reduce the number of concepts a reader must hold in their head are flagged — not approved.

### Brutal-Only Findings

These are reported in `brutal` and only in `brutal`:

1. **File size explosion**
   - A PR that pushes a file from under 1000 lines to over 1000 lines is a presumptive blocker.
   - Treat as a strong code-quality smell. Prefer extracting helpers/subcomponents/modules.
   - Waive only with a compelling structural reason **and** the resulting file is still clearly organized.

2. **Spaghetti growth in existing code**
   - New ad-hoc conditionals, one-off branches, or special cases inserted into unrelated flows.
   - "Weird if statements in random places" is a design problem, not a stylistic nit.
   - Prefer pushing the logic into a dedicated abstraction, helper, state machine, or policy object.

3. **Thin / magical abstractions**
   - Identity wrappers, pass-through helpers, generic mechanisms that hide simple data-shape assumptions.
   - Indirection that doesn't buy clarity.
   - Push back: "this abstraction seems unnecessary, can we just keep the direct flow?"

4. **Canonical-layer leaks**
   - Feature logic leaking into shared/general-purpose paths.
   - Implementation details leaking through APIs.
   - Bespoke helpers where the codebase already has a canonical utility.
   - Push back: "this looks like feature logic leaking into a shared path — can we isolate it?"

5. **Type / boundary churn**
   - Unnecessary `any` / `unknown` / casts that obscure the real contract.
   - Optional params used to paper over an unclear invariant.
   - Silent fallback branches instead of explicit boundaries.

6. **Sequential orchestration where parallel is obvious**
   - Independent async work serialized for no good reason.
   - Non-atomic updates that can leave state half-applied when an atomic structure is achievable.

7. **Refactors that don't actually simplify**
   - Diff moves code around but doesn't reduce the conceptual surface area.
   - "Cleaner version of the same messy idea" when a much simpler idea is plausible.

### Approval Bar in Brutal Mode

Brutal does not approve merely because behavior is correct. Treat these as **presumptive blockers** unless explicitly justified:

- The PR pushes a file from below 1000 lines to above 1000 lines.
- The PR adds ad-hoc branching that tangles an existing flow.
- The PR solves a local problem by scattering feature checks across shared code.
- The PR adds an unnecessary wrapper, cast-heavy contract, or thin abstraction.
- The PR duplicates a canonical helper or puts logic in the wrong layer.
- The PR preserves a lot of incidental complexity when a code-judo move would delete it.

If any condition above is present, leave explicit, actionable feedback and push for a cleaner decomposition. Do not rubber-stamp.

### Tone (Brutal Only)

Direct, serious, demanding. Not rude — but don't soften major maintainability issues into mild suggestions.

Good phrases for `brutal` output:

- `this pushes the file past 1k lines. can we decompose first?`
- `this adds another special-case branch into an already busy flow. can we move it behind its own abstraction?`
- `this works, but it makes the surrounding code more spaghetti. let's keep the behavior and restructure the implementation.`
- `this feels like feature logic leaking into a shared path. can we isolate it?`
- `this abstraction seems unnecessary. can we keep the direct flow?`
- `i think there's a code-judo move here that makes this much simpler. can we reframe this so these branches disappear?`
- `this refactor moves complexity around but doesn't delete it. is there a way to make the model itself simpler?`

### Output Prioritization (Brutal Only)

In `brutal`, prioritize findings in this order:

1. Structural code-quality regressions (file size, spaghetti, layer leaks)
2. Missed code-judo opportunities (dramatic simplifications left on the table)
3. Boundary / abstraction / type-contract problems
4. Modularity / abstraction issues
5. Legibility / maintainability concerns

Prefer a smaller number of high-conviction comments over a long list of cosmetic notes. If there's a structural issue, lead with it — don't bury it under nits.

## Workflow

### Step 1: Load Configuration

```bash
# Read bruhs:state from CLAUDE.md (fallback AGENTS.md, then legacy .claude/bruhs.json)
python3 <PLUGIN_DIR>/scripts/read_bruhs_block.py --kind state --root .
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

Slop calls `scripts/validate_pr_ready.sh` by default — it already detects the language and runs the right checkers. If the script isn't available, fall back to the inline language-specific commands below.

```bash
# Preferred: delegate to the canonical runner
bash scripts/validate_pr_ready.sh 2>/dev/null || echo "validate_pr_ready.sh not available — falling back to inline detection"
```

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

**Non-TypeScript static analysis — route by `config.stack?.language`:**

```javascript
switch (config.stack?.language) {
  case 'python':
    // Lint + type-check + dead-test detection
    Bash("ruff check .");
    Bash("mypy ." /* or `ty check` if `ty` is present in the project */);
    Bash("pytest --collect-only"); // surfaces dead / uncollectable tests
    break;

  case 'rust':
    Bash("cargo check --all-targets");
    Bash("cargo clippy --all-targets -- -D warnings");
    break;

  case 'go':
    Bash("go vet ./...");
    Bash("go build ./...");
    break;

  default:
    // TypeScript path above already ran
    break;
}
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

// Determine stack from bruhs:state and load stack-specific practices
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
    rustRefs.push(Read('practices/rust-async-patterns.md'));
  }
  if (stack === 'leptos') {
    rustRefs.push(Read('practices/rust-leptos-patterns.md'));
  }
  if (stack === 'gpui') {
    rustRefs.push(Read('practices/rust-gpui-patterns.md'));
  }
  if (stack === 'axum') {
    rustRefs.push(Read('practices/rust-axum-patterns.md'));
  }
  // Always-useful refs for Rust work
  rustRefs.push(Read('practices/rust-ownership-and-borrowing.md'));
  rustRefs.push(Read('practices/rust-error-design.md'));
  rustRefs.push(Read('practices/rust-type-state-and-newtypes.md'));
}

// Load Effect practices if stack uses Effect
if (config.stack?.libraries?.includes('effect')) {
  effectPractices = Read('practices/effect-ts.md');
}

// Load UI/motion practices when the target includes user-visible surfaces.
if (targetTouchesUI || diffTouchesUI || config.stack?.animation) {
  uiPractices = Read('practices/ui-design.md');
  designEngineering = Read('practices/design-engineering.md');
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
- UI/motion slop when visible surfaces are touched:
  - `transition: all`, `ease-in` on UI, `scale(0)` entrances
  - animation on keyboard/high-frequency actions
  - UI duration > 300ms without interaction-specific justification
  - centered transform origin on trigger-anchored popovers/dropdowns/tooltips
  - keyframes for rapidly-triggered or gesture-driven motion
  - layout-property animation instead of transform/opacity
  - missing `prefers-reduced-motion` or ungated hover motion
  - Framer Motion/Motion shorthand `x`/`y`/`scale` under load
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

After fixes, slop calls `scripts/validate_pr_ready.sh` by default — it detects the language and runs the full verification matrix. If the script isn't available, fall back to the inline language-specific commands below.

```bash
# Preferred: delegate to the canonical runner
bash scripts/validate_pr_ready.sh 2>/dev/null || echo "validate_pr_ready.sh not available — falling back to inline detection"
```

**TypeScript (default path):**
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

**Non-TypeScript verification — route by `config.stack?.language`:**

```javascript
switch (config.stack?.language) {
  case 'python':
    Bash("ruff check .");
    Bash("mypy ." /* or `ty check` if the project uses `ty` */);
    Bash("pytest");
    break;

  case 'rust':
    Bash("cargo check --all-targets");
    Bash("cargo clippy --all-targets -- -D warnings");
    Bash("cargo test");
    break;

  case 'go':
    Bash("go vet ./...");
    Bash("go build ./...");
    Bash("go test ./...");
    break;

  default:
    // TypeScript path above already ran
    break;
}
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

Add slop settings to the `bruhs:state` block (in `CLAUDE.md` / `AGENTS.md`):

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
- **Update bruhs:state** - Tune rules in CLAUDE.md / AGENTS.md based on your codebase
- **Pair with tests** - Run tests after each batch of fixes

## References

Research and best practices informing this command:

- [AI Code Quality State 2025](https://www.qodo.ai/reports/state-of-ai-code-quality/)
- [Era of AI Slop Cleanup](https://bytesizedbets.com/p/era-of-ai-slop-cleanup-has-begun)
- [Copilot Code Smells Research](https://arxiv.org/html/2401.14176v2)
- [React TypeScript Code Smells](https://www.sciencedirect.com/science/article/abs/pii/S0950584925001740)
- [Over-Engineering Anti-Patterns](https://medium.com/@srinathperera/a-deeper-look-at-software-architecture-anti-patterns-9ace30f59354)
- [Code Review Best Practices 2026](https://www.codeant.ai/blogs/code-review-best-practices)
