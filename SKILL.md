---
name: bruhs
description: End-to-end development lifecycle for AI coding agents — scaffold projects, plan and build features, create Linear tickets, open and review PRs, clean up after merge, audit codebases. Works with any agent that reads CLAUDE.md or AGENTS.md. Use when starting a project, implementing a feature, shipping code, addressing PR reviews, merging, or auditing code quality.
---

# bruhs

## Index
|commands|spawn,claim,cook,verify,yeet,walk,land,peep,dip,slop,doodle,deepen,drill,recap
|practices|type-driven-design,architecture-deepening,testing-infrastructure,source-ground-truth,_common,pr-review,typescript-react,typescript-hono,python,python-fastapi,effect-ts,effect-*,rust,rust-*,ui-design
|config|CLAUDE.md + AGENTS.md (`bruhs:state` and `bruhs:rules` blocks)

## Commands Quick Reference
|spawn|Create project or add to monorepo|commands/spawn.md
|claim|Initialize config for existing project|commands/claim.md
|cook|Plan + Build feature end-to-end|commands/cook.md
|verify|Prove a claim with falsifiable evidence (VERIFIED/NOT VERIFIED/INCONCLUSIVE)|commands/verify.md
|yeet|Ship: Linear ticket → Branch → Commit → PR|commands/yeet.md
|walk|Generate reviewer walkthrough (markdown or interactive HTML canvas)|commands/walk.md
|land|Watch PR checks and iterate on CI failures until green|commands/land.md
|peep|Address PR review comments and merge|commands/peep.md
|dip|Clean up after merge, switch to base branch|commands/dip.md
|slop|Deep codebase analysis, AI slop cleanup (--quick for branch-diff only)|commands/slop.md
|doodle|Visualize architecture as tldraw diagrams (PRs, modules, deps, compare, map, freeform)|commands/doodle.md
|deepen|Find shallow modules, propose architectural deepenings (explore → candidates → grill)|commands/deepen.md
|drill|Find missing/weak test-infra layers, propose adoptions (explore → candidates → grill)|commands/drill.md
|recap|Status update from git log over a time window (bugfix/tech-debt/net-new)|commands/recap.md

## Lifecycle Map

Commands compose into an end-to-end loop. Typical flow:

```
spawn / claim          → project setup
        ↓
cook <feature>         → plan + build
        ↓
verify <claim>         → prove the behavior changed (recommended for fixes)
        ↓
slop --quick           → clean up branch-diff slop before shipping
        ↓
yeet                   → Linear ticket + branch + commit + PR
        ↓
walk --post            → reviewer walkthrough comment (large PRs)
        ↓
land                   → watch CI to green
        ↓
peep                   → address review comments (compose with land via --land)
        ↓
dip                    → post-merge cleanup
```

Out-of-band, any time:
- `slop` — deep codebase audit
- `doodle` / `deepen` / `drill` — structural / test-infra investigation
- `recap` — status update for standup or retro

## Invocation
- `/bruhs` → Interactive menu (AskUserQuestion)
- `/bruhs:<command>` → Direct to command
- `/bruhs:cook <feature>` or `/bruhs:cook TICKET-123` → With argument
- `/bruhs:verify [claim | PR#] [--keep-artifacts]` → Falsifiable verification
- `/bruhs:walk [PR#] [--canvas|--post|--commit-body]` → Reviewer walkthrough
- `/bruhs:land [PR#] [--no-fix|--max-iterations N]` → Watch CI to green
- `/bruhs:peep [PR# | TICKET] [--land|--resolve-conflicts]` → Address review comments
- `/bruhs:slop [path] [--quick|--fix|--report] [--severity ...]` → Codebase analysis
- `/bruhs:doodle <mode> [args] [--out|--gist|--commit|--pr-comment|--format|--depth]` → Render diagram (modes: pr, module, deps, dependents, compare, map, freeform)
- `/bruhs:deepen [path | module-name] [--no-explore]` → Find shallow modules, propose deepenings
- `/bruhs:drill [path | layer-name] [--no-explore]` → Find missing/weak test-infra layers, propose adoptions
- `/bruhs:recap [window] [--all-authors|--linear|--branch <name>]` → Status update from git log

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

## Architectural Deepening

> A deep module hides a lot of behaviour behind a small interface. A shallow module's interface is nearly as complex as its implementation.

