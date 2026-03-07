# UI Design Best Practices

Integrates [pbakaus/impeccable](https://github.com/pbakaus/impeccable) skills into the bruhs workflow for high-quality UI work.

**Used by:**
- `cook` - Invoked automatically when building UI features
- `slop` - Can audit UI quality

---

## When to Apply

These practices activate when a feature involves **visible UI changes** — new pages, components, layouts, forms, modals, onboarding flows, etc. Skip for pure backend/API/infra work.

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

  // Check for design context
  if (!CLAUDE_MD.includes('## Design Context')) {
    // Suggest one-time setup
    AskUserQuestion: "No Design Context in CLAUDE.md. Run /teach-impeccable?"
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

// 2. Fix based on findings
Skill("polish")     // always — final detail pass

// 3. Conditional fixes from audit/critique
if (edgeCasesFound) Skill("harden")
if (perfIssuesFound) Skill("optimize")

// 4. Post-build
if (reusablePatternsEmerged) Skill("extract")
```

---

## Skill Selection Quick Reference

Don't invoke every skill — pick what's relevant:

| Scenario | Skills to invoke |
|----------|-----------------|
| **New page from scratch** | `frontend-design` + `normalize` + `clarify` → `critique` + `audit` + `polish` |
| **New component** | `frontend-design` + `normalize` → `critique` + `polish` |
| **Improving existing UI** | `critique` first → targeted adjustment skills → `polish` |
| **Mobile-facing feature** | add `adapt` + consider `animate` |
| **Onboarding / empty states** | add `onboard` + `clarify` |
| **Design feels bland** | `bolder` or `colorize` or `delight` |
| **Design feels noisy** | `quieter` or `distill` |
| **Before shipping to prod** | `audit` + `polish` + `harden` |
| **Performance concerns** | `optimize` |
| **Design system enrichment** | `extract` |

---

## Quick Checklist

- [ ] Design context exists in CLAUDE.md (or run `teach-impeccable`)
- [ ] `frontend-design` loaded before any other design skill
- [ ] Follows existing design system / component library (`normalize`)
- [ ] Copy is clear and actionable (`clarify`)
- [ ] Accessible: keyboard nav, screen readers, contrast (`audit`)
- [ ] Responsive across breakpoints (`adapt`)
- [ ] Dark mode support if project uses it (`audit`)
- [ ] Loading, error, empty states handled (`harden`)
- [ ] Animations respect `prefers-reduced-motion` (`animate`)
- [ ] Touch targets >= 44px on mobile (`adapt`, `audit`)
- [ ] No layout shift on load (`optimize`, `polish`)
- [ ] Doesn't look AI-generated (`critique`, `frontend-design`)
