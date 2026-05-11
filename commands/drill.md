---
description: Find missing or weak layers in the test suite's safety net and propose adoption plans — modules need depth, suites need layered discipline. 3-phase workflow (explore → present candidates → grilling loop). Use when tests pass but bugs still ship, when coverage looks high but feels meaningless, when "clean architecture" ADRs erode unenforced, or when AI-generated test files are accumulating without review.
---

# drill — Find and Propose Test-Infrastructure Adoptions

Surface gaps in the testing safety net and propose **adoption opportunities** — layers of discipline whose absence is letting a known bug class through. The aim is a suite that catches what it claims to catch and a CI orchestrator that fails the build when it doesn't.

The companion to `/bruhs:deepen`: deepen modules, drill tests. Same 3-phase workflow, different lens.

## Contents

- [Invocation](#invocation)
- [Philosophy](#philosophy)
- [Vocabulary](#vocabulary)
- [Workflow](#workflow)
  - [Phase 1: Explore](#phase-1-explore)
  - [Phase 2: Present candidates](#phase-2-present-candidates)
  - [Phase 3: Grilling loop](#phase-3-grilling-loop)
- [The 8 Layers](#the-8-layers)
- [Output Shapes](#output-shapes)
- [Anti-Patterns](#anti-patterns)
- [Examples](#examples)
- [References](#references)

---

## Invocation

- `/bruhs:drill` — Walk the whole project, surface missing or weak layers
- `/bruhs:drill apps/web` — Scope to a path
- `/bruhs:drill <layer-name>` — Jump straight to grilling one layer (e.g. `mutation`, `acceptance`, `architecture-check`)
- `/bruhs:drill --no-explore` — Skip explore if you already have a target in mind

---

## Philosophy

> A test suite is a layered safety net. Each layer catches a different bug class. A missing layer isn't covered by the others — it's just where bugs ship from.

This command **does not write tests**. It produces:

1. A ranked list of **adoption candidates** — layers that are missing, advisory-only, or rotting.
2. For a chosen candidate: a co-designed adoption plan — what the layer enforces, how it's gated, what success looks like in CI.
3. Optional ADR when a "we're not doing this" decision would prevent re-suggestion.

Implementation lives in `/bruhs:cook`. Use `/bruhs:drill` to decide *which layer* to add and *what shape* its gate should have, then hand off.

### Why this is its own command

`/bruhs:slop` flags line-level issues (types, perf, swallowed errors). `/bruhs:deepen` flags structural issues (shallow modules, leaky seams). `/bruhs:drill` flags **safety-net** issues — bug classes the suite isn't structured to catch at all. Different lens, different output, different decision criteria.

### Sibling discipline

`/bruhs:deepen` and `/bruhs:drill` share two beliefs:

1. **The interface is the test surface.** A test that crosses past it is testing the wrong thing.
2. **Replace, don't layer.** A new layer makes the old shallow tests waste — delete them, don't preserve them out of guilt.

Read `practices/architecture-deepening.md` and `practices/testing-infrastructure.md` together. They reinforce each other.

---

## Vocabulary

**Use these terms exactly. Don't substitute "testing strategy", "quality gate", or "QA process".**

| Term | Meaning |
|---|---|
| **Layer** | One of the 8 components in the safety net (acceptance specs, unit tests, coverage gate, mutation runner, complexity composite, architecture checker, test-code linter, CI orchestrator). Each catches a distinct bug class. |
| **Hard gate** | A check that fails the build. Advisory checks (warnings, dashboards, weekly reports) don't count as gates. |
| **Discipline floor** | The minimum a layer enforces in CI. Below the floor, the layer is decoration. |
| **Kill ratio** | For mutation testing: of N introduced mutants, how many tests caught. Proves coverage is meaningful, not just present. |
| **Architecture rule** | A machine-checkable constraint on module dependencies. Encodes an ADR so it's enforced, not just documented. |
| **Test-code linter** | Static analysis applied to test files themselves. Keeps AI-generated test code from rotting into a parallel untyped codebase. |
| **Orchestrator** | The CI step that runs every layer as hard gates. Without it, every other layer is opt-in. |

> Full definitions and gating-posture rules → `practices/testing-infrastructure.md`.

---

## Workflow

### Phase 1: Explore

Read the project, not a dashboard. Don't trust a green CI badge — green can mean "no gate fired" as easily as "no problem found".

1. **Read the project config.** `package.json` / `pyproject.toml` / `Cargo.toml`, the CI workflow files (`.github/workflows/*`, `.gitlab-ci.yml`, etc.), any test config (`vitest.config`, `jest.config`, `pytest.ini`, `cargo-nextest.toml`), and the `bruhs:state` block in `CLAUDE.md` (read via `scripts/read_bruhs_block.py`, with legacy `.claude/bruhs.json` fallback). The CI workflow is the ground truth — what runs there is what's enforced.
2. **Walk the test tree.** `apps/*/src/**/*.test.*`, `tests/`, `features/`, `__tests__/`. Look for what's tested *and* what's conspicuously absent — files with no neighbour test, integration paths covered only by unit tests, API routes with no acceptance spec.
3. **Map each layer to its current state** (see the [8 layers](#the-8-layers) table). For each:
   - **Absent** — no implementation at all.
   - **Advisory** — exists, reports a number, doesn't fail the build.
   - **Gated** — fails the build below a threshold.
   - **Rotting** — gated but the threshold has been lowered repeatedly to keep CI green, or exclusions have grown.
4. **For each non-absent layer, check the discipline floor:**
   - Coverage gate < 60% on changed lines → effectively absent.
   - Mutation kill-ratio reported but ungated → advisory only.
   - Architecture rules in code comments / ADRs but no enforcer → unenforced.
   - Test files excluded from lint/type config → test-code linter absent.
   - Any gate in `continue-on-error: true` → advisory, not a gate.
5. **Apply the "what would slip through" test** to each absent or advisory layer. Concrete: *if this layer were absent for the next 10 PRs, which class of bug would slip through?* If the answer is "none in this codebase" → don't flag it. If the answer is concrete → it's a candidate.

**Output of Phase 1:** A working set of weak or missing layers, each tied to specific evidence (file paths, CI step names, threshold values, exclusion lists). Don't propose adoption plans yet.

### Phase 2: Present candidates

Produce a numbered list. Each entry is structured:

```
N. <short title>

   Layer: <one of the 8>
   Current state: <absent | advisory | gated-but-rotting>
   Evidence: <CI file + step, config flags, threshold history>
   Bug class it would catch: <concrete — what slips through today>
   Proposed adoption: <plain English — what gets gated, at what threshold>
   Gating posture: <hard gate from day 1 | advisory then hard after baseline>
   Cross-layer effect: <which other layers it strengthens or replaces>
   Rough effort: <S | M | L>
```

**Constraints on this phase:**

- **Use the 8-layer vocabulary** from the table below. Don't invent new layer names.
- **Don't propose tools yet.** Phase 2 is about *which layer to adopt*, not *which library to install*. Tool choice happens in Phase 3.
- **Rank by bug-class-prevented × cross-layer leverage, not by effort.** A high-impact L beats a low-impact S.
- **5–8 candidates max.** If you have more, you haven't filtered — re-apply the "what would slip through" test and cut the ones with no concrete answer.
- **Call out advisory-only layers explicitly.** "Exists but ungated" is a candidate, not a check-mark. The CI orchestrator only counts hard gates.

Then ask: *"Which would you like to grill?"*

### Phase 3: Grilling loop

Once a candidate is chosen, co-design the adoption plan through conversation. **Do not write code, install dependencies, or modify CI.** Produce a plan.

**3a. Frame the layer.** Restate the candidate as a brief any cold reader could pick up:

- Which bug class the layer must catch (the discipline target)
- Constraints (language, CI provider, existing tooling, perf budget for CI)
- Illustrative gate output — concrete, not abstract (e.g., "the build fails with: `coverage on changed lines is 47%, gate is 80%`")
- Whether this is a hard gate from day 1 or an advisory-then-baseline ramp

**3b. Design the gate twice.** Generate alternatives, each with a distinct constraint. Use sub-agents in parallel via `dispatching-parallel-agents` (superpowers) when alternatives are independent:

| Alternative | Constraint |
|---|---|
| **A. Strict from day 1** | Hard gate at production-grade threshold immediately. What breaks? |
| **B. Ratchet-only** | Gate enforces "no worse than baseline" — the floor can only go up. What does the first ratchet look like? |
| **C. Scoped pilot** | Hard gate on one package / one route / one module, expanding monthly. What's the rollout shape? |
| **D. Cross-layer fusion** *(only if this layer replaces or subsumes another)* | Adopt this layer *and* delete the weaker layer it supersedes. What tests-to-delete fall out? |

Each alternative produces: gate specification, threshold and reporting shape, CI integration sketch, rollout plan, trade-offs.

**3c. Compare and recommend.** Contrast on:

- **Discipline floor** — Where does this layer start saying "no"?
- **False-positive rate** — How often does this gate fail for non-bug reasons?
- **Maintainer cost** — Who owns the threshold; how often is it expected to move?
- **Cross-layer effect** — Does adopting this make other layers redundant (delete them) or stronger (keep them)?

Make an **opinionated recommendation**. Optionally propose a hybrid (e.g. "ratchet-only for 4 weeks, then hard gate at the ratchet ceiling").

**3d. Update CONTEXT.md / ADRs** if the conversation produces durable decisions. If the candidate is rejected with a load-bearing reason ("we don't gate mutation kill-ratio because the runner takes 40 minutes and that's load-bearing for our deploy cadence"), draft an ADR so the layer isn't re-suggested.

**3e. Hand off.** When an adoption plan is agreed, output:

- **Adoption plan** suitable for `/bruhs:cook` — what to install, what to configure, what to wire into CI, in what order
- **Gate spec** — exact threshold, exact CI step shape, exact failure message
- **Tests-to-delete list** — old advisory checks or shallow tests that this layer makes waste
- **Rollback plan** — what to do if false-positive rate is too high in the first week
- **Cross-reference** — which other layers this strengthens; whether `/bruhs:drill` should re-run after adoption

---

## The 8 Layers

The layers `/bruhs:drill` reasons about. Tool-agnostic by design — pick the runner in Phase 3, not in Phase 2.

| # | Layer | Catches | Discipline floor |
|---|---|---|---|
| 1 | **Acceptance specs** | Intent drift — "works in dev" with no executable definition of done. Behaviour-level specs (Gherkin-style or equivalent) describe end-to-end behaviour that humans and AI can both author and read. | At least one executable scenario per user-visible feature. Gated. |
| 2 | **Unit tests** | Regressions in module behaviour. Authored against the **module's interface** (see `practices/architecture-deepening.md`), not its internals. AI is allowed and expected to draft these — the discipline is that they're reviewed, asserted, and not test-past-the-interface. | A test exists at the interface of every module that has one. Gated indirectly via the coverage gate. |
| 3 | **Coverage gate** | Untested code lands. Coverage measured on *changed lines* (per PR), not total — the only meaningful number. | Hard gate at a threshold the team commits to; no `continue-on-error`. |
| 4 | **Mutation runner** | Tests that exist but assert nothing meaningful. Introduces small program changes and checks the suite catches them — produces a kill ratio. The kill ratio is the only number that proves coverage is doing work. | Kill ratio measured on changed lines per PR, gated at a threshold. Or scheduled (not per-PR) with a ratchet-only gate. |
| 5 | **Complexity composite** | High-complexity / low-coverage hotspots. Combines cyclomatic / cognitive complexity with coverage so the worst-of-both code is visible. (The "CRAP" idea — high-risk code with no safety net.) | A list of hotspots produced per PR; gate on "no new hotspot above X". |
| 6 | **Architecture checker** | Layer / dependency rule violations — callers reaching past the architecture an ADR committed to. The rule set IS the architecture, machine-checked. | Rule set committed in-repo; CI fails on any violation. |
| 7 | **Test-code linter** | Rot in test files themselves — AI-generated test code that becomes a second, untyped, unreviewed codebase. Applies the production lint + type config to test files. | Test files are not excluded from lint/type config; same gate as production code. |
| 8 | **CI orchestrator** | Discipline collapse. Without it, every other layer is opt-in. Runs every layer as a hard gate; nothing in `continue-on-error: true` unless the team has explicitly chosen advisory for that layer. | Every gate above runs on every PR; failures block merge. |

The 8th is the load-bearing one. Layers 1–7 without a real orchestrator are decoration.

---

## Output Shapes

### Phase 2 output (candidate list)

```
Adoption candidates for apps/web

1. Mutation runner is absent
   Layer: mutation
   Current state: absent
   Evidence: no mutation config, no CI step, coverage reports 84% line coverage
   Bug class it would catch: tests that exist but assert against the wrong thing;
                             AI-generated test scaffolding with `expect(true).toBe(true)`
                             survivors that look like coverage but verify nothing
   Proposed adoption: kill-ratio gate on changed lines per PR
   Gating posture: advisory for 2 weeks to establish baseline, then hard gate at baseline - 5%
   Cross-layer effect: makes the existing coverage gate meaningful — replaces "84% covered"
                       (which means little) with "84% covered, kill ratio 71%" (which means tests assert)
   Rough effort: M

2. Architecture checker is absent — ADR-0004 (no UI → DB) unenforced
   ...

3. CI orchestrator runs every layer with `continue-on-error: true`
   Layer: orchestrator
   Current state: advisory
   Evidence: .github/workflows/ci.yml — typecheck, lint, test, coverage all have
             continue-on-error: true. Build is green when nothing fails *fatally*,
             not when nothing fails.
   Bug class it would catch: everything — discipline collapse across all layers
   Proposed adoption: remove continue-on-error from typecheck/lint/test/coverage; keep it only on the optional perf-regression step
   Gating posture: hard gate immediately
   Cross-layer effect: turns all existing advisory checks into real gates
   Rough effort: S

Which would you like to grill? (1-3, or 'all', or 'none')
```

### Phase 3 output (chosen candidate, post-grilling)

```
Adoption plan: Mutation runner

Gate (recommended — Alternative B, ratchet-only):
  Step: pnpm test:mutate -- --changed-since=origin/main
  Threshold: kill ratio on changed lines >= max(70%, last_main_kill_ratio - 2%)
  Failure message: "Kill ratio 64% on changed lines; gate is 70% (or main baseline 73%)."
  Runs: every PR
  Budget: 8-minute timeout; if it times out, the gate fails

Why B over A/C:
  - A (strict day 1 at 80%) would block ~6 of the last 10 PRs based on retroactive analysis;
    too noisy, team would learn to disable it.
  - B (ratchet-only) starts at the current baseline (~71% spot-checked); the curve can only
    go up. Realistic first-day pass rate, but no regression.
  - C (scoped to billing/) would work but billing is already the best-tested area; scoping
    away from the actual weak spots defeats the point.

Cross-layer effect:
  - Coverage gate stays. The two numbers report different things — coverage = code touched,
    kill ratio = assertions doing work.
  - 14 unit tests in apps/web/src/lib/ flagged as suspicious by a pilot run (all mutants
    survive). Tests-to-delete after author review.

Rollback plan:
  - If kill-ratio reports vary by ±10% run-to-run (flaky mutants), drop to scheduled-only
    (nightly) with a ratchet on the nightly number rather than per-PR.

CI integration:
  - New job `mutation` in .github/workflows/ci.yml, after `test`.
  - No continue-on-error.
  - Required check in branch protection.

Hand-off: ready for `/bruhs:cook mutation-runner-adoption`.
```

---

## Anti-Patterns

What this command refuses to do — and what it should call out when others do it:

- **"Add a layer because we don't have it."** Adoption needs a concrete bug class it catches in *this* codebase. If you can't name one, don't propose it.
- **"Make it advisory first forever."** Advisory checks don't change behaviour. Adoption plans must commit to a hard-gate date or threshold ratchet. Indefinite advisory = decoration.
- **"Raise the threshold gradually."** Without a ratchet (gate at "no worse than baseline"), thresholds drift down to keep CI green. Ratchet or hard gate. Don't propose "we'll raise it later".
- **"Test the test code's coverage."** Recursion is a smell. Test-code linter checks structure (no commented-out tests, no `expect(true)`, types match); coverage of test code itself is not a layer.
- **"Add mutation testing to find more code to test."** Mutation finds *tests that don't assert*. If coverage is low, fix coverage first; mutation on a 30%-covered file produces noise.
- **Proposing a layer without checking the orchestrator.** If `continue-on-error: true` is the norm, adopting any layer is theatre. Fix layer 8 first or in the same PR.
- **Recommending tools in Phase 2.** Tool choice belongs in Phase 3, after the team has agreed which layer matters.
- **Recommending without an opinion.** "Here are three runners, you pick" is failure. Pick one. Defend it.
- **Leaving old tests when a deeper layer subsumes them.** If acceptance specs cover the integration path, the 14 brittle integration unit tests are waste — list them for deletion in the hand-off.

---

## Examples

### Example 1: Whole-project walk

```
> /bruhs:drill

Phase 1: Exploring apps/web ...
  Read .github/workflows/ci.yml (typecheck, lint, test, build — all continue-on-error: false ✓)
  Read package.json (vitest, no mutation runner, no acceptance-spec runner)
  Read bruhs:state block in CLAUDE.md (stack: nextjs, testing: vitest)
  Walked apps/web/src — 247 source files, 89 test files
  Layer state:
    1. Acceptance specs        — absent
    2. Unit tests              — present (89 files, vitest)
    3. Coverage gate           — advisory (reports, no threshold gate)
    4. Mutation runner         — absent
    5. Complexity composite    — absent
    6. Architecture checker    — absent (ADR-0004 "no UI → DB" not enforced)
    7. Test-code linter        — present (biome runs on test files too) ✓
    8. CI orchestrator         — gated for typecheck/lint/test/build ✓

Phase 2: 4 candidates

1. Coverage gate is advisory-only
   ...
2. Architecture checker is absent — ADR-0004 unenforced
   ...
3. Mutation runner is absent
   ...
4. Acceptance specs are absent
   ...

Which would you like to grill? (1-4, or 'all', or 'none')
```

### Example 2: Targeted grilling

```
> /bruhs:drill architecture-check

Phase 1: Scoped to architecture checker.
  Found: docs/adrs/0004-no-direct-db-from-ui.md committed
  Found: no enforcement — grep finds 3 `import { db } from` in apps/web/src/app/
  "What slips through": the ADR has been violated 3 times in 8 months;
                        each was caught in PR review (sometimes); none caught by CI.

Phase 2: 1 candidate

1. Architecture checker is absent — ADR-0004 unenforced
   Layer: architecture-check
   Current state: absent
   Evidence: ADR committed; 3 violations live in src/app/; no CI step
   Bug class it would catch: UI components importing from DB layer, exactly what ADR-0004 forbids
   Proposed adoption: rule set committed in-repo, CI fails on any violation
   Gating posture: hard gate from day 1 — fix the 3 violations as part of the adoption
   Cross-layer effect: encodes the ADR machine-readably; future ADRs in the same area
                       become rules, not prose
   Rough effort: M (3 violations to fix + rule set + CI step)

Grill it? (y/n)
```

---

## References

- **`practices/testing-infrastructure.md`** — The 8 layers, diagnostics, gating posture, rejected framings
- **`practices/architecture-deepening.md`** — Sibling discipline; shares "the interface is the test surface" and "replace, don't layer"
- **`commands/deepen.md`** — Companion command for the architecture lens
- **`commands/cook.md`** — Hand off implementation here
- **`commands/slop.md`** — Line-level audit (different lens)

External:
- Robert C. Martin, *Clean Craftsmanship* (the discipline list this command is shaped around)
- John Ousterhout, *A Philosophy of Software Design* (deep modules — the dual of layered suites)
- Michael Feathers, *Working Effectively with Legacy Code* (seams as the test surface)
