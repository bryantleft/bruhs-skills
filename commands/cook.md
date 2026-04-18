---
description: Plan + Build a feature end-to-end
---

# cook - Plan + Build Features

Combined planning and building workflow. Wraps brainstorming and feature development patterns into a single end-to-end flow.

## Invocation

- `/bruhs:cook <feature>` - Start cooking a specific feature
- `/bruhs:cook <TICKET-ID>` - Fetch Linear ticket and start working on it (e.g., `PERDIX-123`)
- `/bruhs:cook` - Interactive mode, will ask what to build

## Best Practices

All code produced by cook follows the patterns defined in:

- **`practices/type-driven-design.md`** - **PRIMARY** - Type signatures, explicit errors, immutability
- **`practices/_common.md`** - Universal patterns (naming, git, errors, testing)
- **`practices/pr-review.md`** - PR authoring, reviewer etiquette, Conventional Comments (used by peep)
- **`practices/typescript-react.md`** - TypeScript + React (incl. TS 5.4+ patterns + Next.js 16 Cache Components)
- **`practices/typescript-hono.md`** - Hono framework (edge-native, RPC, type-safe middleware)
- **`practices/python.md`** - Modern Python 3.13+ (uv/ruff/ty, Pydantic v2, PEP 695 generics)
- **`practices/python-fastapi.md`** - FastAPI specifics (Annotated DI, async SQLAlchemy 2.0, error handling)
- **`practices/effect-ts.md`** - Effect-TS specific patterns (loaded when `effect` in `stack.libraries`)
- **`practices/rust.md`** - Idiomatic Rust patterns (loaded when `language: rust` or Rust framework in stack)
- **`practices/rust-references/`** - Deep refs (ownership, errors, async, type-state, leptos, gpui, axum) — loaded conditionally
- **`practices/ui-design.md`** - UI design quality via impeccable skills (loaded for UI features)

**Optional integrations** (auto-detected from MCPs available):

| MCP | Used for | Triggers |
|-----|----------|----------|
| `paper.design` | UI prototyping in real HTML/CSS — generate component shells before coding them | `featureInvolvesUI` AND `mcp__paper__*` tools available |
| `tldraw render` | Sketch proposed architecture before building | Complex/multi-module features (manual opt-in) |

**Key principles:**

| Principle | Description |
|-----------|-------------|
| **Types as Documentation** | Signatures should tell the full story |
| **Explicit Errors** | Errors visible in return types, not hidden throws |
| **Immutability** | Prefer readonly, don't mutate parameters |
| **Fast Path by Default** | When patterns are equivalent in correctness, pick the faster one. Anti-patterns (N+1, await-in-loop, sync-in-async, per-request clients) are bugs, not optimizations |
| **KISS** | Keep It Simple, Stupid |
| **YAGNI** | You Ain't Gonna Need It |
| **Single Source of Truth** | One authoritative source for each piece of data |
| **Atomic Design** | Hierarchical components: atoms → molecules → organisms |

