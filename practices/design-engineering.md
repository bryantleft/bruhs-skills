# Design Engineering and Motion

Design and motion guidance adapted from
`emilkowalski/skills`: `emil-design-eng`, `review-animations`, and
`animation-vocabulary`.

Use this with `practices/ui-design.md` whenever a task touches visible UI,
component polish, animation, motion review, or animation naming. Do not add a
separate bruhs command; fold these checks into `cook`, `slop`, `peep`, and UI
preview work.

## Core posture

- Treat taste as trained judgment, not preference. Inspect strong interfaces and
  copy the underlying reasoning, not the surface.
- Optimize for details users do not consciously notice: correct origin,
  responsive timing, good defaults, edge cases that disappear.
- Use beauty as product leverage. A feature that only works is unfinished if it
  feels generic, sluggish, or careless.
- Prefer excellent defaults over option sprawl. Most consumers never customize.
- Keep component APIs low-friction. A component that is hard to adopt will not
  get used, even if it is visually strong.

## Animation decision framework

Answer these before writing or approving motion:

1. **Should this animate?**
   - 100+ times per day, keyboard shortcuts, command palette toggles: no
     animation.
   - Tens of times per day, hover effects, list navigation: remove or reduce
     heavily.
   - Occasional surfaces, modals, drawers, toasts: standard animation.
   - Rare, first-time, onboarding, feedback, celebrations: can carry delight.

2. **What is the purpose?**
   - Acceptable purposes: spatial consistency, state indication, explanation,
     feedback, preventing a jarring change.
   - "Looks cool" is not enough, especially on frequent actions.

3. **Which easing?**
   - Entering or exiting: strong `ease-out`.
   - Moving or morphing on screen: strong `ease-in-out`.
   - Hover or color change: `ease`.
   - Constant motion: `linear`.
   - Avoid `ease-in` for UI. It starts slowly at the exact moment users are
     watching for feedback.

4. **How long?**
   - Button press feedback: 100-160ms.
   - Tooltips and small popovers: 125-200ms.
   - Dropdowns and selects: 150-250ms.
   - Modals and drawers: 200-500ms.
   - Most UI motion should be under 300ms unless the interaction explicitly
     needs a longer deliberate phase.

Use strong custom curves instead of weak browser defaults:

```css
:root {
  --ease-out: cubic-bezier(0.23, 1, 0.32, 1);
  --ease-in-out: cubic-bezier(0.77, 0, 0.175, 1);
  --ease-drawer: cubic-bezier(0.32, 0.72, 0, 1);
}
```

Use easing libraries such as `easing.dev` or `easings.co` for variants; do not
invent cubic-beziers from scratch unless you verify them visually.

## Non-negotiable review standards

Flag these as findings in UI or animation review:

1. Motion has no stated purpose.
2. High-frequency or keyboard-initiated actions animate.
3. UI uses `ease-in`, weak default easing on deliberate motion, or sluggish
   timing.
4. UI animation exceeds 300ms without a reason tied to the interaction.
5. Popovers, dropdowns, or tooltips scale from `center` instead of their trigger.
6. Any entrance starts from `scale(0)`.
7. Rapidly-triggered or gesture-driven motion uses keyframes that restart from
   zero instead of transitions, WAAPI, or springs.
8. Animation changes layout properties such as `width`, `height`, `top`, `left`,
   `margin`, or `padding`.
9. Movement ignores `prefers-reduced-motion`.
10. Hover motion is not gated behind `(hover: hover) and (pointer: fine)`.
11. Press-and-release or hold interactions use symmetric timing when the
    deliberate phase should be slower and release should snap back.
12. A group entrance appears all at once when a 30-80ms stagger would clarify the
    sequence.

Use this remedial order:

1. Delete the animation.
2. Reduce duration, distance, scale, or number of animated properties.
3. Fix easing and duration.
4. Fix origin and physicality.
5. Make it interruptible.
6. Move it to GPU-friendly properties.
7. Make timing asymmetric when the interaction has a deliberate phase.
8. Add polish: blur a crossfade, stagger a group, use `@starting-style`.
9. Add accessibility and device gating.

