---
name: bruhs
description: Opinionated development lifecycle - spawn projects, cook features, yeet to ship
---

# bruhs

## Index
|commands|spawn,claim,cook,yeet,peep,dip,slop
|practices|type-driven-design,_common,typescript-react
|config|.claude/bruhs.json

## Commands Quick Reference
|spawn|Create project or add to monorepo|commands/spawn.md
|claim|Initialize config for existing project|commands/claim.md
|cook|Plan + Build feature end-to-end|commands/cook.md
|yeet|Ship: Linear ticket → Branch → Commit → PR|commands/yeet.md
|peep|Address PR review comments and merge|commands/peep.md
|dip|Clean up after merge, switch to base branch|commands/dip.md
|slop|Deep codebase analysis, AI slop cleanup|commands/slop.md

## Invocation
- `/bruhs` → Interactive menu (AskUserQuestion)
- `/bruhs <command>` → Direct to command
- `/bruhs cook <feature>` or `/bruhs cook TICKET-123` → With argument
- `/bruhs slop [path] [--fix|--report]` → Codebase analysis

---

## Type-Driven Design

> A function's type signature should tell you everything about what it does.

### Priority Hierarchy (fix in this order)
1. **Missing/wrong type signatures** - Types ARE documentation
2. **Hidden side effects** - Signature lies about behavior
3. **`any` types** - Type system disabled
4. **`!` or `as` on external data** - Compiler trust violated
5. **Implementation issues** - Secondary to type correctness

### Checklist
**Signatures:**
- [ ] Explicit return types on public functions
- [ ] No `any` - use `unknown` + validation
- [ ] No `!` - handle null explicitly
- [ ] No `as` for external data - validate instead
- [ ] Errors in return type, not thrown silently
- [ ] `readonly` parameters signal no mutation
- [ ] Discriminated unions for state (not multiple booleans)

**Errors:**
- [ ] Errors visible in return type (Result<T,E> or union)
- [ ] Typed errors, not strings
- [ ] Handle at call site, not deferred
- [ ] No empty catch blocks

**Immutability:**
- [ ] Prefer `const` over `let`
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

## Command Workflows

### cook - Plan + Build Feature
```
1. CONFIG: Check .claude/bruhs.json exists (offer /bruhs claim if not)
2. UNDERSTAND: Parse feature or fetch Linear ticket (TICKET-123 format)
3. EXPLORE: Load project skills from bruhs.json, find-skills for new ones, code-explorer agents
4. PLAN: Design 2-3 approaches → AskUserQuestion for selection
5. SETUP: Stash unrelated changes if needed (git stash push -m "bruhs: ...")
6. BUILD: TDD if test suite exists, else temp tests → cleanup after
7. REVIEW: code-reviewer agents, browser verification for UI
8. READY: "Run /bruhs yeet to ship" (ticket context in memory for yeet)
```
Detail → `commands/cook.md`

### yeet - Ship Code
```
1. CONFIG: Check bruhs.json (git-only mode if missing)
2. CHANGES: git status/diff - abort if none
3. ANALYZE: Categorize (feat/fix/chore/refactor), generate title + summary
4. LINEAR: Use ticketContext from cook OR create new ticket
   - Tool: mcp__<mcpServer>__linear_create_issue
   - Get branchName from issue.gitBranchName
5. BRANCH: git switch -c <branchName>
6. COMMIT: git add <files> && git commit (HEREDOC, "Fixes TICKET-ID")
7. PUSH: git push -u origin <branchName>
8. PR: gh pr create --title --body (Summary + Linear + Test plan)
9. STATUS: Update Linear → "In Review"
```
Detail → `commands/yeet.md`

### peep - Address PR Reviews
```
1. DETECT: Get PR from current branch, or arg (PR# or TICKET-ID)
2. FETCH: gh api repos/.../pulls/.../comments
3. CATEGORIZE: must-fix | suggestion | question
4. ADDRESS: Interactive per comment (apply/respond/skip)
5. COMMIT: Stage fixes, commit, push
6. RE-REVIEW: Request if needed
7. MERGE: When approved (squash/merge/rebase via AskUserQuestion)
8. TRANSITION: Auto-run dip workflow after merge
```
Detail → `commands/peep.md`

### dip - Post-Merge Cleanup
```
1. SWITCH: git switch <base-branch> (main/dev from config)
2. PULL: git pull
3. DELETE: git branch -d <feature-branch> && git push origin --delete
4. RESTORE: git stash pop (if cook stashed changes)
```
Detail → `commands/dip.md`

### spawn - Create Project
```
1. DETECT: Monorepo context (pnpm-workspace.yaml, turbo.json)
2. SELECT: Structure → Type → Language → Framework → Stack (AskUserQuestion flow)
3. SCAFFOLD: Official CLIs (pnpm create for TS projects)
4. LINEAR: Create project + initial tickets
5. GITHUB: Setup Actions with Blacksmith runner
6. CONFIG: Create .claude/bruhs.json
7. SKILLS: find-skills for relevant skills
```
Detail → `commands/spawn.md`

### claim - Initialize Existing Project
```
1. DETECT: Auto-detect stack from files (package.json, framework configs)
2. LINEAR: Configure team, project, labels (AskUserQuestion)
3. MCPS: Detect installed MCPs from ~/.claude.json
4. WRITE: Create .claude/bruhs.json
```
Detail → `commands/claim.md`

### slop - Codebase Analysis
```
Priority: Types(1) → Errors(2) → Immutability(3) → Security(4) → Architecture(5) → Performance(6) → Style(7)

1. CONTEXT: Load stack from bruhs.json
2. STATIC: Run tsc, security scan, dead code detection
3. ANALYZE: Each file against Type-Driven Design checklist
4. REPORT: Severity-ranked issues
5. FIX: Interactive (--fix for auto-fix safe issues)
6. VERIFY: tsc, lint, tests

Severity: relaxed | balanced | nitpicky (default) | brutal
```
Detail → `commands/slop.md`

---

## Interactive Menu

When `/bruhs` invoked without arguments:

```javascript
AskUserQuestion({
  questions: [{
    question: "What do you want to do?",
    header: "Command",
    multiSelect: false,
    options: [
      { label: "spawn", description: "Create new project or add to monorepo" },
      { label: "claim", description: "Claim existing project for bruhs" },
      { label: "cook", description: "Plan + Build a feature end-to-end" },
      { label: "yeet", description: "Ship: Linear ticket → Branch → Commit → PR" },
      { label: "peep", description: "Address PR review comments and merge" },
      { label: "dip", description: "Clean up after merge and switch to base branch" },
    ]
  }]
})
```

Note: `slop` excluded from menu (specialized tool - invoke directly with `/bruhs slop`)

After selection, execute the corresponding workflow above. Only read detail files for edge cases.

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
    "auth": "better-auth|clerk|..."
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
