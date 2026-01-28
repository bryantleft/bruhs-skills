---
description: Plan + Build a feature end-to-end
---

# cook - Plan + Build Features

Combined planning and building workflow. Wraps brainstorming and feature development patterns into a single end-to-end flow.

## Invocation

- `/bruhs:cook <feature>` - Start cooking a specific feature
- `/bruhs:cook` - Interactive mode, will ask what to build

## Core Principles

All code produced by cook follows these principles:

| Principle | Description |
|-----------|-------------|
| **Atomic Design** | Hierarchical component architecture (atoms → molecules → organisms → templates → pages) |
| **Clean** | Simple, readable, maintainable code |
| **Immutability** | Predictable state and data flow |
| **Scalable** | Architecture that grows with your needs |
| **Maintainable** | Long-term sustainability and extensibility |
| **Single Source of Truth** | One authoritative source for each piece of data |

## React 19+ Best Practices

When the stack includes React/Next.js, follow these modern patterns. These override legacy patterns you may have learned.

### Server Components First

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

Use the right tool for each layer:

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
        <Reviews reviewsPromise={reviewsPromise} />  {/* Stream to client */}
      </Suspense>
    </div>
  );
}

// Client Component - use() for streamed data
"use client";
function Reviews({ reviewsPromise }: { reviewsPromise: Promise<Review[]> }) {
  const reviews = use(reviewsPromise);  // Suspends until resolved
  return <ReviewList reviews={reviews} />;
}
```

### Avoid useEffect

**useEffect is not deprecated, but it's rarely the right choice.** Before using `useEffect`, check this table:

| You want to... | Use instead |
|----------------|-------------|
| Transform data for render | Calculate during render (derive from props/state) |
| Cache expensive calculations | `useMemo` |
| Reset state when prop changes | `key` prop on component |
| Fetch data | Server Components, `use()` hook, or TanStack Query |
| Handle user events | Event handlers directly |
| Subscribe to external store | `useSyncExternalStore` |
| Run code once on mount | Top-level module code or ref flag |

```tsx
// ❌ Anti-pattern: useEffect for derived state
const [fullName, setFullName] = useState('');
useEffect(() => {
  setFullName(firstName + ' ' + lastName);
}, [firstName, lastName]);

// ✅ Correct: derive during render
const fullName = firstName + ' ' + lastName;

// ❌ Anti-pattern: useEffect for data fetching
useEffect(() => {
  fetch('/api/user').then(r => r.json()).then(setUser);
}, []);

// ✅ Correct: Server Component or TanStack Query
const { data: user } = useQuery({
  queryKey: ['user'],
  queryFn: () => fetch('/api/user').then(r => r.json()),
});
```

### Form Handling with Actions

Use React 19's form primitives instead of manual state:

```tsx
"use client";
import { useActionState } from "react";
import { useFormStatus } from "react-dom";

