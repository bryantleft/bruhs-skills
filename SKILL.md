---
name: bruhs
description: End-to-end development lifecycle for Claude Code — scaffold projects, plan and build features, create Linear tickets, open and review PRs, clean up after merge, audit codebases. Use when starting a project, implementing a feature, shipping code, addressing PR reviews, merging, or auditing code quality.
---

# bruhs

## Index
|commands|spawn,claim,cook,yeet,peep,dip,slop,doodle
|practices|type-driven-design,_common,pr-review,typescript-react,typescript-hono,python,python-fastapi,effect-ts,effect-*,rust,rust-*,ui-design
|config|.claude/bruhs.json

## Commands Quick Reference
|spawn|Create project or add to monorepo|commands/spawn.md
|claim|Initialize config for existing project|commands/claim.md
|cook|Plan + Build feature end-to-end|commands/cook.md
|yeet|Ship: Linear ticket → Branch → Commit → PR|commands/yeet.md
|peep|Address PR review comments and merge|commands/peep.md
|dip|Clean up after merge, switch to base branch|commands/dip.md
|slop|Deep codebase analysis, AI slop cleanup|commands/slop.md
|doodle|Visualize architecture as tldraw diagrams (PRs, modules, deps, compare, map, freeform)|commands/doodle.md

## Invocation
- `/bruhs` → Interactive menu (AskUserQuestion)
- `/bruhs:<command>` → Direct to command
- `/bruhs:cook <feature>` or `/bruhs:cook TICKET-123` → With argument
- `/bruhs:slop [path] [--fix|--report]` → Codebase analysis
- `/bruhs:doodle <mode> [args] [--out|--gist|--commit|--pr-comment|--format|--depth]` → Render diagram (modes: pr, module, deps, dependents, compare, map, freeform)

---

## Type-Driven Design

> A function's type signature should tell you everything about what it does.

### Priority Hierarchy (fix in this order)
1. **Missing/wrong type signatures** - Types ARE documentation
2. **Hidden side effects** - Signature lies about behavior
3. **any** types - Type system disabled
4. **!** or **as** on external data - Compiler trust violated
5. **Fast-path violations** - `await` in loops, N+1 queries, sync-in-async, per-request client construction (see Performance below)
6. **Other implementation issues** - Secondary to type correctness

### Checklist
**Signatures:**
- [ ] Explicit return types on public functions
- [ ] No **any** - use unknown + validation
- [ ] No **!** - handle null explicitly
- [ ] No **as** for external data - validate instead
- [ ] Errors in return type, not thrown silently
- [ ] **readonly** parameters signal no mutation
- [ ] Discriminated unions for state (not multiple booleans)

**Errors:**
- [ ] Errors visible in return type (Result<T,E> or union)
- [ ] Typed errors, not strings
- [ ] Handle at call site, not deferred
- [ ] No empty catch blocks

**Immutability:**
- [ ] Prefer **const** over **let**
- [ ] Don't mutate parameters
- [ ] Return new objects instead of mutating

### Patterns
```typescript
// ❌ Signature hides truth
function getUser(id: string): User  // might throw, might be null

// ✅ Signature tells full story
function getUser(id: string): Promise<Result<User, NotFoundError | NetworkError>>

// ❌ Multiple booleans = impossible states
type State = { isLoading: boolean; isError: boolean; data: User | null }

// ✅ Discriminated union = only valid states
type State =
  | { status: 'idle' }
  | { status: 'loading' }
  | { status: 'success'; data: User }
  | { status: 'error'; error: Error }
```

For full patterns → `practices/type-driven-design.md`

---

## Common Rules

### Naming
|Type|Convention|Example|
|---|---|---|
|Components|PascalCase|`UserCard.tsx`|
|Hooks|camelCase + `use`|`useAuth.ts`|
|Utilities|camelCase|`formatDate.ts`|
|Constants|SCREAMING_SNAKE|`MAX_RETRIES`|
|Booleans|is/has/can/should|`isLoading`, `hasPermission`|
|Functions|verb + noun|`getUser`, `createOrder`|
|Handlers|handle/on prefix|`handleSubmit`, `onUserClick`|

### Code Organization
- Functions do ONE thing
- 20-30 lines max per function
- 200-300 lines max per file
- If you need comments to separate sections → extract functions

### Error Handling
- Specific messages: `User "${id}" not found` not `Something went wrong`
- Validate at boundaries, trust internal code
- Never swallow errors (empty catch blocks)

### Git
```
<type>: <description>

Fixes TICKET-123
```
Types: `feat|fix|refactor|chore|docs|test`

Branch: `<type>/<ticket-id>-<short-description>`

### Comments
- ✅ WHY (business logic, workarounds, non-obvious decisions)
- ❌ WHAT (code already says what it does)
- ❌ Commented-out code
- ❌ TODO without ticket reference

### External Searches
Always include current year in WebSearch queries for fresh results.

For full guidelines → `practices/_common.md`

---

## Performance (Fast-Path-By-Default)

> Pick the fast path by default. You don't need a benchmark to avoid an anti-pattern.

