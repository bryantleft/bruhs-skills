# UI Preview — Verify, Capture, Embed

How to **prove a UI change works** and turn that proof into a reviewer-facing preview in the PR body. A UI claim ("the modal centers", "the button wraps on mobile") is not real until it has been driven in a browser and captured. Screenshots and a short screen recording are the hard evidence; the PR body is where reviewers see it.

**Used by:**
- `cook` — build-time visual verification before self-review
- `yeet` — produces the `## UI preview` section of the PR body
- `peep` — re-verify and re-capture after applying UI review fixes

## When this applies

Any diff that touches user-visible surface: components, pages, routes, styles/CSS, templates, emails, or assets. Skip for pure backend/config/test-only diffs.

## Step 1 — Verify with `/expect` (required)

Run the **`/expect`** skill against the change. It runs adversarial browser tests — it drives the UI through the **chrome-devtools** MCP and actively tries to break it (empty states, overflow, rapid clicks, bad input, mobile viewport). Prefer `/expect` over hand-rolling raw browser calls; it is the canonical UI-verification path.

```
/expect   # after the dev server is up, against the changed surface
```

If `/expect` finds breakage, fix it and re-run before capturing anything. **Never capture a preview of a UI you have not verified** — a pretty screenshot of a broken interaction is a hallucinated "it works".

## Step 2 — Capture screenshots + a recording

Capture against a **running dev server** (start it if needed; remember whether you started it so you can stop it). Capture at least desktop (1280×800) and mobile (390×844). When a meaningful baseline exists (the change modifies existing UI), capture **before** (stash or check out the base) and **after** so the PR can show both.

**Preferred — chrome-devtools MCP** (the tool `/expect` already uses). If connected, drive navigation + screenshots through it:

```javascript
// Detect: ToolSearch("select:mcp__chrome-devtools__take_screenshot")
// then navigate to the route and take_screenshot per viewport.
// Tools are prefixed mcp__chrome-devtools__* (navigate, set viewport, screenshot).
```

**Fallback — the project's Playwright** (do not add it as a dep just for this; use what's in `package.json`). This both screenshots and records the interaction as video in one session:

```javascript
import { chromium } from 'playwright'

const OUT = '/tmp/bruhs-ui-preview'
const browser = await chromium.launch()
// recordVideo on the context captures the whole session as .webm
const ctx = await browser.newContext({
  viewport: { width: 1280, height: 800 },
  recordVideo: { dir: `${OUT}/video`, size: { width: 1280, height: 800 } },
})
const page = await ctx.newPage()
await page.goto('http://127.0.0.1:<port>/<route>')
await page.screenshot({ path: `${OUT}/desktop.png`, fullPage: true })

// Drive the key interaction so the recording SHOWS the behavior, not a static page
await page.getByRole('button', { name: /ship it/i }).click()
await page.screenshot({ path: `${OUT}/desktop-after.png`, fullPage: true })

// Mobile viewport
await page.setViewportSize({ width: 390, height: 844 })
await page.screenshot({ path: `${OUT}/mobile.png`, fullPage: true })

await ctx.close()   // finalizes the .webm recording
await browser.close()
```

Verified-real capture flow (proven): `navigate → screenshot` produces a true PNG of the rendered page (e.g. `1280×720 PNG`, ~160 KB). If a screenshot comes back empty/0-byte or the navigate step errored, the capture is invalid — do not embed it.

## Step 3 — Embed in the PR body

Reviewers can only see media that is hosted; a local `/tmp` path renders as nothing. Two honest paths — pick based on whether you need a guaranteed inline **video player**:

**A. Fully automated (images render inline; video as a link).** Push the captured media to a dedicated, never-merged `bruhs-assets` branch and reference the raw URLs:

```bash
OWNER_REPO=$(gh repo view --json nameWithOwner -q .nameWithOwner)
BR=$(git branch --show-current)
DEST=".bruhs/pr-media/$BR"
tmp=$(mktemp -d)
git worktree add -q "$tmp" --orphan bruhs-assets 2>/dev/null || git worktree add -q "$tmp" bruhs-assets
mkdir -p "$tmp/$DEST" && cp /tmp/bruhs-ui-preview/*.png /tmp/bruhs-ui-preview/video/*.webm "$tmp/$DEST/"
( cd "$tmp" && git add -A && git commit -q -m "chore(pr-media): $BR" && git push -q origin bruhs-assets )
git worktree remove "$tmp"
# Raw URL pattern (images render inline in the PR body):
#   https://raw.githubusercontent.com/$OWNER_REPO/bruhs-assets/$DEST/desktop.png
```

**B. Guaranteed inline video player (one manual paste).** GitHub renders an inline `<video>` player **only** for files uploaded through its web composer (the `github.com/user-attachments/assets/...` domain) — this is not reachable from `gh`/CLI. So for a playable recording, print the saved file paths and a ready-to-paste block, and ask the user to drag the `.webm`/`.mp4` into the PR description. Be explicit that this one step is manual; do not claim a CLI upload yields an inline player when it does not.

### The `## UI preview` block to write into the PR body

```markdown
## UI preview

Verified with `/expect` (adversarial browser tests via chrome-devtools): <1-line result>.

**Desktop (1280×800)**
| Before | After |
|---|---|
| ![before](<raw-url-or-attachment>) | ![after](<raw-url-or-attachment>) |

**Mobile (390×844)**
![mobile](<raw-url-or-attachment>)

**Recording** — <interaction shown>
<!-- drag the .webm here for an inline player; file: /tmp/bruhs-ui-preview/video/<name>.webm -->
https://github.com/<owner>/<repo>/... (link or attachment)
```

## Rules

- **No preview without verification.** `/expect` must pass first. Capturing a broken UI as if it works is a hallucination.
- **Show behavior, not just a frame.** The recording must include the interaction the PR changes — a static screenshot is not a "video preview".
- **Be honest about hosting.** Images embed automatically; an inline video player requires the manual drag-drop. State which path you used and what (if anything) the user still needs to do.
- **Clean up.** Stop the dev server if you started it; remove `/tmp/bruhs-ui-preview` after the media is hosted/embedded.