// Submit button in separate component (required for useFormStatus)
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
  // validate, save to db, return result
  return { success: true };
}
```

### Optimistic Updates

Use `useOptimistic` for instant UI feedback:

```tsx
"use client";
function TodoList({ todos }: { todos: Todo[] }) {
  const [optimisticTodos, addOptimistic] = useOptimistic(
    todos,
    (state, newTodo: Todo) => [...state, newTodo]
  );

  async function addTodo(formData: FormData) {
    const newTodo = { id: crypto.randomUUID(), text: formData.get("text") };
    addOptimistic(newTodo);           // Instant UI update
    await createTodoOnServer(newTodo); // Server catches up
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

### State Management

| Need | Tool |
|------|------|
| Server state (fetched data) | TanStack Query |
| URL state (filters, pagination) | `useSearchParams`, `nuqs` |
| Form state | `useActionState` |
| Local UI state | `useState` |
| Shared client state | Zustand (simple) or Jotai (atomic) |

**Avoid:** Redux for new projects, `useContext` for frequently-updating values, prop drilling more than 2 levels.

### Performance Patterns

```tsx
// ✅ Fetch in parallel, not waterfall
const [user, posts] = await Promise.all([
  getUser(id),
  getPosts(id),
]);

// ✅ Pass only needed props to client components
<ClientComponent name={user.name} />  // Not the whole user object

// ✅ Use Suspense boundaries strategically
<Suspense fallback={<Skeleton />}>
  <SlowComponent />
</Suspense>
```

## Workflow

### Step 0: Check Config

```bash
ls .claude/bruhs.json 2>/dev/null
```

If config doesn't exist:
```
No bruhs.json found. Would you like to:
○ Run /bruhs claim (recommended) - Full setup with stack detection
○ Continue without config - Will skip Linear integration
```

If user chooses to continue without config:
- Skip Linear-related features
- Use sensible defaults for stack detection
- Remind user at end: "Run /bruhs claim to enable full features"

### Step 1: Understand

Clarify what we're building:

1. Parse the feature request
2. Ask clarifying questions if needed:
   - What's the user story?
   - What are the acceptance criteria?
   - Any constraints or preferences?

Output a brief summary:
```
Feature: <name>
Goal: <what it achieves>
Scope: <what's included/excluded>
```

### Step 2: Explore

Launch code-explorer agents to understand the codebase:

```
Exploring codebase...
- Found: <relevant file 1>
- Found: <relevant file 2>
- Pattern: <existing pattern that applies>
```

Use the Task tool with `subagent_type: "feature-dev:code-explorer"` to:
- Find related code
- Understand existing patterns
- Map dependencies
- Identify integration points

### Step 3: Plan

Design 2-3 approaches based on exploration:

```
Planning...

**Approach 1: <name>**
- Description: <how it works>
- Files to modify: <list>
- Pros: <benefits>
- Cons: <tradeoffs>

**Approach 2: <name>**
- Description: <how it works>
- Files to modify: <list>
- Pros: <benefits>
- Cons: <tradeoffs>

Which approach? [1/2]
```

Use brainstorming patterns:
- Consider multiple solutions
- Evaluate tradeoffs
- Present options clearly
- Let user choose

### Step 4: Setup

Prepare the working environment:

**Check for unrelated changes:**
```bash
git status
git diff --stat
```

If there are uncommitted changes unrelated to the feature:
```bash
git stash push -m "bruhs: stashed before <feature-name>"
```

Track that we stashed:
```
stashed_changes = true
```

**Important:** Do NOT create a branch here. Branch creation happens in `/bruhs:yeet` after code is complete.

### Step 5: Build

Implement the feature using TDD where applicable:

**For testable code:**
1. Write failing test
2. Implement minimum code to pass
3. Refactor
4. Repeat

**For UI/non-testable code:**
1. Implement component/feature
2. Manual verification
3. Refactor

Use feature-dev patterns:
- Follow existing code conventions
- Apply atomic design for components
- Maintain single source of truth
- Keep functions pure where possible

**Progress output:**
```
Building...
✓ Created <file>
✓ Modified <file>
✓ Added tests for <feature>
✓ All tests passing
```

### Step 6: Review

Launch code-reviewer agents to check the implementation:

Use the Task tool with `subagent_type: "feature-dev:code-reviewer"` to:
- Check for bugs
- Verify logic
- Look for security issues
- Ensure code quality
- Check adherence to project conventions

```
Reviewing...
✓ No high-confidence issues found
```

Or if issues found:
```
Reviewing...
⚠ Found issues:
  - <issue 1>
  - <issue 2>

Fixing...
✓ Fixed <issue 1>
✓ Fixed <issue 2>
```

### Step 7: Ready to Ship

Signal completion and prompt for shipping:

```
Ready to ship! Run /bruhs:yeet to create ticket and PR.
```

If we stashed changes:
```
Ready to ship! Run /bruhs:yeet to create ticket and PR.
💡 You have stashed changes from before this feature (git stash pop to restore)
```

## Example

```
> /bruhs:cook add leaderboard to game page

Understanding...
Feature: Leaderboard
Goal: Show top AI agents by win rate on game page
Scope: Game page UI only, uses existing agentStats data

Exploring codebase...
- Found: app/game/[matchId]/page.tsx (game page)
- Found: lib/db/schema.ts (agentStats table)
- Found: app/stats/page.tsx (existing stats UI patterns)
- Found: components/ui/card.tsx (card component)
- Pattern: Server components with TanStack Query for data

Planning...

**Approach 1: Inline LeaderboardCard**
- Add LeaderboardCard component to game page
- Query agentStats directly in server component
- Files: app/game/[matchId]/page.tsx, components/game/leaderboard-card.tsx
- Pros: Simple, fast to implement, follows existing patterns
- Cons: Couples game page to stats data

**Approach 2: Separate route + embed**
- Create /leaderboard route
- Import component into game page
- Files: app/leaderboard/page.tsx, components/leaderboard.tsx, app/game/[matchId]/page.tsx
- Pros: Reusable, standalone page option
- Cons: More files, extra complexity

Which approach? [1]

> 1

Setting up...
✓ Working directory clean (no stash needed)

Building...
✓ Created components/game/leaderboard-card.tsx
✓ Added getTopAgents query to lib/db/queries.ts
✓ Modified app/game/[matchId]/page.tsx
✓ Added tests for leaderboard-card
✓ All tests passing

Reviewing...
✓ No high-confidence issues found

Ready to ship! Run /bruhs:yeet to create ticket and PR.
```

## Integration with Other Skills

| Phase | Pattern Source |
|-------|----------------|
| Plan | `superpowers:brainstorming` patterns |
| Build | `feature-dev:feature-dev` patterns |
| Review | `superpowers:requesting-code-review` patterns |

Cook implements its own workflow but draws on these established patterns.

## Configuration

Reads `.claude/bruhs.json` for:
- Stack info (to understand project conventions)
- Linear config (for ticket references if needed)

## Tips

- **Be specific** - "add dark mode" is okay, "add dark mode toggle to header with system preference detection" is better
- **Start small** - Cook works best for focused features, not massive rewrites
- **Trust the review** - If code-reviewer finds issues, fix them before shipping
- **Use /bruhs:yeet** - Don't manually commit after cook, let yeet handle the full shipping workflow