Use the `/bruhs:deepen` command to find shallow modules and propose deepenings. Distinct from `/bruhs:slop` (line-level audit) — this is **structural**.

### Vocabulary (use these terms exactly)

|Term|Meaning|
|---|---|
|**Module**|Anything with an interface and an implementation (function, class, package, slice)|
|**Interface**|Everything a caller must know — types, invariants, ordering, errors, configuration|
|**Depth**|Behaviour-per-unit-of-interface. Deep = lots of behaviour behind a small interface|
|**Seam**|A place where you can alter behaviour without editing in that place (Feathers)|
|**Adapter**|A concrete thing that satisfies an interface at a seam|
|**Leverage**|Caller-side benefit of depth — capability per unit of interface learned|
|**Locality**|Maintainer-side benefit — change/bugs/tests concentrate in one place|

### Core principles

- **Depth is a property of the interface, not the implementation.** Internal seams are fine; don't expose them.
- **The deletion test.** Imagine deleting the module. If complexity vanishes → pass-through, merge it. If it scatters across N callers → the module earns its keep.
- **The interface is the test surface.** If you want to test *past* it, the module is the wrong shape.
- **One adapter means a hypothetical seam. Two adapters means a real one.** Don't add a port for a single implementation.

### When to invoke `/bruhs:deepen`

- A codebase feels like it bounces between many small files for one operation
- Tests feel like they're testing the wrong thing (mocks everywhere, brittle to refactors)
- Callers must learn implementation details (transport, encoding, storage) to use a "domain" module
- Same invariant repeats across N call sites
- During `/bruhs:slop` you keep flagging "architecture" — promote to `/bruhs:deepen` for structural treatment

For full glossary, dependency categories, seam discipline, design-it-twice mechanics → `practices/architecture-deepening.md`

---

## Testing Infrastructure

> A test suite is a layered safety net. Each layer catches a different bug class. A missing layer isn't covered by the others — it's just where bugs ship from.

Use the `/bruhs:drill` command to find missing or weak layers and propose adoption plans. Companion to `/bruhs:deepen`: deepen modules, drill tests.

### The 8 layers

