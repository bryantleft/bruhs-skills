---
description: Generate a reviewer walkthrough for a PR — markdown by default (postable as a PR comment), interactive HTML canvas or a narrated video (local voice) opt-in. Categorizes files into core vs mechanical, summarizes verbose code as pseudocode, surfaces risk and migration order. Use when posting a PR for review, or asked to "walk through this PR".
---

# walk - PR Reviewer Walkthrough

Generate a walkthrough that reads like a peer explaining the PR to a reviewer — what to look at first, what to skip, what's risky, where the moved code went. Default output is markdown (postable as a PR comment). `--canvas` swaps to an interactive HTML page with collapsible diffs and moved-code detection. `--video` renders a short narrated video (intent, change, implications, validation) with a local voice.

## Contents

- [Invocation](#invocation)
- [Output Modes](#output-modes)
- [Workflow](#workflow)
- [File Categorization](#file-categorization)
- [Pseudocode Summaries](#pseudocode-summaries)
- [Canvas Mode](#canvas-mode)
- [Video Mode](#video-mode)
  - [Demo footage](#demo-footage)
- [Examples](#examples)
- [Tips](#tips)

---

## Invocation

- `/bruhs:walk` — Walkthrough for the current branch's PR (markdown)
- `/bruhs:walk 42` — Walkthrough for PR #42
- `/bruhs:walk --canvas` — Interactive HTML page served locally
- `/bruhs:walk --post` — Post the markdown walkthrough as a PR comment
- `/bruhs:walk --commit-body` — Replace the PR body's "What changed" section with the walkthrough
- `/bruhs:walk --max-pseudocode N` — Apply a user-chosen changed-line threshold for pseudocode summaries
- `/bruhs:walk --video` — Narrated video walkthrough, rendered and voiced locally, for the author to watch first
- `/bruhs:walk --video --post` — After the author approves it, post the transcript comment and hand over the video to attach
- `/bruhs:walk --video --tts piper|say|espeak-ng|none` — Force a narration engine (default: best available)

## Output Modes

| Mode | When to use | Output |
|---|---|---|
| **markdown** (default) | Posting to PR comment, reviewer reads in GitHub UI, async review | Single markdown block, copy-pasteable |
| **canvas** (`--canvas`) | Synchronous walkthrough, complex diff with moved code, you want collapsible sections | Local HTML page served at `http://127.0.0.1:8432` |
| **post** (`--post`) | Auto-post the markdown as a `gh pr comment` so reviewers see it before the diff | Markdown + PR comment URL |
| **video** (`--video`) | The why and the implications matter as much as the diff: behavior changes, UI, a demo worth seeing, reviewers outside the code | `walkthrough.mp4` + captions + transcript, under `.git/bruhs/walk/pr-<N>/` |

Choose markdown when a linear reading order is clear. Use `--canvas` when the diff's
dependency shape, moved code, or migration order is materially easier to understand
spatially. Do not switch modes because of an arbitrary file count.

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

- What is this PR doing? Write the shortest TL;DR that preserves the behavior and why.
- Which files contain the **core logic**?
- Which files are **mechanical** (lockfiles, generated code, formatting, imports)?
- Are there **moved blocks** deleted in one location and added identically elsewhere?
- What's the **migration order** if the changes need to land in a specific sequence?
- Where's the **risk**? New code paths, dropped error handling, behavior changes hidden in refactors?

### Step 3: Categorize Files

See [File Categorization](#file-categorization). For each file decide: `core` | `mechanical` | `moved` | `test`.

### Step 4: Identify Pseudocode Candidates

Any file that is harder to review as a raw diff and boils down to a recognizable
algorithm (retry/backoff, validator, state machine, RPC handler, paginator) is a
**pseudocode candidate**. When the user supplied `--max-pseudocode`, also apply that
explicit threshold. See [Pseudocode Summaries](#pseudocode-summaries).

### Step 5: Generate the Walkthrough

For markdown mode, use [Markdown Template](#markdown-template). For canvas mode, jump to [Canvas Mode](#canvas-mode). For video mode, jump to [Video Mode](#video-mode).

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
- **`--video`**: see [Video Mode](#video-mode).

## File Categorization

| Category | What goes here |
|---|---|
| **core** | Files where reviewers should spend most of their time. New logic, behavior changes, public API edits, schema/migration files. |
| **moved** | Files with a meaningful verbatim block moved between locations (often refactor extractions). Tag them and link the source/destination. |
| **test** | Test files. Useful as evidence the change is covered; usually skim, not read line-by-line. |
| **mechanical** | Lockfiles (`package-lock.json`, `pnpm-lock.yaml`, `Cargo.lock`, `uv.lock`), generated code (`*.gen.ts`, Convex `_generated/`, GraphQL codegen, `openapi.*.ts`), pure formatting, import-only rearranges, copyright headers. Collapse by default. |

Detection heuristics:

```bash
# Mechanical signals
- file matches: '.*lock(file)?\.(json|yaml|toml)$', '_generated/', '\.gen\.(ts|tsx|js)$', 'dist/', 'build/'
- file's diff has 0 net change in non-whitespace, non-import lines
- file's diff is exclusively renames/case changes

# Moved-block detection
- find consecutive `-` lines that match (verbatim, modulo whitespace) consecutive `+` lines elsewhere in the diff
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

## Video Mode

`--video` turns the walkthrough into a narrated video of about 45–90 seconds, scaled to
the change (a small fix can be 20). It explains **why** the PR exists, **what** it
changes, **what that affects**, and **how we know** it works. The demo is
evidence, not the whole video. Everything renders on this machine. The voice is a local
text-to-speech model, and nothing leaves the machine until the author posts.

Two audiences, in this order:

1. **The author** watches first. It checks whether the agent built what they meant and
   explains it the way they would. Never post before the author approves.
2. **Reviewers** watch it before opening the diff. The transcript comment keeps it
   skimmable and searchable.

### Step V1: Read the PR and collect receipts

Do Steps 1–4 above. Then collect evidence for the validation scene. A **receipt** is
something that ran and that you can point at:

- `gh pr checks <N>` results (name + state)
- test, typecheck or benchmark output you ran in this session (command + result line)
- `/bruhs:verify` verdicts and artifacts under `/tmp/verify-this/<slug>/`: their
  screenshots and recordings are the best demo footage

A checked box in the PR body is the author's claim, not a receipt. If the PR body says
"tested locally" and nothing here shows it, the claim is `unchecked`. When a demo would
help and there is no artifact, run `/bruhs:verify --keep-artifacts` first, or record
one with `scripts/record_demo.mjs` (see [Demo footage](#demo-footage)), or say the
video has no demo. Artifacts can hold secrets, customer data or tokens. Look at every
image and clip before it goes in the video.

### Demo footage

When the change is visible in a browser, record the demo with the bruhs recorder
rather than a raw screen grab:

```bash
DEMO="$(git rev-parse --absolute-git-dir)/bruhs/demo/<slug>"
node <SKILL_DIR>/scripts/record_demo.mjs observe http://127.0.0.1:<port>/<route>
node <SKILL_DIR>/scripts/record_demo.mjs check  "$DEMO/shots.json"
node <SKILL_DIR>/scripts/record_demo.mjs record "$DEMO/shots.json" --out "$DEMO"
```

It records at device pixels, draws a cursor that moves like a hand (touch indicators on
a mobile device), zooms in on the element each step touches, and blurs `redact`
selectors. Add a `{"zoom": T}` step on the result of the change, not only the button
that causes it. Put `{"mark": "…"}` steps where the narration turns; their times in
`manifest.json` are the `start` values for the scenes that use the clip. The shot list
format is in `practices/demo-recording.md`.

### Step V2: Write the script

```bash
OUT="$(git rev-parse --absolute-git-dir)/bruhs/walk/pr-<N>"   # under .git/: never committed
mkdir -p "$OUT"
```

Write `$OUT/script.json`. Scenes run **intent → change → implications → validation**.
The first is intent, the last is the single validation scene, and implications is
optional for a trivial change.

```json
{
  "pr": {"number": 42, "title": "feat(api): rate-limit /v1/search per client",
         "base": "main", "head": "feat/api-rate-limit", "additions": 74, "deletions": 9, "files": 8},
  "scenes": [
    {"kind": "intent", "heading": "Enforce the search quota", "visual": {"type": "title"},
     "narration": "Our docs promise partners a hundred searches a minute. Nothing enforced it."},
    {"kind": "change", "heading": "A fixed window per client",
     "visual": {"type": "diff", "path": "src/server.ts", "text": "@@ -14,6 +16,9 @@\n+    if (!decision.allowed) {\n+      return send(res, 429, …);\n+    }"},
     "narration": "Every request after the hundredth in a minute gets a four twenty nine."},
    {"kind": "change", "heading": "The limit in action",
     "visual": {"type": "video", "src": "/tmp/verify-this/search-quota/treatment/demo.mp4", "fill": true},
     "narration": "Here the hundred and first request is refused."},
    {"kind": "implications", "heading": "Per process, not per fleet",
     "visual": {"type": "points", "items": ["3 replicas: a client can get up to 3x the quota", "Old keys are never evicted"]},
     "narration": "Counters live in each process. With three replicas a client can get three times the quota."},
    {"kind": "validation", "heading": "What was checked", "visual": {"type": "claims"},
     "claims": [
       {"text": "Limiter allows the quota, then refuses", "status": "shown", "receipt": "npm test: 2 passed, 0 failed"},
       {"text": "The quota holds across replicas", "status": "intended"},
       {"text": "Behavior under a real partner load", "status": "unchecked"}],
     "narration": "The limiter's tests pass and the burst was refused locally. Sharing the counters across replicas is still to do."}
  ]
}
```

| Visual | Use it for |
|---|---|
| `title` | The intent scene: PR title, branch and size from `pr` |
| `points` | Implications and tradeoffs: a few short items |
| `code` / `diff` | The lines the narration talks about (`path`, optional `start_line`). A diff colors `+`, `-` and `@@` lines |
| `image` / `video` | Screenshots and recordings from verify, `record_demo.mjs` or a manual demo (`src`, relative to the script). A clip shorter than the narration holds its last frame. `start` skips into it. `"fill": true` shows it full-frame under the captions instead of in the slide's content box: use it for recordings, whose detail is lost at a third of the frame |
| `claims` | The validation scene, always: every claim as **shown**, **intended** or **not checked** |

**Narration rules:**

- **It is spoken.** Write it the way you'd say it: "four twenty nine", "three
  replicas", "the client key helper". No backticks, paths or symbols. The slide shows those.
- **Lead with the why.** The intent scene says what was wrong or missing and for whom,
  before any code.
- **Never narrate a result you can't point at.** Every measured or demonstrated claim
  in the narration must be a `shown` claim with a receipt. Say intent as intent
  ("this should…", "the goal is…"). Don't turn "we expect it to be faster" into "it's faster".
- **Implications come from the risk callouts.** Cover who is affected, compatibility,
  migration order, tradeoffs and known limits. A video that hides risk is worse than none.
- **Keep it short.** Use two or three sentences per scene and only the scenes the change
  needs. Captions are timed per sentence, so short sentences read best.

### Step V3: Check and render

```bash
python3 <SKILL_DIR>/scripts/walk_video.py check  "$OUT/script.json"
python3 <SKILL_DIR>/scripts/walk_video.py render "$OUT/script.json" --out "$OUT" [--tts <engine>]
```

`check` lists every problem at once. Typical ones are a shown claim with no receipt,
scenes out of order, or code that doesn't fit the slide. Fix the script; never loosen a
claim's status to get past an error. `render` writes `walkthrough.mp4` (1920x1080,
captions burned in), `captions.srt`, `transcript.md` and `manifest.json`, then prints
the manifest.

**Narration engines.** `auto` picks the first available:

| Engine | What it is | When |
|---|---|---|
| `piper` | Local neural voice model (one ~60 MB download) | Default once installed |
| `say` | macOS built-in voice | macOS without piper |
| `espeak-ng` | Robotic but local | Linux without piper |
| `none` | Silent video, captions only | Nothing else available, or `--tts none` |

When `auto` falls back, the render warns. Pass that warning on to the user along with
the one-time piper setup:

```bash
uv tool install piper-tts                                        # or: pipx install piper-tts
mkdir -p ~/.local/share/bruhs/voices
uvx --from piper-tts python -m piper.download_voices \
  --data-dir ~/.local/share/bruhs/voices en_US-lessac-medium     # any piper voice works
```

`walk_video.py engines` shows what's installed. `--voice <file.onnx>` or
`BRUHS_PIPER_VOICE` picks a specific piper voice, and `--say-voice <name>` picks a
macOS voice. Use the same voice every time, so walkthroughs sound consistent across PRs.

If ffmpeg (with libass) is missing, the script exits 3 and says how to install it. Tell
the user; don't fall back to a markdown walkthrough without saying so.

### Step V4: The author watches it

Show the author the video and the transcript (`open "$OUT/walkthrough.mp4"` on macOS;
otherwise give the path), then ask:

```javascript
AskUserQuestion({
  questions: [{
    question: "Does the walkthrough say what you meant this PR to do?",
    header: "Video",
    multiSelect: false,
    options: [
      { label: "Post it", description: "Post the transcript as a PR comment; you attach the video" },
      { label: "Change it", description: "Tell me what's off; I'll edit the script and re-render" },
      { label: "Keep it local", description: "Don't post anything" }
    ]
  }]
})
```

On "Change it", edit `script.json` and re-render. Rendering takes seconds. Don't post
until the author picks "Post it", even when `--post` was passed.

### Step V5: Post

```bash
gh pr comment <N> --body-file "$OUT/transcript.md"
open -R "$OUT/walkthrough.mp4"   # macOS: reveal the file for dragging
```

GitHub has no API for uploading video to a comment. Say so plainly: the author edits
the new comment and drags `walkthrough.mp4` onto the `_Video: …_` line, and GitHub
plays it inline. Give the comment URL and the file path. The transcript says the
narration was synthesized on the author's machine; keep that line.

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

### `--video`

```
> /bruhs:walk --video

Fetching PR #42…
  feat/api-rate-limit ← main, +74 / -9, 8 files
Receipts: gh pr checks (3 passing), npm test (2 passed), /tmp/verify-this/search-quota/
Writing .git/bruhs/walk/pr-42/script.json (5 scenes)…
  check: ok, ~58s estimated
Rendering with piper (en_US-lessac-medium)…
  ✓ .git/bruhs/walk/pr-42/walkthrough.mp4 (0:56)

Opened the video. Transcript: .git/bruhs/walk/pr-42/transcript.md
Shown: limiter tests, local burst refused. Intended: quota across replicas. Not checked: partner load.
Does the walkthrough say what you meant this PR to do?
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
- **Run `/bruhs:verify --keep-artifacts` before `--video`** when the change has visible behavior. Its screenshots and recordings are the demo footage, and its verdict is a receipt.
- **Record demos with `record_demo.mjs`, show them with `"fill": true`.** The zooms are what make a 1080p walkthrough readable; a full-page recording in a slide box is not.