## Required animation review output

When reviewing motion, lead with a markdown table. Do not use prose-only
before/after bullets.

| Before | After | Why |
| --- | --- | --- |
| `transition: all 300ms` | `transition: transform 200ms var(--ease-out)` | Limit properties; avoid accidental layout or paint animation. |
| `transform: scale(0)` | `opacity: 0; transform: scale(0.95)` | Entrances need visible physical continuity. |
| `ease-in` on dropdown | `var(--ease-out)` | Starts fast, so the UI responds immediately. |
| `transform-origin: center` on popover | Trigger-origin CSS variable | Anchored surfaces should grow from the trigger. |

Then give a verdict grouped by impact:

- **Block** for feel-breaking regressions, high-frequency animation, `scale(0)`,
  `ease-in` on UI, easy-to-fix non-GPU animation, missing reduced-motion on
  movement, or incorrect origin on anchored surfaces.
- **Approve** only when purpose, frequency, easing, duration, origin,
  interruptibility, performance, accessibility, and cohesion are all acceptable.

Always cite `file:line` for findings.

## Component polish rules

### Pressable controls

Add subtle press feedback to buttons and button-like controls:

```css
.button {
  transition: transform 160ms var(--ease-out);
}

.button:active {
  transform: scale(0.97);
}
```

Use 0.95-0.98. Keep it subtle.

### Entrances

Never animate from `scale(0)`. Use opacity plus a near-final scale:

```css
.popover[data-starting-style],
.popover[data-ending-style] {
  opacity: 0;
  transform: scale(0.95);
}
```

Use `@starting-style` for entry when supported:

```css
.toast {
  opacity: 1;
  transform: translateY(0);
  transition:
    opacity 200ms var(--ease-out),
    transform 200ms var(--ease-out);

  @starting-style {
    opacity: 0;
    transform: translateY(100%);
  }
}
```

Fallback to a `data-mounted` pattern only when support requires it.

### Origin-aware overlays

Anchored overlays should scale from the trigger:

```css
.popover {
  transform-origin: var(--radix-popover-content-transform-origin);
}

.base-ui-popover {
  transform-origin: var(--transform-origin);
}
```

Modals are exempt because they are viewport-centered, not trigger-anchored.

### Tooltips

Use an initial delay to prevent accidental activation. Once one tooltip is open,
adjacent tooltips should appear instantly and skip animation so toolbars feel
fast.

### Crossfades

When two states overlap awkwardly during a crossfade, add a small blur during
the transition:

```css
.button-content[data-transitioning] {
  filter: blur(2px);
  opacity: 0.7;
}
```

Keep blur below 20px; heavy blur is expensive, especially in Safari.

### Stagger

Use short stagger delays for grouped entrances:

- 30-80ms between items.
- Decorative only; never block interaction while a stagger is running.
- Prefer small offset, opacity, and a 200-300ms duration.

## Springs

Use springs when motion needs physical interruption or gesture continuity:

- Drag interactions with momentum.
- Swipe or dismiss gestures.
- Alive decorative elements.
- Mouse-following decoration where direct binding would feel artificial.

Recommended starting points:

```js
{ type: "spring", duration: 0.5, bounce: 0.2 }
{ type: "spring", mass: 1, stiffness: 100, damping: 10 }
```

Keep bounce between 0.1 and 0.3, and avoid bounce in serious product surfaces.

Springs preserve velocity when interrupted. CSS keyframes restart, so avoid
keyframes for rapid toggles, toasts, or user-reversible interactions.

## Transform, clip-path, and gesture notes

- `translateY(100%)` moves by the element's own height. Prefer percentages over
  hardcoded pixel offsets for toasts, drawers, and sheets.
