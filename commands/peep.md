---
description: Address PR review comments with isolated subagents and local validation — analyze each thread, propose fixes, verify against project typecheck/lint/tests, apply, commit, optionally merge. Use when responding to PR feedback or checking merge readiness.
---

# peep - Address PR Review Comments

Review and address PR feedback, push fixes, and optionally merge when ready.

Uses **isolated subagents** per comment thread to prevent context bleed. Each comment is analyzed independently — findings from one thread never influence analysis of another.

## Contents

- [Best Practices](#best-practices)
- [Invocation](#invocation)
- [Prerequisites](#prerequisites)
- [Architecture: Subagent Review Model](#architecture-subagent-review-model)
- [Local Validation (Key Principle)](#local-validation-key-principle)
- [Workflow](#workflow)
- [Output Summary](#output-summary)
- [Design Decisions (from BugBot + Code Review Research)](#design-decisions-from-bugbot--code-review-research)
- [Tips](#tips)

---

## Best Practices

- **`practices/pr-review.md`** — primary lens. Conventional Comments labels (`nit`, `suggestion`, `issue`, `praise`, decorations like `(blocking)` / `(non-blocking)`), reviewer/author etiquette, anti-patterns. Loaded by every subagent so categorization stays consistent.
- **Stack practices** — same as `cook` and `slop`. Use the project's stack to inform what counts as a real issue vs preference.

## Invocation

- `/bruhs:peep` - Address comments on current branch's PR
- `/bruhs:peep 42` - Address comments on PR #42 (switches branch if needed)
- `/bruhs:peep PERDIX-145` - Find PR by Linear ticket ID

## Prerequisites

- GitHub CLI (`gh`) authenticated
- Open PR with review comments
- Linear MCP configured (optional, for ticket ID lookup)

## Architecture: Subagent Review Model

```
Main Agent (orchestrator)
├── Fetches PR metadata + comment threads
├── Spawns N subagents in parallel (one per comment thread)
│   ├── Subagent 1: reads file, analyzes comment, proposes fix, VALIDATES LOCALLY
│   ├── Subagent 2: reads file, analyzes comment, proposes fix, VALIDATES LOCALLY
│   └── Subagent N: reads file, analyzes comment, proposes fix, VALIDATES LOCALLY
├── Aggregates results, filters by confidence + validation status
├── Presents to user for approval (showing which fixes verified locally)
├── Runs full validation suite before commit
└── Applies approved fixes, commits, pushes
```

**Why subagents?**
- **No context bleed**: Each comment is analyzed in a fresh context. Analysis of a type error in `queries.ts` doesn't bias the review of a naming suggestion in `leaderboard-card.tsx`.
- **Parallel execution**: All comments analyzed concurrently, not sequentially.
- **Dynamic context discovery**: Each subagent reads what it needs (the file, imports, related types) instead of front-loading everything into one prompt.
- **Aggressive analysis + natural filtering**: Subagents investigate thoroughly. Their tool use (reading files, checking types) naturally filters false positives — no need for conservative prompting.
- **Local validation per fix**: Each subagent runs the project's real typecheck/lint/scoped tests against its proposed fix and reverts. Static reasoning is not enough — a fix that "looks right" can still break the build. Only fixes that pass local checks are surfaced as high-confidence.

## Local Validation (Key Principle)

**Every proposed fix must be verified against the project's actual tooling before it is presented to the user as valid.** Subagents don't just read code and reason — they apply the fix in-place, run scoped checks (typecheck, linter, affected tests), and revert, leaving the working tree exactly as they found it.

Validation commands are detected per-project:
- **TypeScript/JS**: `npm run typecheck` / `tsc --noEmit`, `eslint <file>` / `biome check <file>`, `vitest run <file>` / `jest <file>`
- **Rust**: `cargo check`, `cargo clippy`, `cargo test <module>`
- **Python**: `ruff check <file>`, `mypy <file>`, `pytest <file>`
- **Go**: `go vet ./...`, `go build ./...`, `go test <package>`

Safety rules enforced by subagents:
1. Before modifying, check `git status --porcelain <file>` — if the file has uncommitted changes, skip validation with reason `dirty-overlap`.
2. Always revert via the reverse Edit (swap `old_string`/`new_string`) after validation runs — pass or fail.
3. If revert fails, stop and report `dirty-cleanup-needed` so the orchestrator can alert the user.
4. Never run destructive commands (no `git reset`, no `rm`, no `git clean`).

## Workflow

### Step 1: Detect PR

**If no argument provided:**

```bash
# Get PR for current branch
pr=$(gh pr view --json number,headRefName,url,state,reviewDecision,title 2>/dev/null)
```

If no PR found, use `AskUserQuestion`:

```javascript
AskUserQuestion({
  questions: [{
    question: "No PR found for current branch. What would you like to do?",
    header: "No PR",
    multiSelect: false,
    options: [
      { label: "Specify a PR number", description: "Enter a specific PR to review" },
      { label: "Abort", description: "Exit without reviewing" },
    ]
  }]
})
```

**If PR number provided:**

```bash
pr=$(gh pr view <number> --json number,headRefName,url,state,reviewDecision,title)
currentBranch=$(git branch --show-current)

# Switch to PR branch if needed
if [ "$currentBranch" != "$headRefName" ]; then
  git fetch origin $headRefName
  git switch $headRefName
  git pull origin $headRefName
fi
```

**If Linear ticket ID provided:**

```javascript
ToolSearch("select:mcp__linear__get_issue")

// Get issue details
issue = mcp__linear__get_issue({ identifier: "PERDIX-145" })

// Search for PR with ticket reference in title or body
pr=$(gh pr list --search "PERDIX-145" --json number,headRefName --jq '.[0]')

// Then proceed as with PR number
```

### Step 2: Fetch Review Comments

```bash
# Get all review comments
gh api repos/{owner}/{repo}/pulls/{number}/comments --jq '.[] | {
  id: .id,
  path: .path,
  line: .line,
  body: .body,
  user: .user.login,
  created_at: .created_at,
  in_reply_to_id: .in_reply_to_id
}'

# Get review threads with resolution status
gh api graphql -f query='
  query($owner: String!, $repo: String!, $number: Int!) {
    repository(owner: $owner, name: $repo) {
      pullRequest(number: $number) {
        reviewThreads(first: 100) {
          nodes {
            id
            isResolved
            path
            line
            comments(first: 10) {
              nodes {
                body
                author { login }
              }
            }
          }
        }
      }
    }
  }
'

# Get PR reviews (approved, changes requested, etc.)
gh pr view <number> --json reviews --jq '.reviews[] | {user: .author.login, state: .state, body: .body}'
```

### Step 3: Zero Comments? Offer AI Discovery Review

If there are **0 unresolved comment threads**, offer an AI review pass before skipping to merge readiness. This catches issues that human reviewers missed or haven't gotten to yet.

```javascript
AskUserQuestion({
  questions: [{
    question: "No review comments found. Want an AI review before merging?",
    header: "AI Review",
    multiSelect: false,
    options: [
      { label: "Yes - full review", description: "Subagent per changed file (thorough)" },
      { label: "Yes - quick scan", description: "Single subagent over the full diff (fast)" },
      { label: "Skip to merge", description: "No review needed" },
    ]
  }]
})
```

**If "Yes - full review":**

Get the list of changed files, then spawn one `feature-dev:code-reviewer` subagent per file, all in parallel:

```bash
# Get changed files
gh pr diff <number> --name-only
```

```javascript
// For each changed file, spawn in parallel:
Agent({
  subagent_type: "feature-dev:code-reviewer",
  description: `Review ${file}`,
  prompt: `
You are reviewing a single file from PR #${number}: "${pr.title}".
${pr.description ? `PR description: "${pr.description}"` : ""}

Your job is to find bugs, security issues, logic errors, and performance problems in this file's changes. Do NOT comment on style, formatting, or naming — those are handled by linters.

## Your Task

1. **Read the file** at \`${file}\`.
2. **Read the PR diff for this file** to understand what changed vs what was already there.
3. **Read imports, types, and related files** as needed to verify correctness.
4. **Investigate aggressively** — check every suspicious pattern. Your tool use is the false-positive filter. If you read the code and confirm it's fine, don't report it.
5. **Only report issues you verified are real** after reading the surrounding code.

## What to look for (priority order)
1. Bugs and logic errors (off-by-one, null deref, race conditions, missing error handling)
2. Security issues (injection, XSS, hardcoded secrets, improper auth)
3. Performance anti-patterns — these are bugs, not optimizations. Flag aggressively:
   - N+1 queries (ORM lazy loads, fetch-in-map)
   - `await` inside a loop over independent work
   - Per-request client construction (`new PrismaClient()`, `httpx.AsyncClient()`, `reqwest::Client::new()`)
   - Sync I/O / crypto / hashing inside async handlers
   - Unbounded `Promise.all` / recursion / `Vec::with_capacity` on user input
   - Fetch waterfalls where `Promise.all` would work
   - Unstable references passed to memoized children
   - Full-body JSON logging in hot paths
   - Missing database indexes on queried columns
   - Missing cache headers on cacheable GETs
4. Missing edge cases (empty input, null, overflow)
5. API contract violations (breaking backward compat)

## Validate Every Proposed Fix Locally (REQUIRED)

For each issue where you propose a fix, before emitting the final report:

1. Detect the project's validation commands (package.json scripts, tsc, eslint/biome, cargo, ruff/mypy/pytest, go vet/test) — prefer file-scoped invocations.
2. Check \`git status --porcelain ${file}\` — if dirty, mark \`VALIDATION_STATUS: skipped\` (reason: dirty-overlap) and do not apply.
3. Apply the fix via Edit.
4. Run scoped checks (typecheck + linter + colocated test if present). Capture results.
5. Revert via Edit with old_string/new_string swapped. Confirm \`git diff --stat ${file}\` is empty.
6. If revert fails, set \`VALIDATION_STATUS: dirty-cleanup-needed\` and STOP — do not process further issues for this file.

Downgrade CONFIDENCE by 1 for any fix where validation failed. Never run destructive git commands.

## Output Format (STRICT)

For each issue found, output:

ISSUE: <one-line summary>
SEVERITY: <critical|warning|suggestion>
FILE: ${file}
LINE: <line number>
CONFIDENCE: <1-5>
ANALYSIS: <2-3 sentence explanation, what you verified>
FIX_OLD_STRING: |
  <exact string to replace>
FIX_NEW_STRING: |
  <replacement string>
VALIDATION_STATUS: <passed|failed|skipped|dirty-cleanup-needed>
VALIDATION_COMMANDS: |
  <commands run, one per line>
VALIDATION_OUTPUT: |
  <"all clean" or last ~20 lines of first failure, or skip reason>
VALIDATION_SKIP_REASON: <reason|N/A>

If no issues found, output:
NO_ISSUES_FOUND: true
FILES_READ: <list of files you read to verify>
`
})
```

After all subagents return, aggregate and present findings the same way as comment-thread reviews (Step 4), but labeled as "AI-discovered issues" rather than reviewer comments.

**If "Yes - quick scan":**

Spawn a single subagent with the full diff:

```bash
diff=$(gh pr diff <number>)
```

```javascript
Agent({
  subagent_type: "feature-dev:code-reviewer",
  description: "Quick scan PR diff",
  prompt: `
Quick review of PR #${number}: "${pr.title}".

## Diff
\`\`\`
${diff}
\`\`\`

Scan for critical bugs, security issues, and logic errors only.
Skip style, naming, and minor suggestions. Only report high-confidence (4+) issues.

For each issue:
ISSUE: <summary>
SEVERITY: <critical|warning>
FILE: <path>
LINE: <number>
CONFIDENCE: <1-5>
FIX_OLD_STRING: | ...
FIX_NEW_STRING: | ...

If clean, output: NO_ISSUES_FOUND: true
`
})
```

**If "Skip to merge":** Jump directly to Step 12 (Check Merge Readiness).

### Step 4: Fan Out — Spawn Subagents Per Comment Thread (if comments exist)

For each **unresolved** comment thread, spawn an Agent subagent **in parallel**. All subagents launch in a single tool-call message for maximum concurrency.

**CRITICAL: Launch ALL subagents in one message.** Do not await one before spawning the next.

Each subagent receives a self-contained prompt with:
- The comment body and reviewer username
- The file path and line number
- The PR title and description (for intent context)
- Instructions to read the file, analyze, categorize, and propose a fix

```javascript
// For each unresolved thread, spawn in parallel:
Agent({
  subagent_type: "feature-dev:code-reviewer",
  description: `Review ${thread.path}:${thread.line}`,
  prompt: `
You are analyzing a single PR review comment in isolation. Do NOT search for or analyze other comments.

## PR Context
- Title: "${pr.title}"
- Description: "${pr.description}"

## Review Comment
- Reviewer: @${thread.comments[0].author.login}
- File: ${thread.path}
- Line: ${thread.line}
- Comment: "${thread.comments.map(c => c.body).join('\n> ')}"

## Your Task

1. **Read the file** at \`${thread.path}\` to understand the full context around line ${thread.line}.
2. **Read imports and related files** if needed to understand types, dependencies, or contracts.
3. **Categorize** the comment as one of:
   - \`must-fix\`: Bug, security issue, will break, blocking review ("please fix", "this will break", "bug", "security")
   - \`suggestion\`: Optional improvement ("consider", "might be better", "nit:", "optional")
   - \`question\`: Needs explanation ("why", "what does", "can you explain", "?")
   - \`approval\`: Positive feedback ("lgtm", "looks good", "nice", ":+1:") — no action needed
4. **Assess confidence** (1-5) that your categorization and proposed action are correct.
5. **If must-fix or suggestion**: Propose a concrete fix. Show the exact \`old_string\` and \`new_string\` for an Edit tool call.
6. **Validate the fix locally** (see next section) — static reasoning alone is not sufficient.
7. **If question**: Draft a response that explains the reasoning, referencing the code context you discovered.

## Local Validation (REQUIRED for every fix)

Do this before reporting. If you propose a fix without running validation, the orchestrator treats it as unverified and lowers its confidence.

1. **Detect validation commands** by reading project config. Prefer project scripts when defined:
   - package.json → \`scripts\` for \`typecheck\`, \`lint\`, \`test\`, \`check\`
   - tsconfig.json → run \`npx tsc --noEmit\` if no project script
   - biome.json / .eslintrc* → \`npx biome check <file>\` / \`npx eslint <file>\`
   - Cargo.toml → \`cargo check\`, \`cargo clippy -- -D warnings\`, \`cargo test <module>\`
   - pyproject.toml → \`ruff check <file>\`, \`mypy <file>\`, \`pytest <file>\`
   - go.mod → \`go vet ./...\`, \`go build ./...\`, \`go test <pkg>\`
   Prefer file-scoped invocations over whole-repo where the tool supports it, for speed.

2. **Check for working-tree conflicts**: run \`git status --porcelain ${thread.path}\`. If the file is already modified, skip validation and set \`VALIDATION_STATUS: skipped\` with reason \`dirty-overlap\`. Do not apply your fix.

3. **Apply the fix** using the Edit tool with your \`FIX_OLD_STRING\` / \`FIX_NEW_STRING\`.

4. **Run the detected checks**. Capture exit codes and the last ~20 lines of output for each. Pick the minimum useful set — typecheck + linter + the test file colocated with the changed file (if one exists). Avoid full-suite runs unless nothing smaller is available.

5. **Revert the fix** by calling Edit with \`old_string\` and \`new_string\` swapped — put the working tree back exactly as you found it. Confirm with \`git diff --stat ${thread.path}\` showing no changes.

6. **Report the outcome**:
   - All commands exited 0 → \`VALIDATION_STATUS: passed\`
   - Any command failed → \`VALIDATION_STATUS: failed\` (and downgrade \`CONFIDENCE\` by 1)
   - Could not run meaningful checks (no tools detected, dirty tree, etc.) → \`VALIDATION_STATUS: skipped\` with a reason
   - Revert failed → \`VALIDATION_STATUS: dirty-cleanup-needed\` and STOP. Do not continue. The orchestrator will surface this to the user.

**Never** use destructive git commands (reset, clean, checkout --). If revert via Edit doesn't work, report \`dirty-cleanup-needed\` and let the orchestrator handle it.

## Output Format (STRICT)

Respond with ONLY this structured format:

CATEGORY: <must-fix|suggestion|question|approval>
CONFIDENCE: <1-5>
ANALYSIS: <1-2 sentence explanation of what the reviewer is asking for and whether it's valid>
PROPOSED_ACTION: <fix|respond|skip>
FIX_OLD_STRING: |
  <exact string to replace, or "N/A" if not a fix>
FIX_NEW_STRING: |
  <replacement string, or "N/A" if not a fix>
RESPONSE_DRAFT: |
  <suggested reply to post on the thread, or "N/A" if not responding>
REASONING: <why this fix/response is correct, what you verified>
VALIDATION_STATUS: <passed|failed|skipped|dirty-cleanup-needed|n/a>
VALIDATION_COMMANDS: |
  <one shell command per line, in the order run, or "N/A">
VALIDATION_OUTPUT: |
  <condensed output: "all clean" on success, or last ~20 lines of the first failure, or skip reason>
VALIDATION_SKIP_REASON: <dirty-overlap|no-tools-detected|non-code-change|other: ...|N/A>
`
})
```

### Step 5: Aggregate and Present Results

Collect all subagent results. Filter and sort:

1. **Drop approval-category results** (no action needed)
2. **Sort by**: must-fix first, then suggestion, then question
3. **Within each category**: sort by confidence (highest first), with validation-passed items above validation-failed/skipped at the same confidence
4. **Flag low-confidence items** (confidence <= 2) for manual review
5. **Surface any `dirty-cleanup-needed` subagents immediately** and halt the flow — the working tree may be inconsistent. Show the user which file is affected and let them run `git status` / `git diff` before continuing.

Display summary (include validation status per thread):

```
PR #42: Add leaderboard to game page
Branch: perdix-140-add-leaderboard

Review Status:
- @reviewer1: Changes Requested
- @reviewer2: Approved

Comments analyzed by isolated subagents (4 threads, 0 context bleed):
┌─────────────┬──────┬───────────┬──────────────┬─────────────────────────────────────┐
│ Category    │ Count│ Confidence│ Validation   │ Files                               │
├─────────────┼──────┼───────────┼──────────────┼─────────────────────────────────────┤
│ must-fix    │ 1    │ 5/5       │ ✓ passed     │ lib/db/queries.ts                   │
│ suggestion  │ 2    │ 4/5, 3/5  │ ✓ / ✗ failed │ components/game/leaderboard-card.tsx│
│ question    │ 1    │ 4/5       │ n/a          │ lib/hooks/use-leaderboard.ts        │
└─────────────┴──────┴───────────┴──────────────┴─────────────────────────────────────┘

Legend: ✓ passed (fix verified locally) · ✗ failed (typecheck/lint/test broke) · ○ skipped (no validator / dirty file)
```

Then use `AskUserQuestion`:

```javascript
AskUserQuestion({
  questions: [{
    question: "Ready to address comments?",
    header: "Review",
    multiSelect: false,
    options: [
      { label: "Yes", description: "Go through each comment with AI suggestions" },
      { label: "View all first", description: "See all subagent analyses before addressing" },
      { label: "Auto-apply high confidence", description: "Apply all fixes with confidence >= 4, review the rest" },
      { label: "Abort", description: "Exit without addressing" },
    ]
  }]
})
```

### Step 6: Address Each Comment (with Subagent Analysis)

For each comment, present the subagent's analysis alongside the original comment.

**Must-fix example:**

```
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
[1/4] must-fix | lib/db/queries.ts:45 | confidence: 5/5
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

@reviewer1:
> This query isn't using an index. Add .orderBy(desc(agentStats.winRate))
> before the limit to use the existing index.

Subagent analysis:
  Category: must-fix (confidence 5/5)
  The reviewer is correct — the query returns arbitrary rows without ordering.
  The agentStats table has an index on winRate. Adding orderBy ensures index
  usage and deterministic results.

  Proposed fix:
  - return db.select().from(agentStats).limit(limit);
  + return db.select().from(agentStats).orderBy(desc(agentStats.winRate)).limit(limit);

  Verified: desc import exists from drizzle-orm, agentStats.winRate column confirmed.

  Local validation: ✓ passed
    $ npx tsc --noEmit              → 0
    $ npx biome check lib/db/queries.ts  → 0
    $ npx vitest run lib/db/queries.test.ts  → 0 (3 passed)
```

If validation failed, show the failing command and its tail:

```
  Local validation: ✗ failed
    $ npx tsc --noEmit              → 2 (type errors)

    lib/db/queries.ts:45:40 - error TS2345: Argument of type 'string' is not
      assignable to parameter of type 'SQLWrapper | Column | ...'
```

A failing validation does NOT automatically drop the fix — the user may still want to apply it (e.g. the failure is a pre-existing issue the fix surfaced). But it is surfaced prominently and excluded from auto-apply.

Then use `AskUserQuestion`:

```javascript
AskUserQuestion({
  questions: [{
    question: "How would you like to proceed?",
    header: "Action",
    multiSelect: false,
    options: [
      { label: "Apply fix", description: "Apply the subagent's proposed fix" },
      { label: "Custom fix", description: "Write a different fix" },
      { label: "Skip", description: "Address later" },
      { label: "Discuss", description: "Need clarification from reviewer" },
    ]
  }]
})
```

**If "Apply fix":**

Apply the fix using the Edit tool with the subagent's exact `old_string` and `new_string`. Show the diff and confirm:

```
Applying fix...

✓ Updated lib/db/queries.ts:45

Diff:
- return db.select().from(agentStats).limit(limit);
+ return db.select().from(agentStats).orderBy(desc(agentStats.winRate)).limit(limit);
```

Then use `AskUserQuestion`:

```javascript
AskUserQuestion({
  questions: [{
    question: "Does this address the comment?",
    header: "Confirm",
    multiSelect: false,
    options: [
      { label: "Yes", description: "Continue to next comment" },
      { label: "No", description: "Revise the fix" },
    ]
  }]
})
```

**If "Skip":**

```
Skipped. Will remain unresolved.
```

**If "Discuss":**

```
What would you like to clarify?
> [user types response]

Posting reply...
✓ Replied to @reviewer1's comment
```

### Step 7: Handle Suggestions (with Subagent Context)

```
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
[2/4] suggestion | components/game/leaderboard-card.tsx:23 | confidence: 4/5
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

@reviewer2:
> nit: Consider using a constant for the max items instead of magic number 10

Subagent analysis:
  Category: suggestion (confidence 4/5)
  Valid nit — the value 10 appears here and in the getTopAgents query default.
  Extracting a constant would keep them in sync. However, the query default
  already parameterizes this, so it's low-risk as-is.

  Proposed fix:
  + const LEADERBOARD_LIMIT = 10;
  - const topAgents = agents.slice(0, 10);
  + const topAgents = agents.slice(0, LEADERBOARD_LIMIT);
```

Then use `AskUserQuestion`:

```javascript
AskUserQuestion({
  questions: [{
    question: "How would you like to proceed?",
    header: "Suggestion",
    multiSelect: false,
    options: [
      { label: "Apply", description: "Apply subagent's proposed fix" },
      { label: "Acknowledge", description: "Good idea, will do later" },
      { label: "Decline", description: "Explain why not needed" },
      { label: "Skip", description: "Address later" },
    ]
  }]
})
```

**If "Decline":**

First, output the suggested response (drafted by the subagent):
```
Suggested response:
"Thanks for the suggestion! I'm keeping it as-is because this is only used
in one place and the limit is already parameterized in the query. Adding
a constant here would be over-abstraction."
```

Then use `AskUserQuestion`:

```javascript
AskUserQuestion({
  questions: [{
    question: "Post this reply?",
    header: "Reply",
    multiSelect: false,
    options: [
      { label: "Yes", description: "Post the suggested response" },
      { label: "Edit first", description: "Modify the response before posting" },
    ]
  }]
})
```

### Step 8: Handle Questions (with Subagent Context)

```
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
[4/4] question | lib/hooks/use-leaderboard.ts:12 | confidence: 4/5
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

@reviewer1:
> Why refetch every 5 seconds? Seems aggressive for a leaderboard.

Subagent analysis:
  Category: question (confidence 4/5)
  The 5-second interval matches the game state polling interval used in
  useGameState (same file, line 28). During active games, matches complete
  frequently. The reviewer may not have seen the game state context.

  Suggested response:
  "The 5-second interval matches our game state polling. During active games,
  the leaderboard can change frequently as matches complete. Happy to make
  this configurable if you think it's too aggressive."
```

Then use `AskUserQuestion`:

```javascript
AskUserQuestion({
  questions: [{
    question: "How would you like to proceed?",
    header: "Question",
    multiSelect: false,
    options: [
      { label: "Post suggested", description: "Post the subagent's drafted response" },
      { label: "Edit and post", description: "Modify before posting" },
      { label: "Skip", description: "Address later" },
    ]
  }]
})
```

### Step 9: Auto-Apply Mode (Optional)

If the user selected "Auto-apply high confidence" in Step 4:

1. Apply all fixes where **confidence >= 4 AND validation_status == passed** automatically
2. Kick fixes with validation_status of `failed`, `skipped`, or `dirty-cleanup-needed` to manual review regardless of confidence — the user should see the evidence before the code lands
3. Show a summary of what was applied
4. Present remaining items for manual review

```
Auto-applied (confidence >= 4, validation passed):
✓ [must-fix] lib/db/queries.ts:45 - Added orderBy clause (5/5, ✓ tsc + biome + vitest)
✓ [suggestion] components/game/leaderboard-card.tsx:23 - Added constant (4/5, ✓ tsc + biome)

Needs manual review:
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
[1/2] suggestion | components/game/leaderboard-card.tsx:45 | confidence: 2/5 | validation: ✓ passed
[2/2] must-fix   | lib/api/handler.ts:88 | confidence: 5/5 | validation: ✗ failed (tsc)
...
```

### Step 10: Commit and Push Fixes

After addressing all comments:

```bash
# Check for changes
git status
git diff
```

**Before committing, run the full validation suite once.** Per-fix validation catches each fix in isolation, but not cross-file interactions (e.g. two fixes that separately pass tsc but together introduce a type conflict). Run the project's standard CI-equivalent commands:

```bash
# Detect & run — examples; use what the project defines
npm run typecheck && npm run lint && npm test
# or
cargo check && cargo clippy -- -D warnings && cargo test
# or
go vet ./... && go test ./...
```

If full-suite validation fails, surface the failure and ask the user how to proceed:

```javascript
AskUserQuestion({
  questions: [{
    question: "Full validation failed after applying fixes. What now?",
    header: "Validation failed",
    multiSelect: false,
    options: [
      { label: "Show me the failure", description: "Print the failing command output" },
      { label: "Revert last fix", description: "Un-apply the most recently applied fix and re-run" },
      { label: "Revert all fixes", description: "Restore the working tree to pre-peep state" },
      { label: "Commit anyway", description: "I'll fix the failure in a follow-up" },
    ]
  }]
})
```

If changes were made:

```
Changes made:
- lib/db/queries.ts (1 fix)
- components/game/leaderboard-card.tsx (1 fix)

Commit message:
"fix: address PR review feedback

- Add orderBy to getTopAgents query for index usage
- Extract LEADERBOARD_LIMIT constant"
```

Then use `AskUserQuestion`:

```javascript
AskUserQuestion({
  questions: [{
    question: "Commit and push these changes?",
    header: "Commit",
    multiSelect: false,
    options: [
      { label: "Yes", description: "Commit and push now" },
      { label: "Edit message", description: "Modify commit message first" },
      { label: "Abort", description: "Don't commit yet" },
    ]
  }]
})
```

```bash
git add -A
git commit -m "$(cat <<'EOF'
fix: address PR review feedback

- Add orderBy to getTopAgents query for index usage
- Extract LEADERBOARD_LIMIT constant
EOF
)"
git push
```

### Step 11: Resolve Threads (Optional)

```javascript
// For comments that were addressed with code changes
gh api graphql -f query='
  mutation($threadId: ID!) {
    resolveReviewThread(input: {threadId: $threadId}) {
      thread { isResolved }
    }
  }
' -f threadId="$threadId"
```

Then use `AskUserQuestion`:

```javascript
AskUserQuestion({
  questions: [{
    question: "Resolve addressed comment threads?",
    header: "Resolve",
    multiSelect: false,
    options: [
      { label: "Yes", description: "Mark addressed threads as resolved" },
      { label: "No", description: "Let reviewer resolve them" },
    ]
  }]
})
```

### Step 12: Check Merge Readiness

```bash
# Refresh PR status
gh pr view <number> --json reviewDecision,mergeable,mergeStateStatus,statusCheckRollup
```

Evaluate:
- `reviewDecision`: APPROVED, CHANGES_REQUESTED, or REVIEW_REQUIRED
- `mergeable`: MERGEABLE, CONFLICTING, or UNKNOWN
- `mergeStateStatus`: CLEAN, UNSTABLE, DIRTY
- `statusCheckRollup`: All checks passing?

### Step 13: Offer to Merge

**If ready to merge:**

```
✓ All review comments addressed
✓ PR approved by @reviewer1, @reviewer2
✓ CI passing
✓ No merge conflicts
```

Then use `AskUserQuestion`:

```javascript
AskUserQuestion({
  questions: [{
    question: "Ready to merge?",
    header: "Merge",
    multiSelect: false,
    options: [
      { label: "Squash and merge (Recommended)", description: "Combine commits into one" },
      { label: "Merge commit", description: "Preserve all commits" },
      { label: "Rebase and merge", description: "Linear history without merge commit" },
      { label: "Not yet", description: "Wait for more reviews" },
    ]
  }]
})
```

**If merge blocked:**

```
⚠ Cannot merge yet:

- ✗ Changes requested by @reviewer1
- ✓ CI passing
- ✓ No merge conflicts

Waiting for @reviewer1 to re-review after your fixes.
```

Then use `AskUserQuestion`:

```javascript
AskUserQuestion({
  questions: [{
    question: "What would you like to do?",
    header: "Blocked",
    multiSelect: false,
    options: [
      { label: "Request re-review", description: "Ask @reviewer1 to re-review" },
      { label: "Done for now", description: "Exit and wait for re-review" },
    ]
  }]
})
```

```bash
# Request re-review
gh pr edit <number> --add-reviewer reviewer1
```

### Step 14: Merge and Transition

If user chooses to merge:

```bash
# Squash and merge (default)
gh pr merge <number> --squash --delete-branch

# Or merge commit
gh pr merge <number> --merge --delete-branch

# Or rebase
gh pr merge <number> --rebase --delete-branch
```

After successful merge:

```
✓ PR #42 merged!

Switching to main and cleaning up...
```

Then automatically run the dip workflow:
- Switch to base branch
- Pull latest
- Delete local feature branch (remote already deleted by --delete-branch)
- Check for stashed changes

```
✓ Switched to main
✓ Pulled latest (includes your merged changes)
✓ Deleted local branch: perdix-140-add-leaderboard

Ready for your next feature! Run /bruhs:cook to start.
```

### Step 15: Update Linear (if available)

If Linear MCP is configured and PR was merged:

```javascript
ToolSearch("select:mcp__linear__update_issue")

// Find the Done/Completed state
mcp__linear__update_issue({
  issueId: issueId,
  stateId: "done"  // Or find the "Done" state ID
})
```

```
Updating Linear...
✓ PERDIX-140 → Done
```

## Output Summary

**After addressing comments (not merging yet):**

```
PR #42: Add leaderboard to game page

Subagent Review (4 threads analyzed in parallel, 0 context bleed):

Addressed:
✓ [must-fix] lib/db/queries.ts:45 - Added orderBy clause (5/5)
✓ [suggestion] components/game/leaderboard-card.tsx:23 - Added constant (4/5)
✓ [question] lib/hooks/use-leaderboard.ts:12 - Replied (4/5)

Skipped:
- [suggestion] components/game/leaderboard-card.tsx:45 - Will address later (2/5)

Committed and pushed:
✓ fix: address PR review feedback (abc1234)

Requested re-review from @reviewer1

Run /bruhs:peep again after re-review, or wait for approval to merge.
```

**After addressing and merging:**

```
PR #42: Add leaderboard to game page

Subagent Review (4 threads analyzed in parallel, 0 context bleed):

Addressed:
✓ [must-fix] lib/db/queries.ts:45 - Added orderBy clause (5/5)
✓ [suggestion] components/game/leaderboard-card.tsx:23 - Added constant (4/5)
✓ [question] lib/hooks/use-leaderboard.ts:12 - Replied (4/5)

Committed and pushed:
✓ fix: address PR review feedback (abc1234)

Merged:
✓ PR #42 squash-merged into main

Cleaned up:
✓ Switched to main
✓ Deleted branch perdix-140-add-leaderboard

Linear:
✓ PERDIX-140 → Done

Ready for your next feature! Run /bruhs:cook to start.
```

## Design Decisions (from BugBot + Code Review Research)

### Why subagents over single-context review?

| Approach | Pros | Cons |
|----------|------|------|
| Single context (old) | Simple, sees all comments at once | Context bleed between comments, biased analysis, context window pressure |
| **Subagent per thread (new)** | **Isolated analysis, parallel, no bias** | More API calls, slightly more orchestration |
| Multi-pass with voting (BugBot v1) | Good false positive reduction | Overkill for addressing known comments |

For **addressing existing review comments** (not discovering new bugs), subagent-per-thread is the sweet spot. We're not doing discovery — we're analyzing known feedback — so multi-pass voting is unnecessary overhead.

### Key learnings applied from Cursor's BugBot:

1. **Aggressive prompting + tool-based verification** — Subagents investigate thoroughly and verify their own findings by reading files. Conservative prompting caused under-reporting in BugBot's agentic system.
2. **Dynamic context discovery** — Each subagent reads the file and related imports on its own, rather than us pre-loading all context. BugBot found this consistently outperformed pre-computed context.
3. **Confidence scoring** — Self-rated confidence (1-5) enables auto-apply mode for high-confidence fixes and flags uncertain items for manual review.
4. **Iterate on tool design** — "Even small changes in tool design had outsized impact on outcomes." The structured output format and explicit verification instructions matter more than prompt length.

## Tips

- **Run early, run often** — Don't wait for all reviews; address feedback as it comes
- **Must-fix first** — Always prioritize blocking feedback
- **Use auto-apply** — For PRs with many comments, auto-apply high-confidence fixes saves time
- **Decline gracefully** — It's okay to push back on suggestions with good reasoning
- **Re-request reviews** — After pushing fixes, explicitly request re-review
- **Let reviewers resolve** — Some teams prefer reviewers mark their own threads resolved
- **Trust confidence scores** — Scores >= 4 are reliable; scores <= 2 need human judgment
