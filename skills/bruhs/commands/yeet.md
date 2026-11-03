---
description: Ship staged work — categorize the diff, create or reuse a Linear ticket, checkout a branch, commit, push, open a PR via gh, update Linear to In Review. Use when ready to ship changes, open a PR, or turn a WIP into a ticketed branch.
---

# yeet - Ship Workflow

> `<SKILL_DIR>` is the bruhs skill directory: the folder that holds `SKILL.md`, one level above this file's `commands/` folder.

Ship code that's ready to go. Creates Linear ticket, commits, pushes, and opens PR.

## Contents

- [Invocation](#invocation)
- [Best Practices](#best-practices)
- [Prerequisites](#prerequisites)
- [Workflow](#workflow)
- [Configuration](#configuration)
- [Git-Only Mode](#git-only-mode)
- [Examples](#examples)
- [Git Best Practices](#git-best-practices)
- [Stacked PRs](#stacked-prs)
- [Tree-Identity Guard](#tree-identity-guard)
- [Tips](#tips)

---

## Invocation

- `/bruhs:yeet` - Ship current changes
- `/bruhs:yeet` after `/bruhs:cook` - Complete the cooking workflow (uses existing ticket if cook started from one)

## Best Practices

PR description + commit + reviewer-assignment quality is governed by **`practices/pr-review.md`**. Key applications in this command:

- **Conventional Commits — always.** Every commit message and the PR title MUST follow the [Conventional Commits](https://www.conventionalcommits.org/) spec (`feat(scope):`, `fix(scope):`, `chore:`, …) per `practices/_common.md`. This is not optional and has no "quick commit" escape hatch — a non-conventional message is a bug in the ship, not a style preference.
- **PR body and ticket text:** shape and AI-tell scan per **`practices/writing.md`** (sentence case, point first, behavior not diff narration)
- **PR title:** Conventional Commits format (`feat(scope):`, `fix(scope):`, etc.) — see `_common.md`
- **UI preview — always for UI changes.** When the diff touches user-visible surface, verify it with `/expect` and capture screenshots + a screen recording, then embed them as a `## UI preview` section in the PR body. Full procedure: **`practices/ui-preview.md`**. A UI PR with no verified preview is incomplete.
- **PR body shape:** point first, behavior bullets, Decisions, Review focus, collapsed Background, Testing (Ran / Mutation-checked / Not tested), and Risks with watch signals, inside the repo's PR template when one exists (Step 8)
- **Size discipline:** if the diff is > 400 LOC, warn the user and suggest splitting into a [stack](#stacked-prs) (or accept with a justification noted in the PR body)
- **CODEOWNERS:** if `.github/CODEOWNERS` exists, GitHub auto-requests reviewers; don't manually re-request
- **Diagram:** for non-trivial architectural changes, suggest `/bruhs:doodle pr` after the PR opens to attach a visualization comment
- **Walkthrough:** for ≥ 10-file PRs or anything with significant moved code, suggest `/bruhs:walk --post` after the PR opens to drop a reviewer-friendly walkthrough comment
- **Core vs mechanical separation:** when the diff mixes hand-written changes with lockfile/generated/formatting churn, list core files first in the PR body and collapse mechanical files in a `<details>` block (see [Reviewer-Friendly PR Body](#reviewer-friendly-pr-body))
- **History rewriting (only when asked):** if the user requests a history rewrite before pushing (squash, reorder, fixup), follow the [Tree-Identity Guard](#tree-identity-guard) so the rewritten tree provably matches the original

## Prerequisites

- Changes ready to commit (staged or unstaged)
- GitHub CLI (`gh`) authenticated
- Linear MCP configured (optional, will work without)

## Workflow

### Step 0: Check Config

```bash
# Try the new marker-block first, falling back to legacy bruhs.json
CONFIG_JSON=$(python3 <SKILL_DIR>/scripts/read_bruhs_block.py --kind state --root . 2>/dev/null)
```

If no config found (empty `CONFIG_JSON`), use `AskUserQuestion`:

```javascript
AskUserQuestion({
  questions: [{
    question: "No bruhs config found in CLAUDE.md (or legacy bruhs.json). Would you like to:",
    header: "Config",
    multiSelect: false,
    options: [
      { label: "Run /bruhs:claim (Recommended)", description: "Full setup with Linear integration" },
      { label: "Continue in git-only mode", description: "Commit and PR without Linear tickets" },
    ]
  }]
})

If user chooses git-only mode:
- Skip all Linear steps (ticket creation, status updates)
- Generate branch names from change type: `<type>/<short-description>`
- Commit without ticket reference
- Remind user at end: "Run /bruhs:claim to enable Linear integration"

### Step 1: Check for Changes

```bash
git status
git diff --stat
git diff --cached --stat
```

If no changes:
```
No changes to ship. Make some changes first!
```

### Step 2: Analyze Changes

Understand what changed to generate good descriptions:

```bash
git diff
git diff --cached
```

Categorize the change type:
- `feat` - New feature
- `fix` - Bug fix
- `chore` - Maintenance/config
- `refactor` - Code improvement
- `docs` - Documentation
- `test` - Test additions/changes

Generate:
- **Title**: Short description (under 70 chars)
- **Summary**: What changed and why

**Schema split check.** If the diff touches migrations or a generated schema (`migrations/`, `db/migrate/`, `prisma/migrations/`, `drizzle/`, `alembic/versions/`, `schema.prisma`, a schema snapshot) **and** any application code, stop: every schema change ships in its own PR (migration files plus the generated schema, nothing else), merged before the code that uses it. No size exception. Offer to split: the schema PR first, then the code PR on top (a [stack](#stacked-prs) while both are open).

### Step 3: Check Linear MCP

```javascript
// Read Linear config from bruhs:state (CLAUDE.md > AGENTS.md > legacy bruhs.json)
config = JSON.parse(Bash(`python3 <SKILL_DIR>/scripts/read_bruhs_block.py --kind state --root .`))
linearConfig = config.integrations?.linear

if (!linearConfig?.mcpServer) {
  console.log("Linear not configured in bruhs:state.")
  linearAvailable = false
} else {
  // Tool format: mcp__<mcpServer>__linear_<method>
  const mcpName = linearConfig.mcpServer    // e.g., "linear-sonner"

  try {
    // Load the tools for this workspace
    ToolSearch(`select:mcp__${mcpName}__linear_get_teams`)
    call(`mcp__${mcpName}__linear_get_teams`)
    linearAvailable = true
  } catch {
    console.log("Linear MCP not connected.")

    // Ask user with AskUserQuestion
    AskUserQuestion({
      questions: [{
        question: "Linear MCP not connected. Continue without Linear?",
        header: "Linear",
        multiSelect: false,
        options: [
          { label: "Yes, git-only mode", description: "Commit and PR without Linear tickets" },
          { label: "No, abort", description: "Stop and configure Linear first" },
        ]
      }]
    })
  }
}
```

### Step 4: Get or Create Linear Ticket (if available)

**First, check if ticket context exists from cook:**

The ticket context lives in conversation memory - if cook ran earlier in the same session with a ticket ID, that context is available here.

```javascript
// If cook passed ticket context (started from a ticket ID), use it
if (ticketContext) {
  console.log("Using existing ticket from cook...")
  branchName = ticketContext.branchName   // "perdix-145-add-dark-mode-toggle"
  ticketId = ticketContext.identifier     // "PERDIX-145"
  issueId = ticketContext.id              // UUID for API calls

  // Skip ticket creation
  return
}

// Note: If user started a new conversation after cook, context is lost
// and we'll create a new ticket below (which is fine)
```

**If no existing ticket, create one:**

```javascript
// Use the Linear config already loaded from bruhs:state
const mcpName = linearConfig.mcpServer    // e.g., "linear-sonner"

// Load Linear tools
ToolSearch(`select:mcp__${mcpName}__linear_create_issue`)
ToolSearch(`select:mcp__${mcpName}__linear_get_teams`)
ToolSearch(`select:mcp__${mcpName}__linear_get_user`)

// Get current user ID for assignment
const user = call(`mcp__${mcpName}__linear_get_user`)
const assigneeId = user.viewer.id

// Get the label name from config (e.g., "feat" -> "Feature", "chore" -> "Chore")
const labelName = linearConfig.labels[changeType]

// Get team labels to find the matching label ID
const teamsData = call(`mcp__${mcpName}__linear_get_teams`)
const team = teamsData.teams.nodes.find(t => t.id === linearConfig.team)
const label = team?.labels?.nodes?.find(l => l.name.toLowerCase() === labelName?.toLowerCase())
const labelIds = label ? [label.id] : []

// Create issue with project, assignee, and labels
issue = call(`mcp__${mcpName}__linear_create_issue`, {
  title: generatedTitle,
  teamId: linearConfig.team,
  projectId: linearConfig.project,
  assigneeId: assigneeId,
  labelIds: labelIds
})

// Capture the branch name Linear generates
branchName = issue.gitBranchName  // e.g., "sonner-140-improve-toast-animation"
ticketId = issue.identifier  // e.g., "SON-140"
issueId = issue.id
```

### Step 5: Create Branch

Use modern git commands for branch operations:

```bash
git switch -c <branchName>
```

Example:
```bash
git switch -c perdix-140-improve-game-state-validation
```

If Linear not available, generate branch name:
```bash
# Format: <type>/<short-description>
git switch -c feat/add-leaderboard
```

### Step 5.5: Validate Before Shipping

Before committing, run the project's verification suite. Broken code must not end up in a Linear ticket or PR.

```bash
bash scripts/validate_pr_ready.sh
```

`scripts/validate_pr_ready.sh` lives at the plugin's scripts directory and runs the project's typecheck + lint + tests in one shot.

**Fallback if `scripts/validate_pr_ready.sh` is not present** — auto-detect the toolchain and run the equivalents inline:

- **Node / TypeScript**: `npm run typecheck` (or `tsc --noEmit`), `npm run lint`, `npm test` — substitute `pnpm` / `yarn` / `bun` per the project's lockfile.
- **Rust**: `cargo check`, `cargo clippy -- -D warnings`, `cargo test`.
- **Python**: `ruff check .`, `mypy .` (or `ty check` / `pyright`), `pytest`.
- **Go**: `go vet ./...`, `go test ./...`.

**Interpret the output:**

- **All passed** → continue to Step 6 silently.
- **Anything failed** → STOP. Do not commit. Use `AskUserQuestion`:

```javascript
AskUserQuestion({
  questions: [{
    question: "Validation failed. How do you want to proceed?",
    header: "Validation",
    multiSelect: false,
    options: [
      { label: "Show me the failure output", description: "Print the failing typecheck/lint/test output" },
      { label: "Fix the issue now", description: "Pause here — iterate on the fix, then re-run validation" },
      { label: "Ship anyway (not recommended)", description: "Proceed with commit + PR; unvalidated areas will be flagged in the PR body" },
      { label: "Abort", description: "Stop the ship workflow entirely" },
    ]
  }]
})
```

**Rules:**

- Never pass `--no-verify` to `git commit` or `git push` to bypass hooks.
- Never skip this step unless the user explicitly chose "Ship anyway (not recommended)".
- If the user chose "Ship anyway", name the failing checks and unvalidated areas on the PR body's **Not tested** line in Step 8, e.g. `**Not tested:** typecheck fails in <file>; shipped anyway at the author's request`.

### Step 6: Stage and Commit

Stage changes:
```bash
# Stage specific files (preferred)
git add <file1> <file2> ...

# Or stage all if appropriate
git add -A
```

Commit with ticket reference and an `Assisted-by:` trailer (see `practices/_common.md` → *AI attribution*):
```bash
git commit -m "$(cat <<'EOF'
<type>: <description>

Fixes <TICKET-ID>

Assisted-by: <Agent>:<model-id>
EOF
)"
```

Example:
```bash
git commit -m "$(cat <<'EOF'
feat: add leaderboard to game page

Fixes PERDIX-140

Assisted-by: Claude:claude-opus-5-5
EOF
)"
```

Without Linear:
```bash
git commit -m "$(cat <<'EOF'
feat: add leaderboard to game page

Assisted-by: Claude:claude-opus-5-5
EOF
)"
```

### Step 7: Push

```bash
git push -u origin <branchName>
```

### Step 7.5: UI Verification & Preview Capture (UI changes only)

If the diff touches user-visible surface (components, pages, routes, styles, templates, emails), produce a verified UI preview **before** writing the PR body. Follow **`practices/ui-preview.md`** in full:

1. **Verify with `/expect`** — adversarial browser tests via the chrome-devtools MCP. Fix any breakage and re-run before capturing. Never capture an unverified UI.
2. **Capture** screenshots (desktop 1280×800 + mobile 390×844; before/after when modifying existing UI) and a short **screen recording** that shows the changed interaction — via chrome-devtools MCP, or the project's Playwright (`recordVideo` + `page.screenshot`) as a fallback.
3. **Host** the media (auto-push to the `bruhs-assets` branch for inline images; drag-drop the recording for an inline player — see the practice for the honest hosting limits).
4. Carry the resulting markdown into the `## UI preview` section in Step 8.

If the diff has no UI surface, skip this step. Detect quickly:

```bash
git diff --name-only origin/<base>...HEAD | grep -Eiq '\.(tsx|jsx|vue|svelte|css|scss|html|astro)$' && echo "UI diff: run Step 7.5" || echo "no UI surface: skip"
```

### Step 8: Create PR

Two readers: a reviewer skimming to decide where to look, and an agent (`/bruhs:peep`, a bot reviewer, someone running `git blame` in two years) checking each claim against the diff. Both want the point first, claims as checkable behavior, and judgment calls in one known place. Fewest words that keep the meaning; never a walkthrough of the diff. Scale to risk: a typo fix gets one sentence.

**Repo template first.** If a `pull_request_template.md` exists (`.github/`, `docs/`, or the root), fill its headings in order and put the shape below inside them as bold lead-in labels. Never add, rename, or reorder template headings. Tick only checklist boxes you actually satisfied. With no template, use these headings:

```bash
gh pr create --title "<type(scope): description>" --body "$(cat <<'EOF'
## Summary

<1–2 sentences: what changes after merge, and why>

- <change, as behavior checkable against the diff>

<optional mermaid diagram or table, when it replaces prose>

**Decisions**
- <deviation from the ticket/design, or a call that looks like a bug: one-line reason>

**Review focus:** <where a bug would hide>

<details><summary>Background</summary>

<history, alternatives, citations, platform mechanics>

</details>

<!-- UI changes only: produced by Step 7.5 / practices/ui-preview.md -->
## UI preview
Verified with `/expect` (chrome-devtools): <1-line result>.
<before/after screenshots with captions, plus a screen recording of the changed interaction>

## Linear
<TICKET-ID>

## Testing

**Ran:** <what ran, what it proved>
**Mutation-checked:** <guard removed, test failed; or `none`>
**Not tested:** <what never hit the real dependency>

## Risks

- <risk>. Watch: <metric, log query, or error-tracker item>
EOF
)"
```

**Rules for each part:**

- **First sentence is the PR.** Mechanics and history go in `<details>` or nowhere.
- **Behavior, not methods.** Name code only to locate it or state an invariant (unique key, query count).
- **The summary's lead depends on the type.** Feature: the capability and who gets it. Fix: the broken behavior, then the root cause in one sentence (how it was found goes in Background). Refactor/chore: why now, with proof of no behavior change under Testing.
- **Decisions** holds every deviation and every intentional oddity. Omit the label if empty; never bury one mid-paragraph.
- **Review focus:** omit on trivial diffs. On 5+ file PRs it also names where to start reading (see [Reviewer-Friendly PR Body](#reviewer-friendly-pr-body)).
- **Diagram when it beats prose.** Branching logic, a flow across systems, or a state change → a small mermaid block. A case matrix (input → outcome) → a table. Under ~10 nodes, and drop the prose it replaces. Render it before posting (`npx -y -p @mermaid-js/mermaid-cli mmdc -i d.mmd -o /tmp/d.png`, then look at the PNG); quote labels containing `'`, `,` or `()`.
- **Testing, never Risks, holds what you verified.** `Not tested` is always filled. Mutation-checked means you removed the guard and watched the test fail; `none` is an honest answer.
- **Every risk has a watch signal**, or it isn't a risk entry. "No risks" is almost never true.
- **UI preview**: required for any UI change, and *verified*: run `/expect` first, then embed screenshots **and** a screen recording, each with a caption ("Before: button overflows on mobile. After: wraps."). A bare screenshot of an unverified or static screen does not satisfy this.
- **Sentence case throughout**, labels included (`practices/writing.md`).

**Read-back gate before `gh pr create` / `gh pr edit`:** give only the body to a fresh subagent and ask what changes, what's riskiest, what deviates from the ticket, and which terms it couldn't define from the body alone. Wrong or "can't tell" means fix the body. The subagent has no team context, so it over-flags: define a term only if a reviewer from another team wouldn't know it. Then cut every word that doesn't change those answers.

**Example (fix PR, no repo template):**

```bash
gh pr create --title "fix(engine): reshuffle the discard pile when the deck runs out" --body "$(cat <<'EOF'
## Summary

Games past 40 turns no longer crash: drawing from an empty deck now reshuffles the discard pile into a new deck. `drawCard()` popped without checking deck size, so the empty array returned `undefined` and `evaluateHand()` threw.

- Drawing from an empty deck reshuffles the discard pile, then draws
- Drawing with both deck and discard empty throws `DeckExhaustedError` instead of returning `undefined`

**Decisions**
- Reshuffle instead of ending the game, because it matches standard rules and the ticket's repro

**Review focus:** the reshuffle must not include cards currently in players' hands.

## Linear
PERDIX-142

## Testing

**Ran:** unit tests for empty-deck and both-empty draws; a scripted 120-turn game completes.
**Mutation-checked:** removed the size check and the empty-deck test failed.
**Not tested:** concurrent draws in multiplayer rooms.

## Risks

- Reshuffling changes card order mid-game in long games. Watch: `game_error` events with `stage=evaluate` in the error tracker.
EOF
)"
```

### Step 9: Update Linear Status (if available)

```javascript
// Load and call edit_issue
ToolSearch(`select:mcp__${mcpName}__linear_edit_issue`)

call(`mcp__${mcpName}__linear_edit_issue`, {
  issueId: issue.id,
  stateId: "in-review"  // Or find the "In Review" state ID
})
```

### Step 10: Output Summary

**If created new ticket:**
```
Analyzing changes...
- 3 files modified in components/game/

Creating Linear ticket...
✓ PERDIX-140: Add leaderboard to game page

Switching to branch...
✓ perdix-140-add-leaderboard-to-game-page

Committing...
✓ feat: add leaderboard to game page (Fixes PERDIX-140)

Pushing & creating PR...
✓ PR #42: https://github.com/org/repo/pull/42

Updating Linear...
✓ PERDIX-140 → In Review

Done! 🚀

When you get review feedback, run /bruhs:peep to address comments.
```

**If using existing ticket (from cook):**
```
Analyzing changes...
- 2 files modified in app/settings/, lib/hooks/

Using existing ticket...
✓ PERDIX-145: Add dark mode toggle to settings page

Switching to branch...
✓ perdix-145-add-dark-mode-toggle-to-settings-page

Committing...
✓ feat: add dark mode toggle to settings page (Fixes PERDIX-145)

Pushing & creating PR...
✓ PR #45: https://github.com/org/repo/pull/45

Updating Linear...
✓ PERDIX-145 → In Review

Done! 🚀

When you get review feedback, run /bruhs:peep to address comments.
```

## Configuration

Reads the `bruhs:state` block in `CLAUDE.md` (fallback `AGENTS.md`, then legacy `.claude/bruhs.json`):

```json
{
  "integrations": {
    "linear": {
      "mcpServer": "linear-sonner",     // MCP server name from ~/.claude.json
      "team": "<team-id>",
      "teamName": "Sonner",
      "project": "<project-id>",
      "projectName": "Sonner Core",
      "labels": {
        "feat": "Feature",
        "fix": "Bug",
        "chore": "Chore",
        "refactor": "Improvement"
      }
    }
  }
}
```

The `labels` map commit types to Linear label names.

**Multi-workspace setup:** Each project's `bruhs:state` block points to its specific Linear workspace via `mcpServer`. Tool names are always `mcp__<mcpServer>__linear_<method>` (e.g., `mcp__linear-sonner__linear_create_issue`).

## Git-Only Mode

If Linear MCP not available, yeet still works:

1. ~~Create Linear ticket~~ (skipped)
2. Generate branch name from change type + description
3. Stage and commit (without ticket reference)
4. Push and create PR
5. ~~Update Linear~~ (skipped)

Output:
```
Analyzing changes...
- 3 files modified in components/game/

⚠ Linear not configured (git-only mode)

Switching to branch...
✓ feat/add-leaderboard

Committing...
✓ feat: add leaderboard to game page

Pushing & creating PR...
✓ PR #42: https://github.com/org/repo/pull/42

Done! 🚀

When you get review feedback, run /bruhs:peep to address comments.
```

## Examples

### After /bruhs:cook (from feature description)

```
> /bruhs:yeet

Analyzing changes...
- 2 files created
- 1 file modified
- Type: feat (new feature)

Creating Linear ticket...
✓ PERDIX-141: Add dark mode toggle

Switching to branch...
✓ perdix-141-add-dark-mode-toggle

Committing...
✓ feat: add dark mode toggle (Fixes PERDIX-141)

Pushing & creating PR...
✓ PR #43: https://github.com/perdixlabs/gambit/pull/43

Updating Linear...
✓ PERDIX-141 → In Review

Done! 🚀

When you get review feedback, run /bruhs:peep to address comments.
```

### After /bruhs:cook PERDIX-145 (from ticket)

```
> /bruhs:yeet

Analyzing changes...
- 2 files modified
- Type: feat (new feature)

Using existing ticket...
✓ PERDIX-145: Add dark mode toggle to settings page

Switching to branch...
✓ perdix-145-add-dark-mode-toggle-to-settings-page

Committing...
✓ feat: add dark mode toggle to settings page (Fixes PERDIX-145)

Pushing & creating PR...
✓ PR #46: https://github.com/perdixlabs/gambit/pull/46

Updating Linear...
✓ PERDIX-145 → In Review

Done! 🚀

When you get review feedback, run /bruhs:peep to address comments.
```

### Bug Fix

```
> /bruhs:yeet

Analyzing changes...
- 1 file modified in lib/engine/
- Type: fix (bug fix)

Creating Linear ticket...
✓ PERDIX-142: Fix card draw validation

Switching to branch...
✓ perdix-142-fix-card-draw-validation

Committing...
✓ fix: validate card draw against deck state (Fixes PERDIX-142)

Pushing & creating PR...
✓ PR #44: https://github.com/perdixlabs/gambit/pull/44

Updating Linear...
✓ PERDIX-142 → In Review

Done! 🚀

When you get review feedback, run /bruhs:peep to address comments.
```

### Multiple Changes (Interactive)

If changes span multiple logical units, use `AskUserQuestion`:

```
> /bruhs:yeet

Analyzing changes...
- 5 files modified
- Changes appear to span multiple features
```

```javascript
AskUserQuestion({
  questions: [{
    question: "How would you like to ship these changes?",
    header: "Ship mode",
    multiSelect: false,
    options: [
      { label: "Single commit", description: "All changes together in one commit" },
      { label: "Interactive", description: "Choose files per commit" },
    ]
  }]
})
```

If interactive mode selected, use `AskUserQuestion` with `multiSelect: true` for file selection:

```javascript
// Build file options from changed files
const fileOptions = changedFiles.slice(0, 4).map(f => ({
  label: f.name,
  description: f.status // "modified", "created", etc.
}));

AskUserQuestion({
  questions: [{
    question: "Select files for first commit:",
    header: "Files",
    multiSelect: true,
    options: fileOptions
  }]
})

// After first commit, if remaining files exist:
AskUserQuestion({
  questions: [{
    question: "Ship remaining changes too?",
    header: "More files",
    multiSelect: false,
    options: [
      { label: "Yes", description: "Create another commit for remaining files" },
      { label: "No", description: "Leave remaining files uncommitted" },
    ]
  }]
})
```

## Git Best Practices

yeet follows modern git conventions:

| Old Command | Modern Command | Purpose |
|-------------|----------------|---------|
| `git checkout -b <branch>` | `git switch -c <branch>` | Create and switch to new branch |
| `git checkout <branch>` | `git switch <branch>` | Switch to existing branch |
| `git checkout -- <file>` | `git restore <file>` | Discard changes to file |
| `git reset HEAD <file>` | `git restore --staged <file>` | Unstage file |

**Why modern commands?**
- `git switch` and `git restore` were introduced in Git 2.23 (2019)
- Clearer intent: `switch` for branches, `restore` for files
- Less ambiguous than overloaded `checkout` command
- Better error messages and safer defaults

**Other conventions:**
- Stage specific files over `git add -A` when possible
- Use HEREDOC for multi-line commit messages
- Include ticket references in commit body, not title
- Push with `-u` to set upstream tracking

## Reviewer-Friendly PR Body

When the diff mixes core, hand-written changes with mechanical churn (lockfiles, generated code, formatting), front-load the **core** files and collapse the mechanical files. Reviewers skim the body; you owe them a quick "where do I look?".

### Categorize before writing the body

```bash
# Pull the file list once
git diff --name-status origin/<base>...HEAD > /tmp/yeet-files.txt
```

Apply the same heuristics as `/bruhs:walk` (see that command for the full table):

| Category | Examples |
|---|---|
| **core** | Hand-written logic, public API edits, schema changes, new components |
| **mechanical** | `pnpm-lock.yaml`, `Cargo.lock`, `convex/_generated/*`, `*.gen.ts`, codegen output, formatting-only diffs |
| **test** | `*.test.ts`, `*.spec.ts`, `e2e/` |

### What to add to the PR body

Name the start point on the **Review focus** line and add the collapsed mechanical list right after it, still inside the summary section:

```markdown
**Review focus:** <where a bug would hide>. Start at `apps/web/src/app/api/v1/route.ts` → `packages/sdk/src/client.ts`

<details>
<summary>3 mechanical files (lockfiles, generated)</summary>

- pnpm-lock.yaml — +47 / -12
- convex/_generated/api.d.ts — +18 / -4
- packages/sdk/tsconfig.json — +9 / -0 (new package)
</details>
```

For trivial PRs (< 5 files, no mechanical churn), skip this section — don't add noise.

### Dependency-ordered commits

When the user asks for a clean commit history before pushing, group commits in **dependency order**, not chronological order. The order a reviewer can read top-to-bottom:

1. Schema / storage / generated API definitions
2. Core logic
3. Wiring and integration
4. UI / surface behavior
5. Tests

If the current branch's commits don't follow this order, offer to reorganize via `git rebase -i`. Only do this when the user explicitly approves — see [Tree-Identity Guard](#tree-identity-guard).

## Stacked PRs

Stack when one change is too big to review in one pass but its parts depend on each other. Each PR targets the branch below it, so each diff shows only its own layer.

### Slice by subject

- One subject per PR, in dependency order: schema/storage first, then core logic, then wiring, then UI.
- Schema or migration changes always ship in their own PR ahead of the code that uses them, stacked or not (Step 2 → *Schema split check*).
- A change to a shared file lands in the PR that owns that subject, not the PR that happened to need it.

### Create

```bash
git switch -c feat/a-schema origin/main      # bottom of the stack
# ...commit...
git push -u origin feat/a-schema
gh pr create --draft --base main --title "feat(store): add rewards table" --body-file <body>

git switch -c feat/b-logic                   # branch from the layer below
# ...commit...
git push -u origin feat/b-logic
gh pr create --draft --base feat/a-schema --title "feat(rewards): grant on purchase" --body-file <body>
```

Each PR body opens with the stack position and links: `Stack: 2/3 — after #101, before #103`.

### Update a lower layer

```bash
git switch feat/c-ui                          # top of the stack
git rebase --update-refs feat/a-schema        # moves every branch in between too (git ≥ 2.38)
```

Then **push only branches whose content moved**. A reviewer sees a moved SHA and can't tell a no-op rewrite from a real change, so every push resets their confidence in what they already read.

```bash
for b in feat/a-schema feat/b-logic feat/c-ui; do
  git diff --quiet "origin/$b" "$b" && echo "skip $b (unchanged)" && continue
  git push --force-with-lease origin "$b"
done
```

If a reviewer is mid-review, batch the fixes, verify locally, tell them what's coming, and push once.

### Merge bottom-up

1. Merge the bottom PR. When its branch is deleted, GitHub retargets the next PR to `main`.
2. Before touching the next branch, confirm its parent is merged: `gh pr view <n> --json state,baseRefName`. Pushing to a merged PR's deleted branch silently recreates it as an orphan.
3. After a **squash** merge, the child still carries the parent's original commits. Drop them:
   ```bash
   git fetch origin
   git rebase --onto origin/main <old-parent-tip> feat/b-logic
   gh pr edit <n> --base main        # if GitHub didn't retarget
   ```
   `<old-parent-tip>` is the last commit of the parent branch before the merge (`git rev-parse feat/a-schema` before you delete it locally).
4. Run the [Tree-Identity Guard](#tree-identity-guard) on the child's own diff (`git diff origin/main...HEAD`) before pushing.
5. Repeat for each layer; `/bruhs:dip` once the top merges.

## Tree-Identity Guard

If you rewrite branch history before pushing (squash, fixup, reorder), you can accidentally drop changes. The guard verifies that the **tree** (the snapshot of files at HEAD) is identical before and after the rewrite — same files, same content, just a different commit history.

### Run before rewrite

```bash
# Snapshot the current tree hash and the upstream tree hash for diffing later
git fetch origin "$(git branch --show-current)" 2>/dev/null || true
ORIGINAL_TREE=$(git rev-parse HEAD^{tree})
ORIGINAL_UPSTREAM_TREE=$(git rev-parse "@{u}^{tree}" 2>/dev/null || echo "(no upstream yet)")
echo "ORIGINAL_TREE=$ORIGINAL_TREE"
echo "ORIGINAL_UPSTREAM_TREE=$ORIGINAL_UPSTREAM_TREE"
```

### Rewrite history

Common operations:

```bash
# Squash all commits on this branch into one
git reset --soft "$(git merge-base HEAD origin/<base>)" && git commit -m "<conventional message>"

# Reorder / fixup interactively
git rebase -i "$(git merge-base HEAD origin/<base>)"
```

### Verify after rewrite

```bash
NEW_TREE=$(git rev-parse HEAD^{tree})

if [ "$NEW_TREE" = "$ORIGINAL_TREE" ]; then
  echo "✓ Tree identity preserved ($NEW_TREE)"
else
  echo "✗ Tree changed during rewrite!"
  echo "  Original: $ORIGINAL_TREE"
  echo "  Current:  $NEW_TREE"
  git diff "$ORIGINAL_TREE" "$NEW_TREE" --stat
  # STOP. Do not push.
fi
```

**Never push** if the tree changed unintentionally. Either fix the rewrite (reflog → reset back to the pre-rewrite commit) or roll back entirely:

```bash
# Roll back to pre-rewrite state
git reset --hard "HEAD@{<pre-rewrite-index>}"   # find via git reflog
```

### Guardrails

- **Never force-push to a shared base branch** (`main`, `develop`). Force-pushing your own feature branch is fine after the tree-identity check passes.
- **Never rewrite history that's already been review-commented.** Reviewers' comments anchor to commits and lines; rewriting orphans them.
- **Never pass `--no-verify`** to bypass pre-commit hooks during the rewrite.

## Tips

- **Run after /bruhs:cook** - yeet is designed to follow cook for a complete workflow
- **Review before yeet** - Make sure you're happy with changes before shipping
- **One feature per yeet** - Keep commits focused; use interactive mode if needed
- **Check PR** - Always review the PR link to verify everything looks right
- **Pair with `/bruhs:land`** - yeet opens the PR; land babysits it to green
- **Pair with `/bruhs:walk --post`** - drop a reviewer walkthrough comment for large PRs