**Before writing code, review the practices file for your stack.** The practices define:
- What patterns to follow (DO)
- What anti-patterns to avoid (DON'T)
- Quick reference checklists

**Type-first design (from type-driven-design.md):**
- **Explicit return types** on all public functions
- **Errors in return types** - not hidden throws
- **`readonly` parameters** - signal no mutation
- No **any**, **!**, or **as** for external data
- Union types for state machines (not multiple booleans)

For TypeScript + React, key highlights:
- Server Components by default (only `"use client"` when needed)
- Avoid useEffect for derived state, data fetching, event responses
- Const objects over enums

## Workflow

### Step 0: Check Config

```bash
ls .claude/bruhs.json 2>/dev/null
```

If config doesn't exist, use `AskUserQuestion`:

```javascript
AskUserQuestion({
  questions: [{
    question: "No bruhs.json found. Would you like to:",
    header: "Config",
    multiSelect: false,
    options: [
      { label: "Run /bruhs:claim (Recommended)", description: "Full setup with stack detection" },
      { label: "Continue without config", description: "Will skip Linear integration" },
    ]
  }]
})

If user chooses to continue without config:
- Skip Linear-related features
- Use sensible defaults for stack detection
- Remind user at end: "Run /bruhs:claim to enable full features"

### Step 1: Understand

Clarify what we're building:

**If input looks like a ticket ID** (e.g., `PERDIX-123`, `SON-456`):

```javascript
// Get Linear config from bruhs.json
config = readJson(".claude/bruhs.json")
linearConfig = config.integrations?.linear

if (!linearConfig?.mcpServer) {
  console.log("Linear not configured. Cannot fetch ticket.")
  // Fall back to treating input as feature description
} else {
  const mcpName = linearConfig.mcpServer    // e.g., "linear-sonner"

  // Load Linear MCP and fetch the ticket
  // Tool format: mcp__<server-name>__linear_<method>
  ToolSearch(`select:mcp__${mcpName}__linear_get_issue`)

  issue = call(`mcp__${mcpName}__linear_get_issue`, { id: ticketId })

  // Store ticket context for yeet
  ticketContext = {
    id: issue.id,
    identifier: issue.identifier,      // "SON-123"
    title: issue.title,
    description: issue.description,
    branchName: issue.gitBranchName,   // "son-123-add-feature"
  }

  // Output what we're working on
}
```

Output:
```
Working on Linear ticket...
✓ PERDIX-123: Add dark mode toggle

Description:
<ticket description from Linear>

Starting exploration...
```

**If input is a feature description:**

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

**Load practices based on stack:**

```javascript
// Load bruhs.json for stack info
config = readJson(".claude/bruhs.json")

// Load Effect practices if stack uses Effect
if (config.stack?.libraries?.includes('effect')) {
  effectPractices = Read('practices/effect-ts.md');
  console.log("✓ Loaded Effect-TS practices")
}

// Load UI design practices if feature involves visible UI changes
if (featureInvolvesUI) {
  uiPractices = Read('practices/ui-design.md');
  console.log("✓ Loaded UI design practices (impeccable skills)")
}
```

**Load project skills from bruhs.json:**

```javascript
// Load skills already configured for this project
projectSkills = config.tooling?.skills || []

// Load each configured skill
projectSkills.forEach(skill => Skill(skill))
```

```
Loading project skills...
✓ Loaded: shadcn
✓ Loaded: vercel-react-best-practices
```

**Search for additional skills needed for this feature:**

Based on the feature requirements, search for skills not already in bruhs.json:

```javascript
// Identify libraries/technologies involved in the feature
// Examples: stripe, resend, uploadthing, etc.

// Search for matching skills not already loaded
Skill("find-skills")

// Track newly discovered skills
newSkills = []
```

```
Checking for feature-specific skills...
✓ Found: stripe (not in project config)
```

**Persist newly discovered skills to bruhs.json:**

```javascript
if (newSkills.length > 0) {
  // Add to bruhs.json for future sessions
  config.tooling.skills = [...projectSkills, ...newSkills]
  writeJson(".claude/bruhs.json", config)
  console.log(`✓ Added ${newSkills.join(", ")} to bruhs.json`)
}
```

**Launch code-explorer agents to understand the codebase:**

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

Design 2-3 approaches based on exploration. First, output the approach details:

```
Planning...

**Approach 1: <name>**
- Description: <how it works>
- Files to modify: <list>
- Data path: <where data flows — any N+1, waterfall, or fan-out hotspots?>
- Performance notes: <which fast-path patterns apply; any hot-path concerns>
- Pros: <benefits>
- Cons: <tradeoffs>

**Approach 2: <name>**
- Description: <how it works>
- Files to modify: <list>
- Data path: <where data flows — any N+1, waterfall, or fan-out hotspots?>
- Performance notes: <which fast-path patterns apply; any hot-path concerns>
- Pros: <benefits>
- Cons: <tradeoffs>
```

**Performance checklist during planning** (don't ship an approach that fails these):
- [ ] No `await` in loops over independent work — use `Promise.all` / `asyncio.gather` / `try_join!`
- [ ] No N+1 ORM access — plan eager loading up front
- [ ] Concurrency bounded when driven by user input
- [ ] Clients (DB, HTTP, Redis) reused, not constructed per request
- [ ] Streaming vs buffering decided for large payloads
- [ ] Sync I/O / crypto kept off the event loop
- [ ] Cache layer identified (edge cache, app cache, none) with justification

Then use `AskUserQuestion` for selection:

```javascript
AskUserQuestion({
  questions: [{
    question: "Which approach do you want to use?",
    header: "Approach",
    multiSelect: false,
    options: [
      { label: "Approach 1: <name>", description: "<key benefit>" },
      { label: "Approach 2: <name>", description: "<key benefit>" },
      // Add Approach 3 if applicable
    ]
  }]
})

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

First, check if project has a test suite:
```bash
# Look for test config files
ls vitest.config.* jest.config.* pytest.ini 2>/dev/null
# Check for test directories
ls -d __tests__ tests test spec 2>/dev/null
```

**If test suite exists:**
1. Write failing test (will be kept)
2. Implement minimum code to pass
3. Refactor
4. Repeat

```
testSuiteExists = true
```

**If no test suite:**
1. Create temporary test file to verify logic
2. Implement minimum code to pass
3. Verify tests pass
4. Delete temporary test file when done

```
testSuiteExists = false
tempTestFiles = ["<path-to-temp-test>"]
```

Cleanup at end of Step 6:
```javascript
if (!testSuiteExists && tempTestFiles.length > 0) {
  // Remove temporary test files
  tempTestFiles.forEach(f => rm(f))
  console.log("✓ Cleaned up temporary test files")
}
```

**For UI/non-testable code:**

**If UI design practices are loaded**, invoke impeccable skills during build.
See `practices/ui-design.md` for the full skill map and selection heuristic.

```javascript
// 0. (Optional) Prototype in paper.design before coding — if MCP available
//    Use this for genuinely new UI surfaces, not for tweaks to existing components.
const paperAvailable = ToolSearch("select:mcp__paper__create_artboard");
if (paperAvailable && featureIsNewUiSurface) {
  AskUserQuestion: "Prototype this UI in paper.design first? (generates HTML/CSS shell to iterate on visually before bringing into the codebase)"
  if (yes) {
    // Create artboard, get_jsx, screenshot for review
    mcp__paper__create_artboard({ name: featureName });
    mcp__paper__write_html({ html: initialMarkup });
    const screenshot = mcp__paper__get_screenshot();
    // Show screenshot, iterate. Once approved:
    const jsx = mcp__paper__get_jsx();
    // Hand jsx to frontend-design skill as the starting structure
  }
}

// 1. Check for design context (one-time project setup)
if (!CLAUDE_MD.includes('## Design Context')) {
  AskUserQuestion: "No Design Context in CLAUDE.md. Run /teach-impeccable?"
  if (yes) Skill("teach-impeccable")
}

// 2. Foundation — always load first (other skills depend on it)
Skill("frontend-design")

// 3. Primary build skills
if (hasDesignSystem) Skill("normalize")     // match existing tokens/patterns
if (buildingOnboarding) Skill("onboard")    // empty states, first-time UX
if (needsMotion) Skill("animate")           // entrances, micro-interactions
if (multiDevice) Skill("adapt")             // responsive, touch targets
if (hasUserFacingCopy) Skill("clarify")     // labels, errors, CTAs

// 4. Adjustment skills — only if result needs tuning
// Skill("bolder")    // design too safe/generic
// Skill("quieter")   // design too aggressive/noisy
// Skill("colorize")  // design too monochromatic
// Skill("delight")   // design too dry/functional
// Skill("distill")   // design too complex/cluttered
```

First, check if dev server is running (for UI changes):

```javascript
// 1. Detect the dev command and port from package.json
//    - Read package.json (or app's package.json in monorepo)
//    - Parse "dev" script for port flags (--port, -p, etc.)
//    - Check for framework config files (next.config.js, vite.config.ts)
//    - Default ports: Next.js (3000), Vite (5173), etc.

// 2. Check if that port is in use
```

```bash
# Check if detected port is in use
lsof -i :<detected-port> | grep LISTEN
```

If not running, use `AskUserQuestion`:

```javascript
AskUserQuestion({
  questions: [{
    question: "Dev server not running. Would you like to start it?",
    header: "Dev server",
    multiSelect: false,
    options: [
      { label: "Yes", description: "Start dev server in background" },
      { label: "No", description: "Continue without dev server" },
    ]
  }]
})

If yes, start in background using the project's dev command:
```bash
# For monorepo, run from the correct workspace
pnpm --filter <app-name> dev &

# For single project
pnpm dev &
```

Track that we started it:
```
devServerStartedByUs = true
devServerPid = <pid>
```

Then:
1. Implement component/feature
2. Verify in browser (see Step 6)
3. Refactor

**For training/fine-tuning tasks (RunPod, Lambda, Modal):**

When the feature involves training or fine-tuning a custom model, create and maintain a `learnings.md` at the project or app root to document all iterations:

```javascript
// Detect if this is a training task
isTrainingTask = featureDescription.match(/train|fine-?tune|finetune|lora|rlhf|dpo|sft|checkpoint/)
  || config.stack?.gpu?.some(g => ["runpod", "lambda"].includes(g))

if (isTrainingTask) {
  // Create learnings.md if it doesn't exist
  if (!exists("learnings.md")) {
    Write("learnings.md", `# Training Learnings\n\nDocuments iterations, hyperparameters, results, and insights across training runs.\n\n---\n`)
  }
}
```

**After each training run or significant iteration**, append to `learnings.md`:

```markdown
## Run <N> — <date> — <short description>

**Config:** <model, dataset, hyperparams>
**Result:** <metrics — loss, accuracy, eval scores>
**What worked:** <insights>
**What didn't:** <failures, unexpected behavior>
**Next:** <what to try next based on this run>
```

This file persists across sessions so future training work can reference past iterations without re-discovering what was already tried.

Use feature-dev patterns:
- Follow existing code conventions
- Apply atomic design for components
- Maintain single source of truth
- Keep functions pure where possible
- **Follow any skills loaded in Step 2** (shadcn, ai-sdk, etc.)

**Progress output:**
```
Building...
✓ Dev server running on :<detected-port>
✓ Created <file>
✓ Modified <file>
✓ Added tests for <feature>        # kept if test suite exists
✓ All tests passing
```

Or for projects without test suite:
```
Building...
✓ Created <file>
✓ Modified <file>
✓ Created temporary tests to verify logic
✓ All tests passing
✓ Cleaned up temporary test files   # after Step 6
```

### Step 6: Review

**Code Review:**

Launch code-reviewer agents to check the implementation:

Use the Task tool with `subagent_type: "feature-dev:code-reviewer"` to:
- Check for bugs
- Verify logic
- Look for security issues
- Ensure code quality
- Check adherence to project conventions
- **Fast-path audit**: scan for N+1 queries, `await` in loops, sync-in-async, per-request client construction, unbounded concurrency on user input, fetch waterfalls, unstable references passed to memoized children, defensive `useMemo`, full-body logging in hot paths

```
Reviewing code...
✓ No high-confidence issues found
✓ Fast-path audit: no anti-patterns detected
```

**UI Design Review (for UI changes):**

If UI design practices are loaded, run design review before visual verification.
See `practices/ui-design.md` for the full skill map.

```javascript
// 1. Diagnose — these produce reports, not code changes
Skill("critique")    // design director evaluation: hierarchy, IA, AI slop, emotion
Skill("audit")       // systematic scan: a11y, perf, theming, responsive, anti-patterns

// 2. Fix — based on what critique/audit found
Skill("polish")      // always: alignment, spacing, states, transitions, code cleanup
if (edgeCasesFound) Skill("harden")    // i18n, overflow, error handling, edge cases
if (perfIssuesFound) Skill("optimize") // CWV, images, bundle, rendering, animations

// 3. Post-build (optional)
if (reusablePatternsEmerged) Skill("extract") // pull into design system
```

Fix all issues found before proceeding to visual verification.

**Visual Verification (for UI changes):**

If the feature includes UI changes, use the browser agent to verify:

```javascript
// Invoke the agent-browser skill for visual verification
Skill("agent-browser")

// The browser agent will:
// - Navigate to the relevant page
// - Verify the UI renders correctly
// - Check for visual regressions
// - Test basic interactions
```

```
Verifying in browser...
✓ Page loads without errors
✓ Component renders correctly
✓ Interactions work as expected
```

**If issues found:**
```
Reviewing...
⚠ Found issues:
  - <issue 1>
  - <issue 2>

Fixing...
✓ Fixed <issue 1>
✓ Fixed <issue 2>
```

**Cleanup:**

```javascript
// Kill dev server only if we started it
if (devServerStartedByUs) {
  kill(devServerPid)
  console.log("✓ Stopped dev server")
}

// Remove temporary test files only if no test suite existed
if (!testSuiteExists && tempTestFiles.length > 0) {
  tempTestFiles.forEach(f => rm(f))
  console.log("✓ Cleaned up temporary test files")
}
```

### Step 7: Ready to Ship

Signal completion and prompt for shipping:

**If started from a Linear ticket:**
```
Ready to ship! Run /bruhs:yeet to create PR.
📋 Using existing ticket: PERDIX-123
```

**If started from feature description:**
```
Ready to ship! Run /bruhs:yeet to create ticket and PR.
```

If we stashed changes:
```
💡 You have stashed changes from before this feature (git stash pop to restore)
```

**Important:** The ticket context is stored in conversation memory. When yeet runs in the same session, it will have access to `ticketContext` from Step 1 and skip ticket creation.

If the user starts a new conversation before running yeet, the context is lost and yeet will create a new ticket as normal.

## Examples

### From Feature Description

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

### From Linear Ticket

```
> /bruhs:cook PERDIX-145

Working on Linear ticket...
✓ PERDIX-145: Add dark mode toggle to settings page

Description:
Users should be able to toggle between light and dark mode from the settings.
Acceptance criteria:
- Toggle in settings page
- Persists preference to localStorage
- Respects system preference by default

Exploring codebase...
- Found: app/settings/page.tsx (settings page)
- Found: components/ui/switch.tsx (toggle component)
- Found: lib/hooks/use-theme.ts (existing theme hook)
- Pattern: Zustand for client state, localStorage for persistence

Planning...

**Approach 1: Extend existing useTheme hook**
- Add toggle to settings page using existing hook
- Files: app/settings/page.tsx, lib/hooks/use-theme.ts
- Pros: Minimal changes, uses existing infrastructure
- Cons: None significant

Which approach? [1]

> 1

Building...
✓ Modified lib/hooks/use-theme.ts (added system preference detection)
✓ Modified app/settings/page.tsx (added theme toggle)
✓ All manual verification passed

Reviewing...
✓ No high-confidence issues found

Ready to ship! Run /bruhs:yeet to create PR.
📋 Using existing ticket: PERDIX-145
```

## Integration with Other Skills

| Phase | Pattern Source |
|-------|----------------|
| Plan | `superpowers:brainstorming` patterns |
| Build | `feature-dev:feature-dev` patterns |
| Build (UI) | `practices/ui-design.md` — impeccable skills (`frontend-design`, `normalize`, `onboard`, `animate`, `adapt`, `clarify`, + adjustment skills) |
| Review | `superpowers:requesting-code-review` patterns |
| Review (UI) | `practices/ui-design.md` — diagnostic (`critique`, `audit`) then fix (`polish`, `harden`, `optimize`, `extract`) |

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
