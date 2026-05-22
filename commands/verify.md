---
description: Verify a specific claim with fresh local evidence — restate it falsifiably, capture baseline and treatment, compare artifacts, return VERIFIED / NOT VERIFIED / INCONCLUSIVE. Use when asked to "verify", "prove it works", "show evidence", or after a fix lands.
---

# verify - Prove a Claim with Evidence

Verification is not a recap. It proves or disproves a **specific, falsifiable claim** with repeatable evidence. Sits between `cook` (build) and `yeet` (ship), or after `peep` (fix) when the user wants proof the fix actually fixed it.

## Contents

- [Invocation](#invocation)
- [When to Use vs Skip](#when-to-use-vs-skip)
- [Workflow](#workflow)
- [Local Surfaces](#local-surfaces)
- [Artifact Layout](#artifact-layout)
- [Verdict Rules](#verdict-rules)
- [Output Format](#output-format)
- [Examples](#examples)
- [Tips](#tips)

---

## Invocation

- `/bruhs:verify` — Verify the most recent change against an inferred claim (asks to confirm the claim first)
- `/bruhs:verify <claim>` — Verify the explicit claim, e.g. `/bruhs:verify "drawCard reshuffles when deck is empty"`
- `/bruhs:verify <PR#>` — Verify the claim in PR title/body
- `/bruhs:verify --keep-artifacts` — Persist baseline/treatment under `/tmp/verify-this/<slug>/` instead of inline-only evidence

## When to Use vs Skip

**Use when:**
- A bug fix needs a before/after repro.
- A UI / CLI / API / performance / memory claim needs measurement.
- A test passes but the **user-visible** behavior still needs confirmation.
- Reviewer asks "did this actually fix X?"

**Skip for:**
- Vague claims like "the code is cleaner" — ask the user for a measurable claim first.
- Pure refactors with no behavior delta — there is nothing to verify (suggest `/bruhs:slop` or `/bruhs:deepen` instead).
- Type-only changes where `tsc --noEmit` is sufficient evidence on its own.

## Workflow

### Step 1: Restate the Claim Falsifiably

Convert whatever the user said into the shape `condition → metric → threshold`. If you can't write it falsifiably, ask the user to refine it before proceeding.

Examples:

| Vague claim | Falsifiable form |
|---|---|
| "The fix works" | "When deck size is 0, `drawCard()` triggers reshuffle and returns a card (no `undefined`, no throw)" |
| "It's faster" | "Cold start of `gambit dev` drops by ≥ 20% on the same machine, same warmup" |
| "Memory leak gone" | "Heap size after 100 iterations of `evaluateHand()` does not grow by > 5MB" |
| "Toast renders correctly" | "Toast component renders with `data-state=open` and matches baseline screenshot at 1280×800" |

### Step 2: Pick the Smallest Local Surface

Choose the smallest harness that can disprove the claim:

- **Code behavior**: focused unit/integration test or minimal repro script
- **CLI / TUI**: tmux harness or PTY probe (see [Local Surfaces](#local-surfaces))
- **UI**: Playwright probe or CDP harness against the local dev server
- **API**: local HTTP/RPC request → response diff
- **Performance**: same-machine baseline/treatment timing with identical warmup
- **Memory**: heap snapshot before / heap snapshot after

### Step 3: Capture Baseline

Run the **old** state against the same harness. Source the baseline from whichever is closest to "before this change":

```bash
# Option A — merge-base of current branch and main
BASE=$(git merge-base HEAD origin/main)
git stash push -u -m "verify-treatment"
git switch --detach "$BASE"
# … run harness, capture artifact …

# Option B — the parent commit of the fix
BASE=$(git rev-parse HEAD~1)

# Option C — a known-broken state the user pointed at
BASE=<sha>
```

Record:
- exact command run
- the artifact (output, screenshot, timing, snapshot)
- environment (Node version, OS, env vars that matter)

### Step 4: Capture Treatment

Restore the changed state and re-run with the **same command, data, warmup, environment**:

```bash
git switch -    # switch back to the branch
git stash pop   # restore working tree if you stashed
# … run harness, capture artifact …
```

If anything but the code changed between baseline and treatment, the run is **invalid** — restart.

### Step 5: Compare

Compare raw artifacts side-by-side. Acceptable evidence forms:

- numeric diff (timing, memory, count)
- terminal transcript diff
- screenshot pixel/visual diff
- HTTP response body diff
- profile flamegraph delta
- test output: before fails, after passes

### Step 6: Return Verdict

Exactly one of: `VERIFIED`, `NOT VERIFIED`, `INCONCLUSIVE` — see [Verdict Rules](#verdict-rules). Do not soften a `NOT VERIFIED`.

## Local Surfaces

Reuse the repo's own test/demo harness if one exists. Otherwise assemble a temporary harness in `/tmp/` and clean it up after.

### CLI / TUI

Prefer tmux for managed sessions:

```bash
SESSION="verify-$(date +%s)"
tmux new-session -d -s "$SESSION" -- <command-under-test>
tmux capture-pane -pt "$SESSION" > /tmp/verify-baseline.txt
tmux send-keys -t "$SESSION" "<input>" Enter
# wait for a concrete screen pattern, not a sleep
tmux capture-pane -pt "$SESSION" > /tmp/verify-treatment.txt
tmux kill-session -t "$SESSION"
```

Fall back to a PTY probe (Python `pty` module) if tmux is unavailable. Prefer **deterministic waits on screen patterns** over `sleep`.

### UI

Reuse the project's Playwright/Cypress harness if present. Otherwise a minimal probe:

```javascript
import { chromium } from 'playwright'

const browser = await chromium.launch()
const page = await browser.newPage({ viewport: { width: 1280, height: 800 } })
await page.goto('http://127.0.0.1:<port>')
await page.getByRole('button', { name: /submit/i }).click()
await page.screenshot({ path: '/tmp/verify-after.png', fullPage: true })
await browser.close()
```

Do not add Playwright as a project dependency just for the probe — use what's already in `package.json`.

For Electron / Chromium apps launched with `--remote-debugging-port=<port>`, use `chromium.connectOverCDP('http://127.0.0.1:<port>')` and select the page by a stable app-root selector, **not** by tab order.

### Performance

```bash
# Baseline
hyperfine --warmup 3 --runs 10 -n baseline '<command>' > /tmp/verify-baseline.json --export-json /tmp/verify-baseline.json

# Treatment (after switching to changed state)
hyperfine --warmup 3 --runs 10 -n treatment '<command>' --export-json /tmp/verify-treatment.json
```

If `hyperfine` is unavailable, fall back to repeated `time` runs with identical warmup. **Same machine, no other heavy processes, same battery/AC state.**

### Memory

Force GC if available, take a heap snapshot, perform the suspected operation N times, force GC again, snapshot again. Compare retained size of the relevant constructor.

## Artifact Layout

When the user passes `--keep-artifacts` or the evidence is too large to inline:

```text
/tmp/verify-this/<claim-slug>/
├── claim.md           # falsifiable claim, hypothesis, threshold
├── timeline.md        # commands run, in order, with timestamps
├── baseline/          # raw artifacts from old state
├── treatment/         # raw artifacts from changed state
├── diff/              # computed deltas (numeric, image, text)
└── verdict.md         # final verdict + reasoning
```

If artifacts may contain sensitive code, prompts, screenshots, HTTP bodies, or heap data, keep evidence **inline-only** unless the user explicitly agrees to disk storage. Never write secrets, customer data, or auth tokens.

## Verdict Rules

| Verdict | When |
|---|---|
| `VERIFIED` | Baseline and treatment differ in the predicted direction, by the claimed threshold, with no obvious confound. |
| `NOT VERIFIED` | Behavior is unchanged, moves the wrong way, or misses the threshold. |
| `INCONCLUSIVE` | No valid baseline, noisy signal, failed measurement, or an environment difference invalidates the comparison. |

`INCONCLUSIVE` is not a polite `NOT VERIFIED`. Use it only when the measurement itself failed, not when the result was bad.

## Output Format

```text
VERIFIED | NOT VERIFIED | INCONCLUSIVE
Claim: <falsifiable claim>

Evidence:
<metric/artifact>: baseline=<value>, treatment=<value>, delta=<value>, threshold=<value>

Reasoning:
<one tight paragraph naming the evidence and any confounds>

Artifacts: <inline | /tmp/verify-this/<slug>/>
```

## Examples

### Bug fix — empty deck draw

```
> /bruhs:verify "drawCard reshuffles when deck is empty"

Restating claim…
  Condition: deck.length === 0
  Metric:    drawCard() return value
  Threshold: returns a Card (not undefined, no throw)

Baseline (HEAD~1)…
  Ran: node -e 'const g = require("./engine"); console.log(g.drawCard({deck:[],discard:[mkCard()]})) '
  Result: TypeError: Cannot read properties of undefined

Treatment (HEAD)…
  Same command
  Result: { suit: "spades", rank: "A", … }

VERIFIED
Claim: drawCard reshuffles when deck is empty
Evidence:
  return type: baseline=TypeError, treatment=Card, threshold=Card
Reasoning:
  Identical command on parent vs HEAD. Baseline threw on undefined; treatment returned a Card sourced
  from the shuffled discard. Unit test `drawCard.empty-deck.test.ts` added in this PR also passes; without
  the fix it fails with the same TypeError.
Artifacts: inline
```

### Performance — dev server cold start

```
> /bruhs:verify "gambit dev cold start drops by ≥20% on M2 Mac"

Baseline (origin/main)…
  hyperfine --warmup 3 --runs 10 'pnpm dev --port 3001' → mean 4.82s ± 0.14s

Treatment (HEAD)…
  Same command, same machine, AC power
  hyperfine result → mean 3.51s ± 0.11s

VERIFIED
Claim: gambit dev cold start drops by ≥20% on M2 Mac
Evidence:
  cold start (s): baseline=4.82, treatment=3.51, delta=-27.2%, threshold=-20%
Reasoning:
  Same machine, same warmup, no other load. Delta exceeds threshold by 7pp. Variance bands do not overlap.
Artifacts: /tmp/verify-this/gambit-dev-cold-start/
```

### UI — toast renders

```
> /bruhs:verify "toast renders with data-state=open at 1280×800"

Local dev server already running at :3000.

Baseline (parent)…
  page.locator('[data-sonner-toast]').getAttribute('data-state') → null
  Screenshot: /tmp/verify-this/toast-render/baseline/toast-1280x800.png

Treatment (HEAD)…
  Same flow
  data-state → "open"
  Screenshot: /tmp/verify-this/toast-render/treatment/toast-1280x800.png
  Visual diff: 14% pixels changed in toast region, 0% elsewhere

VERIFIED
Claim: toast renders with data-state=open at 1280×800
Artifacts: /tmp/verify-this/toast-render/
```

### Inconclusive — flaky bench

```
> /bruhs:verify "json parser throughput up 2x"

Baseline runs: 134ms, 612ms, 145ms, 138ms, 590ms
Treatment runs: 71ms, 73ms, 502ms, 70ms, 488ms

INCONCLUSIVE
Claim: json parser throughput up 2x
Evidence:
  Both runs show bimodal distribution (cold cache vs warm). Variance > effect size.
Reasoning:
  Cannot disprove the claim — treatment looks faster, but the cold-cache outliers dominate. Re-run with
  --warmup 10 and a fixed dataset path to remove the cache confound.
Artifacts: /tmp/verify-this/json-parser-throughput/
```

## Tips

- **Always restate the claim first.** A vague claim is the #1 reason verification fails.
- **Same command, same data, same machine, same warmup.** Anything else means INCONCLUSIVE.
- **Prefer deterministic waits over `sleep`.** Sleep makes verification flaky and unreproducible.
- **Don't soften a NOT VERIFIED.** A clear no is more useful than a hedged maybe.
- **Pair with `/bruhs:peep`** when verifying a review-comment fix actually closed the issue.
- **Pair with `/bruhs:yeet`** to attach the verdict to the PR body's `## Test plan` section as proof.
