---
description: Generate a reviewer walkthrough for a PR — markdown by default (postable as a PR comment), interactive HTML canvas opt-in. Categorizes files into core vs mechanical, summarizes verbose code as pseudocode, surfaces risk and migration order. Use when posting a PR for review, or asked to "walk through this PR".
---

# walk - PR Reviewer Walkthrough

Generate a walkthrough that reads like a peer explaining the PR to a reviewer — what to look at first, what to skip, what's risky, where the moved code went. Default output is markdown (postable as a PR comment). `--canvas` swaps to an interactive HTML page with collapsible diffs and moved-code detection.

## Contents

- [Invocation](#invocation)
- [Output Modes](#output-modes)
- [Workflow](#workflow)
- [File Categorization](#file-categorization)
- [Pseudocode Summaries](#pseudocode-summaries)
- [Canvas Mode](#canvas-mode)
- [Examples](#examples)
- [Tips](#tips)

---

## Invocation

- `/bruhs:walk` — Walkthrough for the current branch's PR (markdown)
- `/bruhs:walk 42` — Walkthrough for PR #42
- `/bruhs:walk --canvas` — Interactive HTML page served locally
- `/bruhs:walk --post` — Post the markdown walkthrough as a PR comment
- `/bruhs:walk --commit-body` — Replace the PR body's "What changed" section with the walkthrough
- `/bruhs:walk --max-pseudocode 200` — Only summarize files larger than N changed lines as pseudocode (default: 150)

## Output Modes

| Mode | When to use | Output |
|---|---|---|
| **markdown** (default) | Posting to PR comment, reviewer reads in GitHub UI, async review | Single markdown block, copy-pasteable |
| **canvas** (`--canvas`) | Synchronous walkthrough, complex diff with moved code, you want collapsible sections | Local HTML page served at `http://127.0.0.1:8432` |
| **post** (`--post`) | Auto-post the markdown as a `gh pr comment` so reviewers see it before the diff | Markdown + PR comment URL |

Choose markdown for the 80% case. Use `--canvas` when the PR has > 10 files or contains a big refactor with moved blocks where the GitHub diff view is hard to follow.

## Workflow

### Step 1: Fetch PR Data

```bash
# Resolve PR
pr=$(gh pr view --json number,title,body,baseRefName,headRefName,additions,deletions,changedFiles,author 2>/dev/null \
  || gh pr view <PR#> --json number,title,body,baseRefName,headRefName,additions,deletions,changedFiles,author)

# Pull file-level diffs (used for both modes)
gh api "repos/{owner}/{repo}/pulls/${PR_NUMBER}/files" --paginate \
  --jq '.[] | {filename, status, additions, deletions, patch}' \
  > /tmp/walk-pr-${PR_NUMBER}-files.json

# Existing review comments (so we can hint at unresolved threads)
gh api "repos/{owner}/{repo}/pulls/${PR_NUMBER}/comments" \
  --jq '.[] | {user: .user.login, body, path, line}' \
  > /tmp/walk-pr-${PR_NUMBER}-comments.json
```

### Step 2: Read the Diff

Open each changed file's patch from `/tmp/walk-pr-<N>-files.json`. Build a mental model:

- What is this PR doing? Write a 1-2 sentence TL;DR.
- Which files contain the **core logic**?
- Which files are **mechanical** (lockfiles, generated code, formatting, imports)?
- Are there **moved blocks** (≥ 3 lines deleted in one file and added identically elsewhere)?
- What's the **migration order** if the changes need to land in a specific sequence?
- Where's the **risk**? New code paths, dropped error handling, behavior changes hidden in refactors?

### Step 3: Categorize Files

See [File Categorization](#file-categorization). For each file decide: `core` | `mechanical` | `moved` | `test`.

### Step 4: Identify Pseudocode Candidates

Any file with > `--max-pseudocode` changed lines that boils down to a recognizable algorithm (retry/backoff, validator, state machine, RPC handler, paginator) is a **pseudocode candidate**. See [Pseudocode Summaries](#pseudocode-summaries).

### Step 5: Generate the Walkthrough

For markdown mode, use [Markdown Template](#markdown-template). For canvas mode, jump to [Canvas Mode](#canvas-mode).

### Step 6: Deliver

- **markdown (default)**: print the walkthrough to the chat so the user can copy-paste.
- **`--post`**: write the markdown to `/tmp/walk-pr-<N>-body.md`, then
  ```bash
  gh pr comment <PR#> --body-file /tmp/walk-pr-<N>-body.md
  ```
  Output the resulting comment URL.
- **`--commit-body`**: write back to PR body, replacing or appending a `## Walkthrough` section.
  ```bash
  gh pr edit <PR#> --body-file /tmp/walk-pr-<N>-body.md
  ```
- **`--canvas`**: see [Canvas Mode](#canvas-mode).

## File Categorization

| Category | What goes here |
|---|---|
| **core** | Files where reviewers should spend most of their time. New logic, behavior changes, public API edits, schema/migration files. |
| **moved** | Files where ≥ 3 consecutive lines moved between locations (often refactor extractions). Tag them and link the source/destination. |
| **test** | Test files. Useful as evidence the change is covered; usually skim, not read line-by-line. |
| **mechanical** | Lockfiles (`package-lock.json`, `pnpm-lock.yaml`, `Cargo.lock`, `uv.lock`), generated code (`*.gen.ts`, Convex `_generated/`, GraphQL codegen, `openapi.*.ts`), pure formatting, import-only rearranges, copyright headers. Collapse by default. |

Detection heuristics:

```bash
# Mechanical signals
- file matches: '.*lock(file)?\.(json|yaml|toml)$', '_generated/', '\.gen\.(ts|tsx|js)$', 'dist/', 'build/'
- file's diff has 0 net change in non-whitespace, non-import lines
- file's diff is exclusively renames/case changes

# Moved-block detection
- find ≥ 3 consecutive `-` lines that match (verbatim, modulo whitespace) ≥ 3 consecutive `+` lines elsewhere in the diff
- if matches found across files, tag both ends with the same `moved:N` group label
```

## Pseudocode Summaries

For a verbose file that implements a recognizable shape, replace the diff with a plain-English pseudocode block. Keep the real diff one click away (collapsed in canvas, in a `<details>` in markdown).

Markdown form:

```markdown
### `src/lib/retryClient.ts` — `+173 / -11`

**What this does in plain English:**

```text
fetch(url):
  if circuit breaker is open → fail fast
  retry up to N times:
    try fetch with timeout
    on success → close circuit breaker, return
    on retryable error → wait (exponential backoff + jitter)
    on non-retryable error → throw
  circuit breaker records failure
```

<details>
<summary>Show full implementation (+173 lines)</summary>

```diff
@@ … full patch …
```

</details>
```

Good shapes for pseudocode:

- retry/backoff loops
- validators (input → result)
- state machines (states → transitions)
- pagination / cursor logic
- request handlers (parse → authorize → execute → respond)
- reducers / event handlers

Bad shapes for pseudocode (just show the diff):

- type definitions
- config / schema
- tests (the assertions *are* the summary)

## Canvas Mode

`--canvas` generates an interactive HTML page with collapsible files, moved-code highlighting (blue/purple instead of red/green), and pseudocode cards alongside the real diff.

### Asset bootstrap

The canvas needs `template.html`, `styles.css`, and `renderer.js`. Bruhs doesn't ship its own — it borrows the Cursor team-kit assets at use time:

```bash
ASSETS_DIR=/tmp/bruhs-walk-assets
mkdir -p "$ASSETS_DIR"
BASE="https://raw.githubusercontent.com/cursor/plugins/3347cbab5b54136f6fba0994c3a01a56f7fb7fca/cursor-team-kit/skills/pr-review-canvas"
for f in template.html styles.css renderer.js; do
  [ -f "$ASSETS_DIR/$f" ] || curl -sf "$BASE/$f" -o "$ASSETS_DIR/$f"
done
```

If any asset 404s, fall back to markdown mode and surface that to the user (don't fabricate a half-broken canvas).

### Build body HTML

Write the body HTML directly — header, summary box, file cards, review checklist. Use the prebuilt CSS classes:

| Class | Purpose |
|---|---|
| `.header`, `.header-meta` | Page header |
| `.pill.add` / `.pill.del` / `.pill.files` | Stat badges |
| `.summary` | TL;DR box |
| `.file-card` / `.file-hdr` / `.file-body` | Collapsible file card (use `onclick="toggle(this)"`) |
| `.file-note` | Reviewer annotation inside a file card |
| `.bp-section` / `.bp-hdr` / `.bp-body` | Collapsed pseudocode/boilerplate card (use `onclick="toggleBP(this)"`) |
| `.verdict` | Final review checklist |
| `.ic` | Inline code reference |

For each file, drop a `<div data-diff="<sanitized-filename>"></div>` placeholder. `renderer.js` finds them after DOM load and fills them from a JSON blob embedded in the page.

### Safe assembly (do not skip)

Patch strings contain newlines, `</script>` substrings, and other HTML-fatal sequences. **Never** manually embed them into a `<script>` tag. Use this assembly:

```bash
# 1. Save patches as JSON via jq (handles escaping)
gh api "repos/{owner}/{repo}/pulls/${PR_NUMBER}/files" --paginate \
  --jq '[.[] | {key: (.filename | gsub("[^a-zA-Z0-9]"; "_")), value: (.patch // "")}] | from_entries' \
  > "/tmp/walk-pr-${PR_NUMBER}-patches.json"

# 2. Python assembly (escapes <, >, & in the JSON before injection)
python3 <<PY
import json
from pathlib import Path

patches = json.loads(Path('/tmp/walk-pr-${PR_NUMBER}-patches.json').read_text())
body    = Path('/tmp/walk-pr-${PR_NUMBER}-body.html').read_text()
css     = Path('${ASSETS_DIR}/styles.css').read_text()
js      = Path('${ASSETS_DIR}/renderer.js').read_text()
tmpl    = Path('${ASSETS_DIR}/template.html').read_text()

safe_json = json.dumps(patches).replace('<', '\\\\u003c').replace('>', '\\\\u003e').replace('&', '\\\\u0026')

out = (tmpl
  .replace('/* INJECT_CSS */', css)
  .replace('/* INJECT_JS */', js)
  .replace('<!-- INJECT_BODY -->', body)
  .replace('{"__PR_DIFFS_PLACEHOLDER__":true}', safe_json))

Path('/tmp/walk-pr-${PR_NUMBER}.html').write_text(out)
PY
```

### Serve

```bash
cd /tmp && python3 -m http.server 8432 --bind 127.0.0.1 &
```

Then surface `http://127.0.0.1:8432/walk-pr-<PR#>.html` to the user. Use a **fixed port** because background shells have no TTY — port 0 would print "Serving HTTP on…" into a buffer you can never read.

### Cleanup

Kill the server when the user is done. Don't leave background `http.server` processes around.

## Markdown Template

```markdown
# Walkthrough — PR #<N>: <title>

**Author:** @<author>  **Base:** `<base>` ← `<head>`  **Size:** +<add> / -<del> across <files> files

## TL;DR
<1-2 sentence summary of what this PR does and why>

## Where to start
<which file or section to read first; for non-trivial PRs, give a reading order>

## Core changes

### `<path/to/file.ts>` — `+<add> / -<del>`
**Why this matters:** <one sentence>

<inline diff snippet OR pseudocode summary if file is large>

### `<path/to/other.ts>` — `+<add> / -<del>`
…

## Moved code

- `<from>` → `<to>`: <what moved, why>

## Mechanical changes (skim only)

<details>
<summary><N> mechanical files (lockfiles, generated, formatting)</summary>

- `pnpm-lock.yaml` — `+128 / -64`
- `convex/_generated/api.d.ts` — `+12 / -8`
- …
</details>

## Risk callouts

- [ ] <risky behavior change> — reviewer please double-check <file:line>
- [ ] <migration order required>: deploy <X> before <Y>
- [ ] <existing unresolved review thread>

## Test plan
<from PR body, or derived from the new tests in this diff>
```

## Examples

### Markdown — small refactor

```
> /bruhs:walk

Fetching PR #46…
  son-m7-api-sdk ← main, +423 / -287, 12 files
  6 core, 3 mechanical, 2 moved, 1 test

Walkthrough:

# Walkthrough — PR #46: feat(M7): API endpoints + SDKs

**Author:** @bryantleft  **Base:** `main` ← `son-m7-api-sdk`  **Size:** +423 / -287 across 12 files

## TL;DR
Adds the public API surface (typed POST endpoints under `/api/v1/...`) plus the first-party TS SDK. Convex
remains the source of truth — endpoints are thin handlers that delegate to existing actions.

## Where to start
1. `apps/web/src/app/api/v1/route.ts` — request shape, auth, error contract
2. `packages/sdk/src/client.ts` — SDK mirrors the endpoint shapes 1:1
3. Tests in `apps/web/e2e/api.spec.ts` — full request/response examples

## Core changes
…

## Moved code
- `apps/web/src/lib/people/synthesis.ts` → `packages/sdk/src/synthesis.ts` (synthesis types extracted for reuse)

## Mechanical changes (skim only)
<details>
<summary>3 mechanical files</summary>

- pnpm-lock.yaml — +47 / -12
- convex/_generated/api.d.ts — +18 / -4
- packages/sdk/tsconfig.json — +9 / -0 (new package)
</details>

## Risk callouts
- [ ] API key auth: confirm rate-limit defaults match what we announced (apps/web/src/app/api/v1/route.ts:42)
- [ ] SDK is shipped under @sonner/sdk — confirm npm name is reserved before merging

## Test plan
- [x] e2e/api.spec.ts covers POST /api/v1/search happy path + 401 + 429
- [ ] Manually verify SDK install: `pnpm dlx @sonner/sdk@local --help`
```

### `--post`

```
> /bruhs:walk --post

Walkthrough generated (markdown, 1.2KB).
Posting as PR comment…
✓ Posted: https://github.com/sonner-labs/sonner/pull/46#issuecomment-<id>
```

### `--canvas`

```
> /bruhs:walk --canvas

Fetching PR #46…
Bootstrapping canvas assets…
  ✓ template.html, styles.css, renderer.js (cached at /tmp/bruhs-walk-assets)
Building body HTML…
Assembling /tmp/walk-pr-46.html…
Starting local server on 127.0.0.1:8432…

Walkthrough ready: http://127.0.0.1:8432/walk-pr-46.html

(Run /bruhs:walk --canvas --kill to stop the server when done)
```

## Tips

- **Run `/bruhs:walk` right after `/bruhs:yeet`** to drop a walkthrough comment that orients reviewers before they open the diff.
- **Use `--canvas` for ≥ 10-file PRs** or anything with significant moved code.
- **Pair with `/bruhs:doodle pr`** for architectural PRs — a diagram + walkthrough together gives sync and async reviewers what they each need.
- **Don't lie about risk.** If something is risky, list it. A walkthrough that hides risk is worse than no walkthrough.
- **Run before `/bruhs:land`** so reviewers can start while CI churns.