- `scale()` scales children too. That is desirable for press feedback.
- Use 3D transforms (`rotateX`, `rotateY`, `transform-style: preserve-3d`) for
  real CSS depth when it fits the product.
- `clip-path: inset(top right bottom left)` is useful for reveals, hold-to-delete
  overlays, active tab color wipes, image comparison sliders, and scroll
  reveals.
- Hold-to-confirm: slow the active fill (`2s linear`) and make release fast
  (`200ms var(--ease-out)`).
- Swipe dismissal should consider velocity, not only distance. A flick should be
  enough; `Math.abs(distance) / elapsedMs > ~0.11` is a useful threshold.
- Use boundary damping and friction instead of invisible hard stops.
- Capture the pointer once drag starts.
- Ignore extra touch points after a drag begins to prevent jumps.

## Performance rules

- Animate `transform` and `opacity` by default.
- Avoid animating layout or paint-heavy properties unless the tradeoff is
  deliberate and measured.
- Do not update a CSS variable on a parent to drive a hot child transform; that
  can recalculate styles for the subtree. Set `element.style.transform` on the
  moving element.
- CSS animations and transitions stay smoother under main-thread load than
  requestAnimationFrame-driven JS.
- Use WAAPI for programmatic animations that need JS control with browser
  animation performance.
- For Framer Motion / Motion, prefer full `transform` strings over shorthand
  `x`, `y`, or `scale` on animations that run under load.

```jsx
<motion.div animate={{ transform: "translateX(100px)" }} />
```

## Accessibility

Reduced motion means fewer and gentler animations, not necessarily zero motion.
Keep opacity and color changes that preserve comprehension; remove or shrink
transform-based movement.

```css
@media (prefers-reduced-motion: reduce) {
  .element {
    animation: fade 200ms ease;
    transform: none;
  }
}

@media (hover: hover) and (pointer: fine) {
  .element:hover {
    transform: scale(1.03);
  }
}
```

In React, respect `useReducedMotion()` when positioning or animating movement.

## Debugging motion

- Slow animations to 2-5x or use browser animation tools.
- Check whether colors crossfade cleanly, the origin is correct, easing does not
  stop abruptly, and coordinated properties stay in sync.
- Step frame by frame for complex sequences.
- Test touch gestures on real devices when possible.
- Re-review motion later with fresh eyes if the feel is uncertain.

## Animation vocabulary

Use this glossary when the user describes an effect but does not know its name.
Lead with the best term, then mention 1-2 close alternatives only if useful.

### Entrances and exits

- **Fade in / fade out**: opacity changes make an element appear or disappear.
- **Slide in**: an element enters from an edge or off-screen position.
- **Scale in**: an element grows from a smaller size, usually with opacity.
- **Pop in**: an element enters with a slight overshoot or bounce.
- **Reveal**: content is uncovered with a clip-path, mask, or similar technique.
- **Enter / exit**: animation played when an element is added or removed.

### Sequencing and timing

- **Keyframes**: named points in an animation timeline.
- **Interpolation / tween**: generated in-between frames between two values.
- **Stagger**: a group animates one item after another.
- **Orchestration**: multiple animations are timed to feel like one sequence.
- **Delay**: time before animation starts.
- **Duration**: how long animation takes.
- **Fill mode**: whether first or final keyframe styles apply outside playback.
- **Stepped animation**: discrete steps instead of continuous motion.

### Movement and transforms

- **Translate**: move along X or Y.
- **Scale**: grow or shrink.
- **Rotate**: spin around an origin.
- **Skew**: slant along an axis.
- **3D tilt / flip**: rotate in 3D space.
- **Perspective**: controls perceived 3D depth.
- **Transform origin**: anchor point for transform operations.
- **Origin-aware animation**: motion grows or moves from its trigger or source.

### Transitions between states

- **Crossfade**: one element fades out as another fades in in the same place.
- **Continuity transition**: before and after states remain visually connected.
- **Morph**: one shape turns into another.
- **Shared element transition**: the same visual element travels and transforms
  between states.