### Philosophy
- **Correctness first, but equivalent-correctness patterns are not equivalent.** When two patterns solve the same problem, pick the faster one — even without a measurement.
- **Obvious perf wins don't require benchmarks.** N+1 queries, `await` in a loop, sync I/O on the event loop, per-request client construction — these are anti-patterns, not "premature optimization."
- **Measure when the tradeoff is real** (readability cost, complexity cost, risk of regression). Don't measure to justify avoiding an anti-pattern.
- **Measure at boundaries, not inside** — p50/p95/p99 at ingress/egress; internal timers lie about contention.

### Universal Defaults
- **Batch at boundaries.** One round-trip of N beats N round-trips (DB, HTTP, IPC, GPU, syscalls).
- **Stream, don't buffer.** Start bytes moving before you have them all — SSR, JSON, file I/O, LLM tokens.
- **Don't block the hot loop.** Event loop, render thread, request handler — push CPU off, I/O async, never sync-in-async.
- **Colocate data with consumer.** Query next to its route, fetch next to its RSC, cache next to its reader.
- **Built-ins beat rewrites.** `Array.prototype`, `itertools`, `std::collections`, platform `fetch`.
- **Bound concurrency on user input.** `p-limit`, `asyncio.Semaphore`, `buffer_unordered(n)` — unbounded `Promise.all` over user data is a DoS.
- **Singleton clients.** Never `new Client()` per request — it defeats connection pooling.

### LLM-Common Traps (flag these in review)
1. `await` in a `for` loop over independent items → `Promise.all` / `gather` / `join!`
2. `.map().filter().reduce()` chains over large arrays → one pass or lazy iterator
3. N+1 ORM access in "clean" code → eager/join loading
4. `useMemo`/`useCallback` sprinkled without a measured re-render problem
5. `JSON.parse(JSON.stringify(x))` for deep clone → `structuredClone` or targeted copy
6. Unbounded `Promise.all` / recursion over user input → clamp concurrency
7. Sync hashing/crypto in request path → worker / threadpool
8. Per-request client construction (`new PrismaClient`, `httpx.AsyncClient()`, `reqwest::Client::new()`) → singleton
9. Full-body logging in hot paths → structured log fields
10. Parsing config / reading env per request → load once at boot

Per-stack performance patterns → `practices/<stack>.md` (Performance section in each)

---

## Command Details

Each command's full workflow lives in its own file. Read the specific file when executing that command:

| Command | File |
|---|---|
| cook  | `commands/cook.md` |
| yeet  | `commands/yeet.md` |
| peep  | `commands/peep.md` |
| dip   | `commands/dip.md` |
| spawn | `commands/spawn.md` |
| claim | `commands/claim.md` |
| slop  | `commands/slop.md` |
| doodle | `commands/doodle.md` |

---

## Interactive Menu

When `/bruhs` is invoked without arguments, present the command list via `AskUserQuestion` and route to the selected command's file. Options: spawn, claim, cook, yeet, peep, doodle, dip. `slop` is intentionally excluded from the menu — invoke directly with `/bruhs:slop`.

---

## Config Reference

`.claude/bruhs.json`:
```json
{
  "integrations": {
    "linear": {
      "mcpServer": "linear-<workspace>",
      "team": "<team-id>",
      "teamName": "Team Name",
      "project": "<project-id>",
      "projectName": "Project Name",
      "labels": { "feat": "Feature", "fix": "Bug", "chore": "Chore", "refactor": "Improvement" }
    }
  },
  "tooling": {
    "mcps": ["linear", "notion", "context7"],
    "skills": ["superpowers", "shadcn", "vercel-react-best-practices"]
  },
  "stack": {
    "structure": "turborepo|standalone",
    "framework": "nextjs|tanstack-start|astro|hono|...",
    "styling": ["tailwind", "shadcn"],
    "database": ["drizzle-postgres", "convex", "..."],
    "auth": "better-auth|clerk|...",
    "gpu": ["modal", "runpod", "lambda"]
  }
}
```

---

## Linear MCP

Tool format: `mcp__<mcpServer>__linear_<method>`

Common tools:
|Tool|Purpose|
|---|---|
|`linear_get_teams`|List teams (includes labels)|
|`linear_get_user`|Current user (for assigneeId)|
|`linear_create_issue`|Create ticket|
|`linear_edit_issue`|Update status|
|`linear_get_issue`|Fetch ticket by ID|

Multi-workspace: Each project's bruhs.json points to its Linear workspace via `mcpServer`.

Example:
```javascript
// Load the tool
ToolSearch(`select:mcp__${config.integrations.linear.mcpServer}__linear_create_issue`)

// Create issue
const issue = call(`mcp__linear-sonner__linear_create_issue`, {
  title: "Add leaderboard",
  teamId: config.integrations.linear.team,
  projectId: config.integrations.linear.project,
  assigneeId: user.viewer.id,
  labelIds: [labelId]
})

// Use Linear's generated branch name
const branchName = issue.gitBranchName  // "sonner-140-add-leaderboard"
```
