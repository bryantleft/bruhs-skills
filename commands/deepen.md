---
description: Find shallow modules and propose architectural deepenings — modules that hide more behaviour behind smaller interfaces. 3-phase workflow (explore → present candidates → grilling loop). Use when a codebase feels like it bounces between many small files, when tests feel like they're testing the wrong thing, or when you suspect modules aren't earning their keep.
---

# deepen — Find and Propose Architectural Deepenings

Surface architectural friction and propose **deepening opportunities** — refactors that increase **leverage** (what callers gain) and **locality** (what maintainers gain) by moving behaviour behind simpler interfaces.

Adapted from Matt Pocock's *improve-codebase-architecture* skill, which itself draws on Ousterhout's *A Philosophy of Software Design* and Feathers' *Working Effectively with Legacy Code*.

## Contents

- [Invocation](#invocation)
- [Philosophy](#philosophy)
- [Vocabulary](#vocabulary)
- [Workflow](#workflow)
  - [Phase 1: Explore](#phase-1-explore)
  - [Phase 2: Present candidates](#phase-2-present-candidates)
  - [Phase 3: Grilling loop](#phase-3-grilling-loop)
- [Output Shapes](#output-shapes)
- [Anti-Patterns](#anti-patterns)
- [Examples](#examples)
- [References](#references)

---

## Invocation

- `/bruhs:deepen` — Walk the whole codebase, surface candidates
- `/bruhs:deepen src/billing` — Scope to a path
- `/bruhs:deepen <module-name>` — Jump straight to grilling a known shallow module
- `/bruhs:deepen --no-explore` — Skip the explore phase if you already have a target in mind

---

## Philosophy

> A deep module hides a lot of behaviour behind a small interface. A shallow module's interface is nearly as complex as its implementation. The goal of architectural refactoring is to grow depth.

This command **does not refactor code**. It produces:

1. A ranked list of **deepening candidates** with plain-English problem statements.
2. For a chosen candidate: a co-designed interface, dependency strategy, and testing plan.
3. Optional ADR when a rejection reason would prevent future re-suggestion.

Implementation lives in `/bruhs:cook`. Use `/bruhs:deepen` to decide *what* to deepen and *what shape* it should take, then hand off.

### Why this is its own command

`/bruhs:slop` flags style, perf, and type violations — things that are wrong line-by-line. `/bruhs:deepen` looks at things that are wrong **structurally** — modules whose existence isn't earning what it costs. Different lens, different output, different decision criteria.

---

## Vocabulary

**Use these terms exactly. Don't substitute "component", "service", "API", or "boundary".**

| Term | Meaning |
|---|---|
| **Module** | Anything with an interface and an implementation. Function, class, package, or tier-spanning slice. |
| **Interface** | Everything a caller must know to use the module correctly — types, invariants, ordering, errors, configuration, perf characteristics. |
| **Depth** | Behaviour-per-unit-of-interface. Deep = lots of behaviour behind a small interface. |
| **Seam** | A place where you can alter behaviour without editing in that place. |
| **Adapter** | A concrete thing that satisfies an interface at a seam. |
| **Leverage** | Caller-side benefit of depth. |
| **Locality** | Maintainer-side benefit of depth. |

> Full glossary, principles, and rejected framings → `practices/architecture-deepening.md`.

---

## Workflow

### Phase 1: Explore

Walk the codebase organically. Don't run a static linter — read.

1. **Read the domain glossary first.** Look for `CONTEXT.md`, `ARCHITECTURE.md`, `docs/adrs/`, `README.md`. If none exist, infer the domain vocabulary from type names, package boundaries, and tests.
2. **Trace 2–3 representative call paths end-to-end.** A request from ingress, a job from queue to outcome, a UI action to persistence. You're hunting for **bouncing** — concepts that require the reader to jump between many small modules to understand one operation.
3. **Note friction points** as you go. Use the diagnostic table in `practices/architecture-deepening.md`:
   - Bouncing (single concept, many small modules)
   - Pass-through (1:1 forwarding to a dependency)
   - Leaky implementation (callers must know transport/encoding/storage)
   - Boolean-flag interfaces
   - Scattered invariants (validation repeats at every call site)
   - Untested call patterns (common patterns awkward to test)
   - Coupled lifecycle (fixed creation/teardown order across callers)
   - Type signatures that lie (function name says one thing, signature hides side effects)
4. **Apply the deletion test** to suspected shallow modules. *If I deleted this, where would the complexity go?* If it scatters across N callers → the module was earning its keep, but maybe its interface should grow. If it vanishes → the module was a pass-through and a candidate for elimination/merging.

**Output of Phase 1:** A working set of friction points, each tied to specific files. Don't propose interfaces yet.

### Phase 2: Present candidates

Produce a numbered list. Each entry is structured:

```
N. <short title>

   Files: <list of paths>
   Problem: <plain English — what bounces, what leaks, what scatters>
   Proposed deepening: <plain English — what gets hidden, what stays>
   Benefits:
     - Leverage: <what callers no longer need to know>
     - Locality: <where change/bugs/tests will concentrate>
   Dependency category: <in-process | local-substitutable | remote-owned | true-external>
   Rough effort: <S | M | L>
```

**Constraints on this phase:**

- **Use domain vocabulary** from CONTEXT.md / inferred glossary. *"Charge"*, *"Subscription"*, *"Reservation"* — not generic *"manager"*, *"service"*.
- **Use architectural language** exactly: module, interface, depth, seam, adapter, leverage, locality.
- **Don't propose interfaces yet.** Phase 2 is about *what to deepen*, not *what shape*. Interface design happens in Phase 3.
- **Rank by leverage × locality, not by effort.** A high-impact L beats a low-impact S.
- **5–8 candidates max.** If you have more, you haven't filtered — re-apply the deletion test and cut the ones that don't pass.

Then ask: *"Which would you like to grill?"*

### Phase 3: Grilling loop

Once a candidate is chosen, co-design the deepened module through conversation. **Do not write code.** Produce a design.

**3a. Frame the problem.** Restate the candidate as a brief any cold reader could pick up:

- What the module *must* hide (the depth target)
- Constraints (dependency category, perf, deployment, language idioms)
- Illustrative caller code — concrete, not abstract
- Whether the seam needs 1 or 2+ adapters (see seam discipline)

**3b. Design it twice.** Generate radically different alternatives, each with a distinct constraint. Use sub-agents in parallel via `dispatching-parallel-agents` (superpowers) when alternatives are independent and the brief is concrete enough for cold-start work:

| Alternative | Constraint |
|---|---|
| **A. Minimal** | 1–3 entry points max. What gets cut? |
| **B. Extensible** | Max use cases without breaking changes. What's the cost? |
| **C. Caller-optimised** | Optimise for the 80% common pattern. What does the 20% pay? |
| **D. Ports & Adapters** *(only if dependency is remote-owned or true-external)* | Seam as load-bearing. What's the port shape? |

Each alternative produces: interface spec, usage examples, implementation sketch, dependency/test strategy, trade-offs.

**3c. Compare and recommend.** Contrast on:

- **Depth** — Behaviour hidden behind the interface
- **Locality** — Where change concentrates
- **Seam placement** — Where behaviour can vary; is the variation real?
- **Caller cost** — How much must callers learn?

Make an **opinionated recommendation**. Optionally propose a hybrid.

**3d. Update CONTEXT.md** with new terms introduced. Refine fuzzy ones as decisions crystallize. If the candidate is rejected and the reason is durable (e.g., "we evaluated this and chose to keep them split because of deployment topology"), draft an ADR so the candidate isn't re-suggested later.

**3e. Hand off.** When a design is agreed, output:

- **Implementation plan** suitable for `/bruhs:cook` to pick up
- **Test plan** at the new interface (tests at the *external* seam — see Testing strategy)
- **Migration plan** if callers must change
- **Tests-to-delete list** — old shallow-module tests that become waste

---

## Output Shapes

### Phase 2 output (candidate list)

```
Deepening candidates for src/billing

1. Subscription lifecycle is scattered across 6 modules
   Files: src/billing/{create,renew,cancel,suspend,resume,grace}.ts
   Problem: Each lifecycle transition is its own module exporting a single function.
            Callers know all 6. State invariants (e.g. "can't cancel a suspended sub
            without first resuming") live in 4 of them and disagree.
   Proposed deepening: One Subscription module owning the state machine. Callers see
                       transition methods and a single state type.
   Benefits:
     - Leverage: callers stop tracking which lifecycle file owns which transition
     - Locality: state invariants live in one place; one set of tests covers them
   Dependency category: local-substitutable (Postgres via Drizzle)
   Rough effort: M

2. ...
```

### Phase 3 output (chosen candidate, post-grilling)

```
Design: Subscription module

Interface (recommended — Alternative C, caller-optimised):
  type Subscription = ... (discriminated union of states)
  function load(id): Promise<Result<Subscription, NotFound>>
  function transition(sub, event): Result<Subscription, InvalidTransition>
  function persist(sub): Promise<Result<void, ConflictError>>

Why C over A/B:
  - A (minimal) collapsed transition+persist; tests couldn't pin down race window.
  - B (extensible) supported plugin transitions; nothing in our roadmap needs that.
  - C keeps the state machine pure and the I/O explicit — testable in-process,
    persistable as one round-trip.

Seam: internal. Postgres is local-substitutable via PGLite in tests; no port at
      the external interface. (One adapter justified, not two.)

Tests-to-delete: 14 unit tests across the 6 lifecycle files that exercise the
                 state machine through I/O.

Migration: 9 call sites import { transition } from new module instead of the
           per-lifecycle files. Old files become re-exports for one release.

Hand-off: ready for `/bruhs:cook subscription-deepening`.
```

---

## Anti-Patterns

What this command refuses to do — and what it should call out when others do it:

- **"Add an interface so it's mockable."** A single-adapter seam is decoration. *One adapter means a hypothetical seam. Two adapters means a real one.* Push back.
- **"Just split into smaller files."** Smaller files with the same shallow interfaces aren't deeper. Surface tidying ≠ deepening.
- **"Test the new internal helper directly."** The interface is the test surface. If you want to test past it, the module is the wrong shape.
- **Proposing a deepening without applying the deletion test.** A module that fails the deletion test is a pass-through; merge it, don't reshape it.
- **Inventing new vocabulary mid-conversation.** "Service", "manager", "handler", "boundary" — substitute the architectural terms or the proposal turns mushy.
- **Refactoring during the grilling loop.** Phase 3 is design, not code. Code goes through `/bruhs:cook`.
- **Recommending without an opinion.** "Here are three options, you decide" is failure. Pick one. Defend it.

---

## Examples

### Example 1: Whole-codebase walk

```
> /bruhs:deepen

Phase 1: Exploring src/...
  Read CONTEXT.md (domain: Booking, Reservation, Stay, Charge)
  Traced 3 call paths: POST /reservations, nightly settlement job, cancellation flow
  Noted friction:
    - reservation/{create,modify,cancel}.ts bounce through booking/utils/dates.ts
      4x for one operation
    - charge module's interface leaks Stripe's payment intent shape into call sites
    - 2 places re-implement "is room available on these dates"

Phase 2: Candidates

1. Reservation lifecycle bounces across 4 modules
   ...
2. Charge module leaks Stripe shapes (payment intent) into 7 call sites
   ...
3. Availability check duplicated in BookingForm and ReservationCreate
   ...

Which would you like to grill? (1-3, or 'all', or 'none')
```

### Example 2: Targeted grilling

```
> /bruhs:deepen src/charge

Phase 1: Scoped to src/charge.
  Friction: every caller imports `Stripe.PaymentIntent` to read `.status`.
  Deletion test: deleting charge module would scatter Stripe types into 7 callers.
                 Module earns its keep but its interface is shallow — leaks Stripe.

Phase 2: 1 candidate

1. Charge module leaks Stripe shapes
   Files: src/charge/{create,capture,refund,read}.ts, plus 7 callers
   Problem: Callers depend on `Stripe.PaymentIntent.status` directly. Migrating
            from Stripe to a backup processor would touch 7 files, not 1.
   Proposed deepening: Charge owns its own state type. Stripe is an injected
                       port. Callers never see Stripe types.
   Benefits:
     - Leverage: callers learn 1 enum instead of Stripe's full PI shape
     - Locality: processor migration touches charge module only
   Dependency category: true-external (Stripe)
   Rough effort: M

Grill it? (y/n)
```

---

## References

- **`practices/architecture-deepening.md`** — Vocabulary, principles, dependency categories, seam discipline, design-it-twice mechanics
- **`practices/type-driven-design.md`** — Signature-as-documentation, errors-in-return-types (related but orthogonal)
- **`commands/cook.md`** — Hand off implementation here
- **`commands/slop.md`** — Line-level audit (different lens)
- **`commands/doodle.md`** — Visualize the proposed deepening as a module map before/after

External:
- John Ousterhout, *A Philosophy of Software Design* (deep modules, design it twice)
- Michael Feathers, *Working Effectively with Legacy Code* (seams)
- Matt Pocock, *improve-codebase-architecture* skill — original source: https://github.com/mattpocock/skills/tree/main/skills/engineering/improve-codebase-architecture
