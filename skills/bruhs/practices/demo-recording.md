# Demo Recording

How to record a browser demo a reviewer can actually read: captured at the right
resolution, with a cursor (or touch indicators) that moves like a person, and a camera
that zooms in on what each step touches. `scripts/record_demo.mjs` does the work
locally. You write a short shot list, the script drives Chromium with Playwright and
renders an MP4.

Used by `/bruhs:walk --video` (demo footage), `/bruhs:verify --keep-artifacts` (UI
evidence) and `practices/ui-preview.md` (the PR's recording).

## Contents

- [What it fixes](#what-it-fixes)
- [Workflow](#workflow)
- [Shot list](#shot-list)
- [Steps](#steps)
- [Targets](#targets)
- [Resolution](#resolution)
- [Camera](#camera)
- [Cursor and touch](#cursor-and-touch)
- [Privacy](#privacy)
- [Output](#output)
- [Rules](#rules)

## What it fixes

| A raw `recordVideo` / screen grab | `record_demo.mjs` |
|---|---|
| Captures CSS pixels: a 2x viewport records at half resolution, text is soft | Captures device pixels (viewport × scale) with `--force-device-scale-factor`, so a 1280×720 page records at 2560×1440 |
| No cursor, or the cursor teleports | A drawn cursor travels a curved, eased path timed by Fitts' law, settles, then presses. It shows a hand over links and buttons and an I-beam over text. Each click gets a ripple |
| Mobile clicks look like nothing happened | Touch devices get touch indicators: a dot on tap, a dragging dot for swipes and scrolls. No mouse cursor |
| A 13" layout shrunk into a video: the change is 20 px tall | The camera zooms in on each action's element, pans between nearby ones and zooms out before scrolls and page loads |
| Keyboard shortcuts are invisible | `press` steps show a key chip (`⌘ K`, `↵ Enter`) |
| Jump cuts when a target is off-screen | Targets off-screen are scrolled into view with a visible scroll |
| Selectors drift, re-recording is manual | The shot list is deterministic Playwright locators: fix the code, re-run the same file |

Everything runs on this machine. No API keys, no cloud browser, no LLM in the loop:
you are the planner, the script is the hands and the camera.

## Workflow

```bash
DEMO="$(git rev-parse --absolute-git-dir)/bruhs/demo/<slug>"   # under .git/: never committed
mkdir -p "$DEMO"

# 1. Look at the page the way the script will see it
node <SKILL_DIR>/scripts/record_demo.mjs observe http://127.0.0.1:<port>/<route> [--device mobile]

# 2. Write $DEMO/shots.json from the snapshot (roles and names → targets)

# 3. Check, then record
node <SKILL_DIR>/scripts/record_demo.mjs check  "$DEMO/shots.json"
node <SKILL_DIR>/scripts/record_demo.mjs record "$DEMO/shots.json" --out "$DEMO"
```

`observe` prints the page's accessibility snapshot (`button "Save limit"`,
`textbox "Email"`). Write targets from it rather than guessing CSS. `observe
shots.json --steps` runs the steps first, to see the page mid-flow.

`record` exits 4 when a step fails. It names the step, saves
`failed-step-N.png` and prints what the page shows at that moment. Fix the shot
list (or the bug it found) and re-run. Never loosen a step until it passes on a
broken page: a recording of a UI that doesn't work is a hallucinated demo.

Needs Playwright with Chromium (the project's, or `npm i -g playwright && npx
playwright install chromium`) and ffmpeg with libx264. Exit 3 names what is missing.
`BRUHS_CHROMIUM` points it at another Chrome binary.

## Shot list

```json
{
  "url": "http://127.0.0.1:3000/settings/quota",
  "device": "desktop",
  "redact": ["[data-sensitive]", ".api-key"],
  "setup": [
    {"goto": "/login"},
    {"type": {"label": "Email"}, "text": "demo@example.com"},
    {"click": {"role": "button", "name": "Sign in"}},
    {"goto": "/settings/quota"}
  ],
  "steps": [
    {"mark": "set the limit"},
    {"type": {"label": "Requests per minute"}, "text": "250", "clear": true},
    {"select": {"label": "Applies to"}, "value": "fleet"},
    {"click": {"role": "button", "name": "Save limit"}},
    {"waitFor": {"text": "Saved"}},
    {"zoom": {"role": "status"}, "hold": 1500},
    {"press": "Meta+K"},
    {"scroll": 700}
  ]
}
```

| Key | Meaning | Default |
|---|---|---|
| `url` | Absolute URL the recording starts on | required |
| `device` | `desktop`, `mobile` (iPhone 15) or any Playwright device name (`"Pixel 7"`, `"iPad Pro 11"`) | `desktop` |
| `viewport` | `{"width", "height"}` in CSS px, overrides the device | 1280×720 desktop |
| `scale` | Device pixel ratio, 1–4 | 2 desktop, the device's own otherwise |
| `colorScheme` | `light` or `dark` | the browser's |
| `storageState` | Playwright storage state file (a logged-in session), relative to the shot list | none |
| `setup` | Steps run before recording starts: log in, seed data, open the right page | none |
| `steps` | What the video shows | required |
| `redact` | CSS selectors blurred in every frame and hidden from snapshots | none |
| `output` | `{"size": "1920x1080", "fps": 60, "padding": 0.06, "background": "#16181d"}` | 1920×1080 desktop, 1080×1920 portrait devices, 60 fps |
| `zoom` | `false`, or `{"auto": true, "max": 1.6}` | auto, max 1.6 desktop / 1.5 touch |
| `cursor` | `{"size": 1, "speed": 1, "click": "#3b82f6", "hidden": false}` | as shown |
| `scrollbars` | `true` keeps scrollbars visible | hidden |
| `seed` | Integer for the small randomness in paths and typing rhythm | 7 |

Keep it short: one behavior, 5–20 seconds. `check` estimates the length.

## Steps

One action per step. Every step also takes `pause` (ms after it, default 450),
`camera` (`false` to not zoom for it, or `{"scale": 2}`), `timeout` (ms, default
10000) and `note` (ignored; for you).

| Step | Does |
|---|---|
| `{"goto": "/path"}` | Navigate (relative to the current page). The camera zooms out |
| `{"click": T}` | Move to T, settle, click. On touch devices it taps |
| `{"tap": T}` | Same as click; reads better in mobile shot lists |
| `{"type": T, "text": "…", "clear": true, "delay": 55}` | Click T, then type with a human rhythm. `"type": null` types into whatever has focus |
| `{"press": "Meta+K"}` | Press a key or chord and show a key chip. Playwright key names |
| `{"hover": T}` | Move to T and rest (menus, tooltips). Nothing on touch |
| `{"select": T, "value": "fleet"}` | Click a `<select>` and choose by value or label. Native popups never reach the video, so the choice appears directly |
| `{"scroll": 600}` | Scroll by px (positive = down) as a smooth wheel or touch gesture. `"within": T` scrolls that container |
| `{"scroll": T}` | Scroll until T is in view |
| `{"swipe": T, "direction": "left", "distance": 240}` | Touch swipe across T (a mouse drag on desktop) |
| `{"drag": T, "to": T2}` | Press on T, carry to T2, release |
| `{"waitFor": T}` | Wait until T is visible. Use instead of fixed waits |
| `{"wait": 800}` | A fixed beat, e.g. to let an animation finish on camera |
| `{"zoom": T, "scale": 2, "hold": 2000}` | Push in on a detail and hold it (hold counts from when the camera arrives). `scale` defaults to fitting T |
| `{"zoom": "out"}` | Pull back to the full page now |
| `{"mark": "label"}` | A chapter: its time lands in `manifest.json` for lining up narration |

## Targets

A target `T` is a Playwright selector string (`"#save"`, `"text=Save"`,
`"role=button[name='Save']"`) or an object with exactly one of:

```json
{"role": "button", "name": "Save limit"}
{"label": "Email"}
{"text": "Saved"}
{"placeholder": "Search"}
{"testId": "save-button"}
{"alt": "Logo"} {"title": "Close"} {"css": ".toast"}
```

Add `"exact": true` for exact text, `"nth": 1` for the second match. Prefer role and
label: they survive styling changes and match what `observe` prints. The first match is
used when several elements match.

Playwright's own actionability checks run before every click and tap, so a target
covered by an overlay or disabled fails the step instead of clicking whatever is on
top.

## Resolution

The capture is `viewport × scale` device pixels. The video frame shows the page at
`content width` output pixels, and a zoom of Z shows `1/Z` of it. Detail stays sharp
while each output pixel gets at least 0.8 captured pixels:

```
capture width / zoom / content width ≥ 0.8
```

The desktop defaults hold that: 2560 / 1.6 / 1920 = 0.83. `check` warns when a shot
list breaks it (a big explicit zoom, a low scale, a large output) and says what scale
would fix it. `record` warns again with the zooms it actually made. Don't ignore it:
raise `scale`, lower the zoom, or lower `output.size`.

Other rules:

- **Match the viewport to how people use the page.** 1280×720 is a laptop browser.
  Don't record a 1920-wide viewport to fill a 1920 video: everything gets small.
- **Match aspect ratios or accept the frame.** When the viewport's aspect differs from
  the output's, the page sits on a background with rounded corners and a shadow (phone
  recordings look like a device). Set `output.size` to the viewport's aspect for edge
  to edge.
- **Portrait for phones.** A phone demo defaults to 1080×1920. For a landscape PR
  walkthrough, record at `"output": {"size": "1920x1080"}` and the phone is framed in
  the middle.

## Camera

Auto-zoom (on by default) treats each click, tap, type, hover, select, swipe and drag
as a focus on its element:

- Actions less than 1.6 s apart share a shot. If they fit in one framing, the camera
  holds it; otherwise it zooms to a typical element and pans between them.
- The camera arrives as the action happens and lingers 0.8 s after the last one.
- It zooms out before scrolls and navigations (the content under it moves) and
  for `{"zoom": "out"}`.
- Zooms under 1.15x are skipped: they read as wobble, not emphasis.
- Close shots cut straight across instead of out and back in.

Use `"camera": false` on steps whose element doesn't matter (a nav link), and
`zoom` steps for results: the toast, the updated number, the error message. A
demo that only zooms on buttons shows the cause and never the effect.

## Cursor and touch

- Desktop: an arrow that becomes a hand over `cursor: pointer` and links, and an I-beam
  over text fields. It moves on a curved path with a minimum-jerk speed profile (how
  hands reach), takes longer for far or small targets, settles before clicking and
  squeezes on press. The real mouse follows the same path, so hover states in the video
  are real.
- Touch devices (`device: "mobile"` or any device with `hasTouch`): no cursor. A
  translucent dot with a white ring shows each touch. Taps pop, swipes and scrolls drag
  the dot with a short trail.
- `cursor.size` scales the cursor, `cursor.speed` its travel (2 = twice as fast),
  `cursor.hidden` hides it.

## Privacy

Recordings travel: PR bodies, Slack, walkthrough videos. Before recording a page with
real data:

- Prefer seeded or demo data. Log in with a demo account in `setup`.
- `redact` every selector that shows a secret, token, email or customer data. It blurs
  pixels in every frame and the failure screenshot, and hides the text from snapshots.
  Text typed by a `type` step is not redacted: don't type real secrets in a demo.
- Watch the result before it goes anywhere. Look at `poster.png` and scrub the video.

## Output

`record` writes into `--out`:

| File | What |
|---|---|
| `demo.mp4` | H.264, 60 fps, `output.size` |
| `poster.png` | The final state at full capture resolution, for PR bodies and thumbnails |
| `manifest.json` | Capture and output sizes, duration, chapters (`mark` times), each step's start and end, zooms, interaction counts, warnings |

`--keep-work` keeps raw frames and the timeline under `work/` for debugging.

In a walk video, use the clip as a scene's visual. `"fill": true` shows it full-frame
with captions over it, so the zooms aren't wasted on a small box. Use a chapter's time
as `start` to begin the scene at that moment:

```json
{"kind": "change", "heading": "The limit in action",
 "visual": {"type": "video", "src": "../../demo/search-quota/demo.mp4", "start": 0.5, "fill": true},
 "narration": "An admin sets two hundred fifty a minute and saves it."}
```

## Rules

- **Verify first, then record.** The recording shows behavior that already passed
  verification. If a step fails, the demo found a bug or the shot list is wrong. Either
  way, don't post a video of it working.
- **Show cause and effect.** Every action that changes something is followed by a step
  that shows the change (`waitFor` + `zoom` on the result).
- **No dead air.** `waitFor` the thing, not `wait` a guess. Cut setup into `setup`.
- **Re-record, don't edit.** The shot list is the source. After a code change, re-run
  it. Keep it next to the walk script under `.git/bruhs/`.