|#|Layer|Catches|
|---|---|---|
|1|**Acceptance specs**|Intent drift — no executable definition of "done"|
|2|**Unit tests**|Regressions in module behaviour at the interface|
|3|**Coverage gate**|Untested code landing (measured on **changed lines per PR**, not total)|
|4|**Mutation runner**|Tests that exist but assert nothing meaningful — the **kill ratio** is the only number that proves coverage is doing work|
|5|**Complexity composite**|High-complexity / low-coverage hotspots (the worst-of-both — Savoia's "CRAP")|
|6|**Architecture checker**|Layer / dependency rule violations — encodes ADRs so they're enforced, not just documented|
|7|**Test-code linter**|Rot in test files themselves; AI-generated test code becoming a second untyped codebase|
|8|**CI orchestrator**|Discipline collapse — runs every layer as hard gates. The 8th is load-bearing|

### Core principles

- **Hard gate, advisory, or ratchet — pick one, defend it.** Indefinite advisory is decoration. Ratchet ("no worse than baseline") is honest about legacy debt and locks in improvement.
- **The orchestrator is load-bearing.** Layers 1–7 without a real CI gate are theatre. `continue-on-error: true` on a gated layer is advisory regardless of what the config claims.
- **Replace, don't layer.** Old advisory checks become waste once a hard gate exists. Old shallow-module tests become waste once the deeper module's interface is tested. Delete; don't preserve out of guilt.
- **The "what would slip through" test.** Don't propose adopting a layer unless you can name a concrete bug class it catches in *this* codebase.

### When to invoke `/bruhs:drill`

- Tests pass but bugs still ship — the suite isn't catching what it claims to catch
- Coverage is high but feels meaningless (no mutation kill ratio measured)
- ADRs exist but get violated; "clean architecture" decisions erode unenforced
- AI-generated test files are accumulating without review
- CI is green; the build still feels unreliable — likely an advisory orchestrator
- During `/bruhs:slop` you keep flagging "no test for X" — promote to `/bruhs:drill` for safety-net treatment

For full layer specs, diagnostics, gating posture, rejected framings → `practices/testing-infrastructure.md`

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

## Source as Ground Truth

> Code is the best ground truth over docs.

Whenever the work touches a third-party package, repo, or dependency, resolve its real behavior from the **installed source**, not from training memory or docs that may have drifted. Docs orient; the source decides. When they disagree, the version in the lockfile wins.

Use [`opensrc`](https://github.com/vercel-labs/opensrc) to pull a package's source on demand:

```bash
npm install -g opensrc
rg "parse" $(opensrc path zod)                    # search the real implementation
cat $(opensrc path zod)/src/types.ts              # read a specific file
find $(opensrc path pypi:requests) -name "*.py"   # non-npm via pypi: prefix
```

Reach for it before citing an API you're unsure of, when docs are thin or contradict behavior, when an error points into a dependency, or when a review finding hinges on what a library actually does. Reading source is not running it — execute untrusted / AI-generated code in a sandbox, never your host (see Config → stack `sandboxing`).

For full guidance (version-matching, context7-vs-source, fallbacks) → `practices/source-ground-truth.md`

---

## Command Details

Each command's full workflow lives in its own file. Read the specific file when executing that command:

| Command | File |
|---|---|
| cook   | `commands/cook.md` |
| yeet   | `commands/yeet.md` |
| peep   | `commands/peep.md` |
| dip    | `commands/dip.md` |
| spawn  | `commands/spawn.md` |
| claim  | `commands/claim.md` |
| slop   | `commands/slop.md` |
| doodle | `commands/doodle.md` |
| deepen | `commands/deepen.md` |
| drill  | `commands/drill.md` |

---

## Interactive Menu

When `/bruhs` is invoked without arguments, present the command list via `AskUserQuestion` and route to the selected command's file. Options: spawn, claim, cook, yeet, peep, doodle, dip, deepen, drill. `slop` is intentionally excluded from the menu — invoke directly with `/bruhs:slop`.

---

## Config Reference

Project state lives in two marker-bounded blocks inside `CLAUDE.md` **and** `AGENTS.md` (mirrored). The model reads them every session — no separate config file to keep in sync. Hand-written rules live outside the blocks and are never touched.

### Block 1 — `bruhs:state` (auto-maintained JSON)

```markdown
<!-- bruhs:state:begin v1 -->
<!-- AUTO-MAINTAINED BY /bruhs. Edits inside this block will be overwritten. -->

### Project State (managed by /bruhs)

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
    "structure": "single|monorepo",
    "framework": "nextjs|tanstack-start|astro|hono|...",
    "styling": ["tailwind", "shadcn"],
    "database": ["drizzle-postgres", "convex", "..."],
    "auth": "better-auth|clerk|...",
    "gpu": ["modal", "runpod", "lambda"]
  }
}
```
<!-- bruhs:state:end -->
```

### Block 2 — `bruhs:rules` (stack-derived behavioral rules)

```markdown
<!-- bruhs:rules:begin v1 -->
<!-- AUTO-MAINTAINED BY /bruhs. Stack-specific rules derived from detected stack. -->

### Stack-Specific Rules (managed by /bruhs)

#### Convex
- Convex actions that import the `ai` SDK MUST live in a file whose first line is `'use node'`.
- ...
<!-- bruhs:rules:end -->
```

Rules are derived from the detected stack via `scripts/derive_stack_rules.py` — short, high-signal, and **only** stack-specific. Universal behavioral rules (the kind that map to *your* failure modes) should be hand-written by you, outside the bruhs blocks.

### Scripts

| Script | Purpose |
|---|---|
| `scripts/sync_bruhs_block.py` | Atomically write a `bruhs:state` or `bruhs:rules` block into CLAUDE.md + AGENTS.md. |
| `scripts/read_bruhs_block.py` | Read the JSON state (or rules markdown) back out. Falls back to legacy `.claude/bruhs.json` for `--kind state` during the transition. |
| `scripts/derive_stack_rules.py` | Given state JSON on stdin, emit the markdown rules body to pipe into `sync_bruhs_block.py --kind rules`. |

### Migration from `.claude/bruhs.json`

Legacy `.claude/bruhs.json` is still read by `read_bruhs_block.py` as a fallback. `/bruhs:claim` detects the legacy file and offers to port it into the marker blocks, then prompts before deleting the old file.

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

Multi-workspace: Each project's `bruhs:state` block points to its Linear workspace via `mcpServer`.

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
