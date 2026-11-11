# UI Design Best Practices

Integrates [pbakaus/impeccable](https://github.com/pbakaus/impeccable)
skills and Emil Kowalski-derived design-engineering guidance into the bruhs
workflow for high-quality UI work.

**Used by:**
- `cook` - Invoked automatically when building UI features
- `slop` - Can audit UI quality (runs the Live Browser Pass for UI targets)

## Contents

- [When to Apply](#when-to-apply)
- [Skill Categories](#skill-categories)
- [Live Browser Pass (audit + improve)](#live-browser-pass-audit--improve)
- [Design Engineering Reference](#design-engineering-reference)
- [Cook Integration](#cook-integration)
- [Skill Selection Quick Reference](#skill-selection-quick-reference)
- [Quick Checklist](#quick-checklist)

---

## When to Apply

These practices activate when a feature involves **visible UI changes** — new pages, components, layouts, forms, modals, onboarding flows, etc. Skip for pure backend/API/infra work.

---

## Live Browser Pass (audit + improve)

Every UI **audit** or **improve existing UI** task runs this pass against the
real app. Static review (`critique`, `audit`, reading the CSS) finds candidates;
this pass finds what actually breaks. The standing instruction is:

> Test this in the browser at different widths, with touch emulation, and on a
> throttled 3G connection. Fix anything that looks broken or feels off. Save a
> before and after screenshot for every fix and send me a summary afterwards.

Treat that as the task prompt whenever the user asks to audit, review, polish,
or improve UI, and as the closing check of `cook` Step 6 for visible changes.
Do it in a real browser (chrome-devtools MCP, agent-browser, or the project's
Playwright; see `practices/ui-preview.md` for the tool order). Reading code is
not testing it.

### 1. Sweep the matrix

Start the dev server (note whether you started it, so you can stop it). For each
changed or audited route, check every cell:

| Axis | Values |
|------|--------|
| Width | 320, 390, 768, 1024, 1280, 1920 (also any breakpoint the project's CSS defines, and ±1px either side of it) |
| Input | mouse/hover, plus touch emulation (`hasTouch`, `isMobile`, coarse pointer, no hover) at the phone and tablet widths |
| Network | unthrottled, plus throttled 3G (~400 kbps down/up, 400 ms RTT), cache disabled, on first load and on every interaction that fetches |

Look for:
- **Looks broken:** horizontal scroll, overflow and clipped text, overlapping
  or misaligned elements, layout jumps (CLS), unreadable contrast, images
  missing or stretched, a sticky or fixed element covering content.
- **Feels off:** hover-only affordances with no touch path, touch targets under
  44px, tap delay, a missing pressed state, scroll-jacking, janky or long
  motion. On 3G: blank screens with no skeleton or spinner, buttons that can be
  double-submitted, spinners with no timeout or error, late fonts or images
  shifting the layout, interactions that block on large bundles.

Also check the browser console and failed network requests in each cell.

### 2. Fix, with before/after proof

For each issue, in turn:
1. Screenshot the **before** at the exact cell (width + input + network) that
   shows it.
2. Fix the root cause in the code, not a one-off override for that width.
3. Reload the same cell and screenshot the **after**. Then re-check the other
   widths so the fix did not break them.

Save the pairs as
`/tmp/bruhs-ui-audit/<NN>-<slug>-{before,after}-<width>[-touch][-3g].png`.
A fix with no matching before/after pair does not count as done. If a capture
comes back empty or the page errored, retake it.

### 3. Send the summary

When the sweep is done, send the user a summary (with the screenshots attached
or linked, when the surface supports it):

```markdown
## UI browser pass: <route(s)>

Tested: widths 320–1920, touch emulation, throttled 3G (cache off).

| # | Issue | Where (width / input / network) | Fix | Before | After |
|---|-------|---------------------------------|-----|--------|-------|
| 1 | Nav overflows, causes horizontal scroll | 320 / touch | Wrap nav items, `min-width: 0` on flex child | 01-nav-before-320-touch.png | 01-nav-after-320-touch.png |

**Left as is:** <issues found but not fixed, and why>
**Not tested:** <cells skipped, and why>
```

Keep it honest. List what you could not reproduce or chose not to fix. Never
say a cell "looks fine" without having loaded it.

### Playwright reference (fallback driver)

```javascript
import { chromium, devices } from 'playwright'

const browser = await chromium.launch()
// Touch emulation: a phone profile sets hasTouch, isMobile, a coarse pointer and the UA
const ctx = await browser.newContext({ ...devices['iPhone 13'] })
const page = await ctx.newPage()

// Throttled 3G via CDP (Chromium only)
const cdp = await ctx.newCDPSession(page)
await cdp.send('Network.enable')
await cdp.send('Network.setCacheDisabled', { cacheDisabled: true })
await cdp.send('Network.emulateNetworkConditions', {
  offline: false, latency: 400,
  downloadThroughput: (400 * 1024) / 8, uploadThroughput: (400 * 1024) / 8,
})

await page.goto('http://127.0.0.1:<port>/<route>')
await page.screenshot({ path: '/tmp/bruhs-ui-audit/01-nav-before-390-touch-3g.png', fullPage: true })

// Width sweep (desktop context, no touch)
const desk = await browser.newContext()
const dp = await desk.newPage()
for (const w of [320, 768, 1024, 1280, 1920]) {
  await dp.setViewportSize({ width: w, height: 900 })
  await dp.goto('http://127.0.0.1:<port>/<route>')
  const overflow = await dp.evaluate(() => document.documentElement.scrollWidth > innerWidth)
  // overflow === true → horizontal scroll bug at this width
}
await browser.close()
```

---

## Design Engineering Reference

Read `practices/design-engineering.md` whenever the UI work includes:

- New visible surfaces or component polish where defaults, perceived quality, or
  interaction feel matter.
- Motion, transitions, animation review, gestures, hover/press feedback, toasts,
  popovers, drawers, tooltips, tabs, or loading states.
- A user asks what an animation/effect is called.

This reference incorporates Emil's design-engineering philosophy, animation
decision framework, review standards, motion values, performance rules,
accessibility requirements, and animation vocabulary. It is not a separate
command; it is part of the existing UI build/review lens.

Key defaults from the reference:

- Do not animate keyboard-initiated or 100+/day actions.
- Give every animation a purpose: spatial continuity, state indication,
  explanation, feedback, or smoothing a jarring change.
- UI motion should usually stay under 300ms and use strong custom easing.
- Avoid `ease-in`, `transition: all`, `scale(0)`, centered transform origins on
  anchored overlays, layout-property animation, and missing reduced-motion
  handling.
- Motion reviews must start with a `Before | After | Why` markdown table and an
  explicit Block/Approve verdict.

---

## Skill Categories

### Foundation (loaded first, others depend on it)

| Skill | What it does | Notes |
|-------|-------------|-------|
| `frontend-design` | Core design principles, anti-patterns, AI slop detection, typography/color/layout/motion guidelines | **PREREQUISITE** — `colorize`, `bolder`, `quieter`, `animate`, `delight`, `critique`, `audit`, `polish` all require this to run first |
| `teach-impeccable` | One-time project setup: gathers design context (audience, brand, aesthetics, a11y) and writes `## Design Context` to CLAUDE.md | Run once per project, not per feature |

### Build Phase — Primary (Step 5)

These guide how to build UI from scratch or make significant changes.

| Skill | When to invoke | What it does |
|-------|---------------|-------------|
| `frontend-design` | **Always** for new pages/components | Guides distinctive, production-grade UI. Commits to bold aesthetic direction, avoids AI slop |
| `normalize` | **Always** when project has existing design system | Ensures new work matches existing tokens, components, patterns, spacing, typography |
| `practices/design-engineering.md` | **Always** for motion or component polish | Emil-derived defaults for motion purpose, easing, duration, origins, physicality, gestures, performance, a11y, and animation vocabulary |
| `onboard` | Building onboarding flows, empty states, first-time UX, signup wizards | Designs progressive disclosure, contextual teaching, time-to-value optimization |
| `animate` | Adding motion to entrances, state changes, micro-interactions | Stagger reveals, button feedback, form interactions, scroll effects. Requires `prefers-reduced-motion` |
| `adapt` | Feature must work across screen sizes/devices/platforms | Rethinks experience per context (not just shrinking). Touch targets, thumb zones, breakpoints |
| `clarify` | Writing labels, errors, empty states, tooltips, CTAs, confirmation dialogs | Makes copy specific, concise, active, human. Fixes jargon, ambiguity, passive voice |

### Build Phase — Adjustment (Step 5, applied after initial build)

These tune the result in a specific direction. Only invoke when the design needs correction.

| Skill | When to invoke | What it does |
|-------|---------------|-------------|
| `bolder` | Design feels too safe, generic, visually underwhelming | Amplifies typography scale, color saturation, spatial drama, motion. Warns against AI slop traps |
| `quieter` | Design feels too aggressive, overstimulating, visually noisy | Reduces saturation, weight, decoration, animation. "Refined, not boring" |
| `colorize` | Design is too monochromatic, gray, lacking visual warmth | Adds strategic color with 60/30/10 palette strategy. Uses OKLCH for perceptual uniformity |
| `delight` | Design is functional but joyless, needs personality | Adds success celebrations, playful copy, easter eggs, hover surprises. Context-appropriate |
| `distill` | Design is too complex, cluttered, has too many competing elements | Strips to essence. Progressive disclosure, fewer choices, shorter copy, flatter hierarchy |

### Review Phase — Diagnostic (Step 6, before fixes)

These **diagnose only** — they produce reports, not code changes.

| Skill | When to invoke | What it does |
|-------|---------------|-------------|
| `critique` | **Always** for UI features | Design director-level evaluation: AI slop detection, visual hierarchy, IA, emotional resonance, composition, typography, color purpose, states, microcopy. Outputs priority issues with fix commands |
| `audit` | **Always** for UI features | Systematic quality scan: a11y (contrast, ARIA, keyboard, semantics), performance (layout thrashing, expensive animations), theming (hard-coded colors, dark mode), responsive (fixed widths, touch targets). Severity-rated report |
| `practices/design-engineering.md` | **Always** when reviewing motion | Strict animation standards; findings table with Before/After/Why; Block/Approve verdict |

### Review Phase — Fixes (Step 6, after diagnostic)

Apply these based on what `critique` and `audit` found.

| Skill | When to invoke | What it does |
|-------|---------------|-------------|
| `polish` | **Always** as final pass | Pixel-perfect alignment, spacing consistency, all interaction states (hover/focus/active/disabled/loading/error/success), typography refinement, tinted neutrals, transition smoothness, code cleanup |
| `harden` | Feature handles user input, network requests, or will be used internationally | Edge case resilience: long text overflow, i18n/RTL, error handling per status code, empty/loading/permission states, input validation, a11y (keyboard nav, screen readers, reduced motion) |
| `optimize` | Performance issues found or feature is heavy (images, animations, large lists) | Core Web Vitals, image optimization, bundle splitting, render performance, animation GPU acceleration, network optimization |

### Post-Build (optional, Step 7)

| Skill | When to invoke | What it does |
|-------|---------------|-------------|
| `extract` | New patterns emerged that should be reusable | Identifies repeated components, hard-coded values, inconsistent variations. Extracts into design system with proper API, variants, docs |

---

## Cook Integration

### Step 2 (Explore) — Load practices

```javascript
if (featureInvolvesUI) {
  uiPractices = Read('practices/ui-design.md');
  if (needsMotion || featureIsNewUiSurface || reviewingMotion) {
    designEngineering = Read('practices/design-engineering.md');
  }

  // Check for design context
  if (!CLAUDE_MD.includes('## Design Context')) {
    // Suggest one-time setup
    Ask the user: "No Design Context in CLAUDE.md. Run /teach-impeccable?"
  }
}
```

### Step 5 (Build) — Invoke build skills

```javascript
// Always for new UI
Skill("frontend-design")

// If existing design system
if (hasDesignSystem) Skill("normalize")

// Situational
if (needsMotion || featureIsNewUiSurface) Read('practices/design-engineering.md')
if (buildingOnboarding) Skill("onboard")
if (needsMotion) Skill("animate")
if (multiDevice) Skill("adapt")
if (hasUserFacingCopy) Skill("clarify")

// Adjustment — only if needed after initial build
// Skill("bolder")    // if too safe
// Skill("quieter")   // if too noisy
// Skill("colorize")  // if too gray
// Skill("delight")   // if too dry
// Skill("distill")   // if too complex
```

### Step 6 (Review) — Diagnose then fix

```javascript
// 1. Diagnose
Skill("critique")   // design evaluation → priority issues
Skill("audit")      // systematic quality scan → severity report
if (diffTouchesMotion) Read('practices/design-engineering.md')

// 2. Fix based on findings
Skill("polish")     // always — final detail pass

// 3. Conditional fixes from audit/critique
if (edgeCasesFound) Skill("harden")
if (perfIssuesFound) Skill("optimize")

// 4. Live Browser Pass: widths × touch × throttled 3G, fix, before/after per fix, summary
liveBrowserPass()   // see "Live Browser Pass (audit + improve)" above

// 5. Post-build
if (reusablePatternsEmerged) Skill("extract")
```

---

## Skill Selection Quick Reference

Don't invoke every skill — pick what's relevant:

| Scenario | Skills to invoke |
|----------|-----------------|
| **New page from scratch** | `frontend-design` + `normalize` + `clarify` → `critique` + `audit` + `polish` |
| **New component** | `frontend-design` + `normalize` + design-engineering reference → `critique` + `polish` |
| **Improving existing UI** | `critique` first → targeted adjustment skills → `polish` → [Live Browser Pass](#live-browser-pass-audit--improve) |
| **UI audit** | `audit` + `critique` → [Live Browser Pass](#live-browser-pass-audit--improve) (widths, touch, 3G; before/after per fix; summary) |
| **Motion/animation review** | `practices/design-engineering.md` + `critique` + `audit`, then `polish` / `optimize` |
| **Mobile-facing feature** | add `adapt` + consider `animate` + design-engineering gestures/a11y rules |
| **Onboarding / empty states** | add `onboard` + `clarify` |
| **Design feels bland** | `bolder` or `colorize` or `delight` |
| **Design feels noisy** | `quieter` or `distill` |
| **Before shipping to prod** | `audit` + `polish` + `harden` + Live Browser Pass |
| **Performance concerns** | `optimize` |
| **Design system enrichment** | `extract` |

---

## Quick Checklist

- [ ] Design context exists in CLAUDE.md (or run `teach-impeccable`)
- [ ] `frontend-design` loaded before any other design skill
- [ ] Follows existing design system / component library (`normalize`)
- [ ] Emil-derived design-engineering reference loaded for motion/component polish
- [ ] Copy is clear and actionable (`clarify`)
- [ ] Accessible: keyboard nav, screen readers, contrast (`audit`)
- [ ] Responsive across breakpoints (`adapt`)
- [ ] Dark mode support if project uses it (`audit`)
- [ ] Loading, error, empty states handled (`harden`)
- [ ] Animations respect `prefers-reduced-motion` (`animate`)
- [ ] Animations have purpose, frequency fit, strong easing, correct origin, sub-300ms UI timing, and no layout-property animation
- [ ] Touch targets >= 44px on mobile (`adapt`, `audit`)
- [ ] Live Browser Pass run: widths 320–1920, touch emulation, throttled 3G
- [ ] Every fix has a before/after screenshot pair, and the summary was sent
- [ ] No layout shift on load (`optimize`, `polish`)
- [ ] Doesn't look AI-generated (`critique`, `frontend-design`)