- **Layout animation**: size or position changes animate to the new layout.
- **Accordion / collapse**: a section expands or collapses.
- **Direction-aware transition**: forward and backward navigation move in
  opposite directions.

### Scroll

- **Scroll reveal**: elements animate as they enter the viewport.
- **Scroll-driven animation**: animation progress is tied to scroll position.
- **Parallax**: layers move at different scroll speeds.
- **Page transition**: motion during route or page navigation.
- **View transition**: browser-assisted visual continuity between page states.

### Feedback and interaction

- **Hover effect**: visual change on pointer hover.
- **Press / tap feedback**: subtle scale or visual response on activation.
- **Hold to confirm**: progress fills while the user holds a control.
- **Drag**: an element follows pointer movement.
- **Drag to reorder**: list items move while dragged into a new order.
- **Swipe to dismiss**: drag an item off-screen to close or remove it.
- **Rubber-banding**: resistance and snap-back beyond a boundary.
- **Shake / wiggle**: short side-to-side error or rejection signal.
- **Ripple**: expanding circle from the tap point.

### Easing

- **Easing**: rate of speed change over time.
- **Ease-out**: starts fast and ends slow; default for responsive UI.
- **Ease-in**: starts slow and ends fast; usually avoid in UI.
- **Ease-in-out**: slow-fast-slow; useful for moving existing elements.
- **Linear**: constant speed; use for spinners, marquees, and progress.
- **Cubic-bezier**: custom easing curve.
- **Asymmetric easing**: different acceleration and deceleration character.

### Springs

- **Spring**: physics-driven motion.
- **Stiffness / tension**: force pulling toward the target.
- **Damping**: how quickly oscillation settles.
- **Mass**: how heavy the animated element feels.
- **Bounce**: overshoot and settle behavior.
- **Perceptual duration**: how long a spring feels active.
- **Momentum**: carried motion after release or interruption.
- **Velocity**: current speed and direction.
- **Interruptible animation**: motion that can retarget smoothly mid-flight.

### Looping and ambient motion

- **Marquee**: continuous scrolling content.
- **Loop**: repeating animation.
- **Alternate / yoyo**: loop that reverses every cycle.
- **Orbit**: circular movement around a point or object.
- **Pulse**: gentle repeating scale or opacity change.
- **Float**: slow vertical drift.
- **Idle animation**: subtle motion while waiting for interaction.

### Polish and effects

- **Blur**: softening used for focus, depth, or masking transitions.
- **Clip-path**: hard-edged clipping for reveals and wipes.
- **Mask**: soft or gradient-based hiding and revealing.
- **Before / after slider**: draggable comparison wipe.
- **Line drawing**: SVG path appears as if drawn.
- **Text morph**: characters transition to new content.
- **Skeleton / shimmer**: loading placeholder with animated sheen.
- **Number ticker**: digits roll or count to a value.
- **Tabular numbers**: fixed-width digits that prevent shifting.
- **Typewriter**: characters appear sequentially.

### Performance terms

- **Frame rate / FPS**: frames per second; 60fps is baseline smoothness.
- **Jank**: visible stutter.
- **Dropped frame**: a missed rendering deadline.
- **Compositing**: GPU moves or fades a layer without layout or paint.
- **will-change**: hint that a property will animate.
- **Layout thrashing**: repeated layout recalculation during animation.

### Principles

- **Purposeful animation**: motion orients, explains, confirms, or connects.
- **Anticipation**: small preparatory motion before action.
- **Follow-through**: parts continue settling after the main motion.
- **Squash and stretch**: deformation that conveys weight or flexibility.
- **Perceived performance**: animation makes identical load time feel faster.
- **Frequency of use**: repeated motion must get shorter or disappear.
- **Spatial consistency**: motion preserves where things came from and went.
- **Hardware acceleration**: use transform and opacity for compositor-friendly
  motion.
- **Reduced motion**: respect motion sensitivity with gentler alternatives.
