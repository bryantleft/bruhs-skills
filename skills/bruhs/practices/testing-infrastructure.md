# Testing Infrastructure

Shared vocabulary and decision rules for the 8-layer test safety net. Adapted from Uncle Bob's discipline list (acceptance specs, unit tests, coverage, mutation, complexity, architecture, test-code analysis, CI orchestration) and pairs with the deepening-modules discipline in `architecture-deepening.md`.

> A test suite is a layered safety net. Each layer catches a different bug class. A missing layer isn't covered by the others — it's just where bugs ship from.

Used by `/bruhs:drill`. Also pairs with `/bruhs:slop` (line-level audit), `/bruhs:deepen` (structural audit), and `/bruhs:cook` (when adopting a layer).

---

## Contents

- [Language (use these terms exactly)](#language-use-these-terms-exactly)
- [The 8 layers](#the-8-layers)
- [Diagnostics: spotting weak or missing layers](#diagnostics-spotting-weak-or-missing-layers)
- [Gating posture](#gating-posture)
- [Replace, don't layer](#replace-dont-layer)
- [The orchestrator is load-bearing](#the-orchestrator-is-load-bearing)
- [Rejected framings](#rejected-framings)

---

## Language (use these terms exactly)

Consistent vocabulary is the whole point. Don't substitute "testing strategy", "quality gate", "QA process", or "test pyramid".

| Term | Meaning | Avoid |
|---|---|---|
| **Layer** | One of the 8 components in the safety net. Each catches a distinct bug class. Scale-agnostic — applies to a package, an app, or a monorepo. | "kind of test", "test type" (too narrow) |
| **Hard gate** | A check that fails the build. Advisory checks (warnings, dashboards, weekly reports) don't count as gates. | "quality gate" (overloaded with vendor meaning) |
| **Discipline floor** | The minimum threshold a layer enforces in CI. Below the floor, the layer is decoration. | "target", "goal" (too aspirational) |
| **Kill ratio** | For mutation testing: of N introduced mutants, how many tests caught. The only number that proves coverage is doing work. | "mutation score" (used by some tools to mean other things) |
| **Architecture rule** | A machine-checkable constraint on module dependencies. Encodes an ADR so it's enforced, not just documented. | "lint rule" (too small), "design rule" (too vague) |
| **Test-code linter** | Static analysis applied to test files themselves. Keeps AI-generated test code from rotting into a parallel untyped codebase. | "test smell detector" (different concept) |
| **Orchestrator** | The CI step that runs every layer as hard gates. The 8th layer. Without it, every other layer is opt-in. | "pipeline", "workflow" (too generic) |
| **Ratchet** | A gate posture: "no worse than baseline". The floor can rise but never fall. Used when a hard threshold would block legacy code. | "trend gate" (rarer term) |

### Relationships

- A **Layer** has a **Discipline floor** and a **Gating posture** (advisory / hard / ratchet).
- The **Orchestrator** runs every Layer's gate.
- A Layer in `continue-on-error: true` is **advisory** regardless of what its config claims.
- **Kill ratio** is the discipline floor for the mutation layer.
- **Architecture rules** are the discipline floor for the architecture-check layer.

---

## The 8 layers

Each layer has: a bug class it catches, a discipline floor, and a typical failure mode if missing or advisory.

### 1. Acceptance specs

**Catches:** intent drift. End-to-end behaviour that humans and AI can both author and read — typically Gherkin-style scenarios, or any equivalent executable behaviour spec.

**Discipline floor:** at least one executable scenario per user-visible feature, gated.

**Failure mode when missing:** "works in dev" claims with no executable definition of done. PMs and engineers debate intent in PR review instead of in the spec.

**Failure mode when advisory:** specs exist as documentation; nobody runs them; they rot.

### 2. Unit tests

**Catches:** regressions in module behaviour. Authored against the **module's interface** (see `architecture-deepening.md`), not its internals. AI is allowed and expected to draft these — the discipline is review and review and review, not "AI didn't write it".

**Discipline floor:** a test exists at the interface of every module that has one. Gated indirectly via the coverage layer.

**Failure mode when missing:** bugs land in code paths nobody's covering; AI implementations regress silently.

**Failure mode when tests test past the interface:** the suite breaks on every internal refactor; tests become a tax on improvement instead of a safety net.

### 3. Coverage gate

**Catches:** untested code landing. Coverage measured on **changed lines per PR**, not total — the only meaningful number, because total coverage moves slowly enough to hide regressions.

**Discipline floor:** hard gate at a threshold the team commits to; no `continue-on-error`.

**Failure mode when missing:** new code lands with 0% coverage and nobody notices until the bug.

**Failure mode when advisory:** the number is reported; the curve trends down; nobody pushes back.

**Anti-pattern:** total coverage threshold ("80% overall"). It's the wrong number — large untested PRs get hidden by old well-tested code.

### 4. Mutation runner

**Catches:** tests that exist but assert nothing meaningful. Introduces small program changes ("mutants") and checks the suite catches them. Produces a **kill ratio** — the only number that proves coverage is doing work.

**Discipline floor:** kill ratio measured on changed lines per PR and gated. *Or* scheduled (not per-PR) with a ratchet-only gate.

**Failure mode when missing:** coverage looks high but tests assert almost nothing — AI scaffolding survives because `expect(true).toBe(true)` passes and counts as coverage.

**Failure mode when advisory:** the number is reported in a dashboard nobody reads.

**Cost:** mutation runs are slow. Acceptable to schedule (nightly) instead of per-PR if PR latency is a constraint, but the ratchet gate must still apply to the scheduled run.

### 5. Complexity composite

**Catches:** high-complexity / low-coverage hotspots — the worst-of-both code, where bugs are most likely *and* the suite is weakest. (Originates as Alberto Savoia's "CRAP" — Change Risk Anti-Patterns — the combo of cyclomatic complexity with coverage.)

**Discipline floor:** a list of hotspots produced per PR; gate on "no new hotspot above X".

**Failure mode when missing:** the worst code accumulates quietly. Nobody knows where the risk concentrates.

**Failure mode when advisory:** hotspot list grows; nobody reads it.

### 6. Architecture checker

**Catches:** layer / dependency rule violations. The rule set IS the architecture, machine-checked. Encodes ADRs so they're enforced, not just documented.

**Discipline floor:** rule set committed in-repo (same file or close to the ADRs that justify the rules); CI fails on any violation.

**Failure mode when missing:** ADRs erode. "We agreed UI never imports from the DB layer" is enforced by code review (inconsistently) and never by CI.

**Failure mode when advisory:** violations accumulate; ratcheting back becomes a project.

**Typical rules:** layer boundaries (UI → app → domain → infra), forbidden imports (production code can't import test code), cycle prevention.

### 7. Test-code linter

**Catches:** rot in test files themselves. AI-generated test code can become a second, untyped, unreviewed codebase. The fix is to apply the production lint + type config to test files.

**Discipline floor:** test files are not excluded from lint / type / formatter config. Same gate as production code.

**Failure mode when missing:** test files diverge from production style; commented-out tests accumulate; `expect(true).toBe(true)` survives review because nobody reads test diffs as carefully.

**Anti-pattern:** "we lint test code less strictly because tests are noisy". The noise is the smell.

### 8. CI orchestrator

**Catches:** discipline collapse. Runs every layer as hard gates. Without it, every other layer is opt-in — and "opt-in discipline" is a contradiction.

**Discipline floor:** every gate above runs on every PR. Nothing in `continue-on-error: true` unless the team has explicitly chosen advisory for that layer with a documented reason.

**Failure mode when missing or advisory:** the CI badge is green when nothing fails *fatally*, not when nothing fails. Teams learn the badge is unreliable, stop trusting it, and stop checking it.

**The 8th layer is load-bearing.** Layers 1–7 without a real orchestrator are decoration.

---

## Diagnostics: spotting weak or missing layers

Walk the project organically — CI workflow files, package config, test config, ADRs. Note evidence, not vibes:

| Smell | What it looks like |
|---|---|
| **Acceptance gap** | No executable spec of "done"; behaviour is defined by whatever the test happens to assert |
| **AI-test drift** | Many test files added by AI but reviewed only for "looks correct"; assertions over-fit to current impl |
| **Coverage blind** | Coverage uninstrumented OR reported in PR comments but no threshold gate |
| **Coverage on total only** | Threshold gate exists but measures total coverage; a large untested PR sneaks past because old well-tested code dilutes the number |
| **Mutation absent** | Coverage > 80% with no kill-ratio measurement — "tests" that assert nothing meaningful |
| **Hotspots invisible** | No way to find high-complexity / low-coverage code; the worst-of-both hides |
| **Architecture rules unenforced** | ADRs in `docs/adrs/`; no CI step that would fail when an ADR is violated |
| **Test code unlinted** | `lint.ignore` includes `**/*.test.*` or test files don't appear in CI's lint step output |
| **Orchestrator advisory** | `.github/workflows/*.yml` has `continue-on-error: true` on layers the team thinks of as gated |
| **Threshold drift** | Coverage threshold has been lowered in the last 6 months to keep CI green |
| **Exclusion drift** | Architecture rule exclusion list has grown; mutation runner's "skip" list has grown |

**Apply the "what would slip through" test** before proposing adoption. If you can't name a concrete bug class this layer would catch in *this* codebase, don't propose it. Vague "best practice" isn't a candidate.

---

## Gating posture

Three legitimate postures for any layer:

### Hard gate

A failure of this layer fails the build. The default for layers 2 (via coverage), 3, 6, 7, 8. The aspirational state for 1, 4, 5.

### Advisory

The layer runs and reports, but doesn't fail the build. **Use only as a time-boxed step toward a hard gate or ratchet.** Indefinite advisory = decoration.

Acceptable reasons for indefinite advisory (rare):

- The layer's runtime cost exceeds the team's PR latency budget and a scheduled run won't catch the bug in time.
- The layer's false-positive rate is genuinely high in this domain (e.g. mutation runner on UI code where many mutants are equivalent).

If you accept indefinite advisory, write an ADR explaining why.

### Ratchet

The gate enforces "no worse than baseline". The floor can rise but never fall. Used when a hard threshold would block legacy code that's expensive to bring up to the line.

Ratchet posture is honest about the starting state and locks in improvement. Don't propose "we'll raise it later" — propose a ratchet.

### Posture decision rules

- **New layer + new project** → hard gate at production-grade threshold immediately.
- **New layer + existing project with legacy debt** → ratchet (the floor is the current baseline, can only go up).
- **New layer + existing project that's actively healthy** → hard gate at a threshold slightly below current (so the first day is green; the floor ratchets up from there).
- **High-cost layer (mutation, full-suite e2e)** → scheduled with ratchet, plus a fast subset on each PR.

---

## Replace, don't layer

Borrowed verbatim from `architecture-deepening.md` because the same discipline applies:

- Old tests on shallow modules become **waste** once tests at the deepened module's interface exist — delete them.
- Old advisory checks become **waste** once a hard gate exists on the same layer — delete them; the dashboard isn't load-bearing.
- Tests should survive internal refactors — they describe behaviour, not implementation. **If a test has to change when the implementation changes, it's testing past the interface.**

Every adoption hand-off includes a **tests-to-delete list** for the same reason every deepening hand-off does: keeping the waste around is how discipline rots.

---

## The orchestrator is load-bearing

The 8th layer doesn't fit the same shape as 1–7. It isn't a layer that catches a bug class — it's the layer that makes the other layers count.

**Discipline floor:**

- Every gate runs on every PR (or every gate has a documented scheduled-only reason).
- No `continue-on-error: true` on any layer except those with an ADR explaining why.
- Required checks in branch protection match the gates the team thinks are gated.
- The CI failure message names which layer failed and what the gate was, so the failure is actionable on first read.

**Failure mode if the orchestrator is wrong:**

- Layers exist; CI is "green"; bugs ship at the same rate as before adoption.
- Team morale drops because adopting a layer didn't change outcomes — the layer gets blamed, not the orchestrator.
- Future adoption proposals face headwinds: "we tried adopting X, it didn't help".

Fix the orchestrator first (or in the same PR as the first adoption). Otherwise everything else is theatre.

---

## Rejected framings

- **"The test pyramid".** A pyramid implies a count distribution (many unit, fewer integration, few e2e). The 8-layer model isn't about counts — it's about which bug class each layer catches. A team can have an "ideal" pyramid count and still ship bugs because layers 1, 4, 5, 6 are missing.
- **"100% coverage".** Coverage is a leading indicator, not a target. 100% coverage with kill ratio 0 is worse than 70% coverage with kill ratio 90 — the second suite actually asserts.
- **"Mutation testing is too slow to be useful".** It is too slow for per-PR full-suite. It is not too slow for changed-lines-only per PR, or for nightly with a ratchet gate. The honest design choice is *when* mutation runs, not *whether*.
- **"Architecture rules can live in ADRs".** ADRs document decisions. Architecture rules enforce them. They are not the same artefact. ADRs without rules are aspirational; rules without ADRs are unexplained.
- **"AI writes the tests, so we don't need a test-code linter".** This is exactly when you need it. AI generates plausible-looking test code at scale; the linter is the only thing that keeps it honest.
- **"CI is just plumbing, not a layer".** Plumbing that doesn't deliver water is the leak. The orchestrator is where the discipline lives or doesn't.
- **"We'll add gates once the suite is healthy".** The suite gets healthy *because* gates exist. Gates first, then the suite improves to meet them — not the other way around.
