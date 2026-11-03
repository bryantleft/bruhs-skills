# Pull Request Review

How to author and review PRs. Distilled from Google's [eng-practices](https://google.github.io/eng-practices/), the [Conventional Comments](https://conventionalcomments.org) spec, GitHub's staff engineering writeups, and the empirical research on PR size and review latency.

**Used by:**
- `peep` — primary lens for analyzing review comments and proposing fixes
- `yeet` — PR description quality and reviewer assignment
- `cook` — informs final pre-PR self-review
- `slop` — review-specific anti-patterns

## Contents

- [Core Principle](#core-principle)
- [PR Size: The Single Strongest Predictor](#pr-size-the-single-strongest-predictor)
- [What to Look For (in priority order)](#what-to-look-for-in-priority-order)
- [Conventional Comments — The Format](#conventional-comments--the-format)
- [Reviewer Workflow](#reviewer-workflow)
- [Review Output](#review-output)
- [Reviewer Etiquette](#reviewer-etiquette)
- [Author Etiquette](#author-etiquette)
- [What](#what)
- [Why](#why)
- [How](#how)
- [Test plan](#test-plan)
- [Screenshots / diagrams](#screenshots--diagrams)
- [Disagreement](#disagreement)
- [Automation](#automation)
- [Anti-Patterns to Detect](#anti-patterns-to-detect)
- [Review for Different Change Types](#review-for-different-change-types)
- [Quick Checklist](#quick-checklist)
- [References](#references)

---

## Core Principle

> **Code review's job is to keep the codebase healthy over time. The author's job is to be reviewable. Neither is the boss of the other.**

From Google's eng-practices:
> *"In general, reviewers should favor approving a CL once it is in a state where it definitely improves the overall code health of the system being worked on, even if the CL isn't perfect."*

Two failure modes:
- **Author drag** — a reviewer who insists on perfection makes engineers stop improving the code
- **Health drag** — a reviewer who rubber-stamps lets entropy accumulate

The bar is *improvement*, not *perfection*.

---

## PR Size: The Single Strongest Predictor

Empirical research is unambiguous:

| PR size | What happens |
|---------|--------------|
| < 50 LOC | Reviewed in median ~ 1 hour, almost zero post-merge defects |
| 50–200 LOC | The sweet spot — high-quality reviews, low defect rate |
| 200–500 LOC | Review time roughly doubles; defects start to creep in |
| 500+ LOC | Reviewers skim; post-merge defect rate **rises sharply** |
| 1000+ LOC | Effectively unreviewable; rubber-stamps are the norm |

> *"Median time-to-review doubles for every additional 100 lines changed. PRs over 500 lines have a much higher rate of post-merge defects."* — Swarmia / Stripe / Shopify research, 2025

### Splitting strategies

When you find yourself opening a 600-line PR:

| Pattern | Use when |
|---------|----------|
| **Stacked PRs** | Logical sequence: refactor → migration → feature. Each PR is reviewable; later ones depend on earlier |
| **Behind a flag** | Land the implementation dark, then a separate PR enables it |
| **Pure refactor first** | Land the no-behavior-change motion, then the behavior change reads cleanly against it |
| **Test-only PR** | Land the failing test that demonstrates the bug, then the fix |

If you can't split it because *everything* is interdependent, that's a design smell — the splitting friction usually points at the right boundaries.

---

## What to Look For (in priority order)

Cribbed and adapted from Google's [What to Look For](https://google.github.io/eng-practices/review/reviewer/looking-for.html):

| Priority | Question | Why first |
|----------|----------|-----------|
| **0. Existing tool** | Does an installed tool, helper, or established pattern already do this job? | Zero prior instances of a pattern is evidence it doesn't belong, not that the PR pioneers it |
| **1. Design** | Does the change belong here? Is it integrated correctly? | Wrong design wastes everything below |
| **2. Functionality** | Does it do what it claims? Edge cases handled? | Bugs are cheaper here than in prod |
| **3. Complexity** | Could it be simpler? Over-engineered for hypothetical futures? Does it destroy an invariant only to rebuild it (partition then re-sort, group then flatten)? | The rebuild reads as load-bearing; the fix usually deletes both halves |
| **4. Tests** | Are the tests correct, focused, and likely to catch regressions? | Tests are the contract |
| **5. Naming** | Do names communicate intent? | Bad names rot fastest |
| **6. Comments** | WHY (not WHAT) where non-obvious? Stale comments removed? | See _common.md |
| **7. Style** | Consistent with repo conventions? Formatter clean? | Mostly automated; comment only when not |
| **8. Documentation** | If behavior changed, did docs/README/CHANGELOG follow? | Drift is silent |

> Reviewers should be especially vigilant about **over-engineering** — code more generic than the current need.

---

## Conventional Comments — The Format

Use [Conventional Comments](https://conventionalcomments.org) so authors can triage quickly. Format:

```
<label> [decoration]: <subject>

[discussion]
```

### Labels (what kind of comment is this?)

| Label | Meaning |
|-------|---------|
| `issue` | A defect, risk, or standard violation with concrete harm |
| `suggestion` | A specific change; the author chooses |
| `todo` | Small, uncontroversial required change (missing test, rename, import) |
| `question` | Genuine uncertainty about *this PR*. Not speculation about hypothetical futures |
| `nitpick` | Trivial preference (style, typo, naming). Always `(non-blocking)` |
| `chore` | Required task that isn't code (changelog, owner entry) |
| `praise` | Optional. Specific and earned, never filler or a quota |

`thought`, `note`, `typo` and `polish` are left out on purpose. `thought` and `note` carry no action and dodge the evidence bar, so they collect half-baked observations: a concrete idea is a `suggestion`, durable future work is a linked follow-up ticket, anything else gets dropped. Typos are `nitpick`s; polish is a `suggestion`.

### Decorations (what's the urgency?)

| Decoration | Meaning |
|------------|---------|
| `(blocking)` | Must be addressed before merge. Reserve for `issue` and occasionally `todo` |
| `(non-blocking)` | Can be addressed now or in a follow-up |
| `(if-minor)` | Address only if cheap |

### Examples

```
nitpick (non-blocking): `userIds` over `userIdList`, to match the rest of the file.

suggestion (non-blocking): a `Map<string, User>` would drop the linear scan.

Verified: called once per row in renderRows, 2k rows in the fixture.

issue (blocking): this route skips the session check, so a logged-out request
reaches the handler.

Verified: curl without a cookie returns 200 and the user list on this branch.

question: what happens when `request.user` is null here?

Read at handlers/profile.ts:18; no guard upstream in the middleware chain.
```

### Why this matters

Without explicit labels, every comment looks the same urgency. Authors waste time arguing nits, miss real issues in the noise, or block on opinions. The format costs nothing and removes the entire class of "wait, was that blocking?" miscommunication.

> Decoration is required on every `issue`, `suggestion` and `todo`; a missing one reads as blocking. Reviewers earn the right to block by being right.

---

## Reviewer Workflow

Know what the PR is *supposed* to do before critiquing it. Understanding the change is the dominant cost of review (Bacchelli & Bird, MSR 2013), so context is the highest-leverage step.

### 1. Gather context

- **Read the PR body and both comment streams** (`gh api repos/{o}/{r}/issues/<n>/comments` and `.../pulls/<n>/comments`). Settled threads aren't re-raised; cite an existing comment instead of restating it.
- **Follow every link** in the PR body and ticket: the ticket and its attachments, error-tracker items, design docs, threads. They are ground truth; the prose summary is a subset.
- **History of the touched files:** `gh pr list --search "in:file <path>" --state merged --limit 10` surfaces prior attempts, reverts, and recurring bugs.
- **Cite the source** when a finding rests on context outside the diff, or the author can't tell you didn't make it up.

### 2. Check out the branch

The diff shows what changed; the branch shows the world after the change.

```bash
git status --short                  # dirty? use a worktree, never silently stash
git worktree add ../review-<n> && cd ../review-<n> && gh pr checkout <n>
git rev-parse HEAD                  # record the reviewed SHA
```

On the branch: grep for other callers of anything removed, read config/flags/env guards that change blast radius, and read called code in full. If checkout fails, review the diff and say so under *Not verified*.

### 3. Check scope

Render the ticket's acceptance criteria as a checklist: ✅ met (cite file:line), ⚠️ partial, ❌ missing, ❓ unverifiable from code. No criteria? Infer them and say you did. Also flag scope creep, work dropped without a stated follow-up, and a fix for a different problem than the ticket describes. Product-level gaps (empty/error states, edge cases the criteria skipped, inconsistency with sibling features) are `question:`s; the author and PM own those calls.

### 4. Read in order

1. **Broad pass:** read the diff once, no notes, to map it.
2. **Design pass:** open the biggest or most architectural file in full. If the approach is wrong, send only that feedback and stop; line comments on a design that will change are wasted.
3. **Comprehensive pass:** biggest file, then its tests, then the rest in call-graph order, not diff order.

### 5. Investigate, then validate

Investigate aggressively: follow every suspicious pattern and list candidates without pre-filtering. Then validate each one; **a finding is a hypothesis until a probe confirms it.**

| Claim type | Required evidence | No evidence → |
|---|---|---|
| Behavioral ("bug on null") | Failing repro on the branch | `question:` or drop |
| Performance ("N+1", "missing index") | Query count, `EXPLAIN`, benchmark | `question:` |
| Coverage ("not tested") | Mutate the line, rerun; suite still passes | `question:` |
| External ("the docs say X") | Fetch the doc, quote the passage | Drop the citation |
| Structural (layering, dead code) | grep result + line numbers | Drop |
| Design | The ticket, doc, or decision that frames it | `question:` |

**A probe that contradicts the hypothesis drops the finding** rather than softening it into a `question:`. If a probe can't run, try alternatives first (fetch the source, install the dependency, ask for seed data). Only a physical external block (user input, private doc, third-party answer) earns a place under *Not verified*.

Special cases that produce the most false positives:

- **Re-read the PR body before any `question:`.** Authors often pre-empt it under risks or rollout. Answered → drop.
- **Spot-check every cited path outside the diff** (`ls`, `grep`). Investigators invent plausible paths.
- **A repro only proves a bug if its input is reachable in production.** State built by hand (factory overrides, raw column writes) proves behavior on that input, not that the input occurs. When a field's meaning comes from an external system, read the code that decides it before calling it a bug.
- **Walk upstream before patching an output.** A wrong derived value usually reflects a wrong-shaped input that also feeds other consumers.
- **Dead-code claims need an intent search.** grep proves nothing calls it, not that nothing intends to: check sibling tickets, docs and the PR body for a planned consumer.
- **"Use X instead" needs its blast radius.** grep every caller and confirm the full contract (signature, null vs empty, throw vs return, side effects). Can't trace it? Ask instead.
- **"Looks wrong" may be deliberate.** Search docs and threads for the specific constant or flag before flagging. A finding that contradicts a recorded decision is wrong by default.
- **Pre-existing patterns aren't justification on safety surfaces.** For authorization, atomicity, audit trails, PII, injection and mass assignment, an existing same-file gap is a second finding, not a reason to drop the first.

**Target 3–8 findings.** Rank by severity and production impact, not by hypothesis length, recency, or how long the probe took.

---

## Review Output

### Comments

- **One concern per comment**, with the `<label> [decoration]: <subject>` line, a *why* body, and a one-line **validation note** stating the probe and its result. Every label carries the note; a finding without one is dropped.
- **No arrows (`→`) or em dashes (`—`) in finding bodies.** Split clauses into sentences; turn sequences into a numbered list.
- **Critique the code, never "you".** Ask rather than direct when the author may have a reason.
- **Don't explain code back to the author.** If it needs explaining, ask for the code or a comment to change so future readers get it.
- **Skip filler.** "Branch is behind main" is noise (GitHub diffs against the merge base and shows the badge) unless a specific conflict or base-side fix matters. Lint-owned style is noise.

### Shape

Locally: acceptance-criteria checklist, then findings grouped blocking-first (`issue (blocking)`, `issue`/`suggestion`, `todo`, `question`, `nitpick`), then *Not verified*, then the verdict. Omit empty groups.

Close with a **ship verdict**, a judgment call with its reason:

| Verdict | When |
|---|---|
| ✅ Ship | No `issue (blocking)` or `todo (blocking)` |
| ✅ Ship with follow-ups | Safe to merge (flag off, additive) but named items must land before rollout |
| 🛑 Block | At least one blocker; name what unblocks it |

Before stating it, re-fetch the head SHA (`gh pr view <n> --json headRefOid`). If it moved, re-validate the findings the new commits touch.

### Posting

Output stays local. Post, approve or request changes only after the user asks and confirms; autonomy framings ("address feedback until clean") authorize work, not GitHub writes. When posting, default to inline comments with an empty top-level body, bold the label prefix, and keep the acceptance checklist off GitHub. Use ` ```suggestion ` blocks for one-click mechanical fixes.

---

## Reviewer Etiquette

### DO

- **Reply within one business day** — long review cycles are the #1 reason PRs balloon
- **Approve with non-blocking comments** when the change is net positive — let the author land it and address polish
- **Ask, don't accuse** — `"What if X is null here?"` over `"This is broken."`
- **Suggest code blocks** with GitHub's `suggestion` syntax when you have an exact alternative — the author can apply with one click
- **Pull the branch and run it** for non-trivial UI/behavior changes — diffs lie, behavior doesn't
- **Defer to the author on judgment calls** when both approaches are valid
- **Praise only when it's specific** — `praise:` for something worth copying, never as a quota

### DON'T

- **Don't review while annoyed** — wait until you're not
- **Don't do a "drive-by"** — partial reviews leave the author guessing
- **Don't repeat the same comment** in 10 places — make it once, link the rest: `"Same as line 42."`
- **Don't make unrelated requests** — "while you're in there" is how PRs balloon
- **Don't gatekeep on personal style** when the team has no convention — write the convention down first, then enforce it
- **Don't leave only nits** on a major change — engage the design so the author trusts the read was thorough
- **Don't pad** — a clean PR gets a short review

---

## Author Etiquette

### Before opening the PR

- [ ] Self-review the diff first — half the comments you'd get, you can fix
- [ ] Title is conventional (`feat(scope): description`); description has *Why*, not just *What*
- [ ] Test plan in the description — what you tested, what you didn't
- [ ] Linked to ticket / issue
- [ ] CI green (or you note what's flaky)
- [ ] UI changes: verified with `/expect` and a `## UI preview` (screenshots + recording) in the body — see `practices/ui-preview.md`. Architecture changes: diagram (try `/bruhs:doodle pr`)
- [ ] Under 400 lines, or you've split it, or you've explained why it can't be split

### Description template

```markdown
## What

<one-paragraph summary of behavior change>

## Why

<the problem this solves; link to ticket/incident/discussion>

## How

<the design decision, alternatives considered, trade-offs>

## Test plan

- [ ] <specific scenario you verified>
- [ ] <edge case you checked>
- [ ] <thing you explicitly didn't test and why>

## Screenshots / diagrams

<for UI or architectural changes>

Closes BNLE-123
```

### Responding to review

- **Reply to every comment** — even with just `Done` or `👍` (use GitHub's "Resolve" button)
- **Push back on weak feedback** — politely. `"I considered X but went with Y because Z. Happy to switch if you feel strongly."`
- **Don't argue nits** — apply or note "(skipping nit, will follow up)" and move on
- **Group your responses** — push fixes as one or two commits, not one per comment
- **Re-request review** explicitly when you've addressed everything (don't make reviewers guess if you're done)
- **For long threads**, state the resolution: `"Going with the original approach — we agreed offline that <reason>."`

---

## Disagreement

When author and reviewer disagree, Google's protocol:

1. **Sync** — try to reach consensus in a comment thread or quick call
2. **Defer to expertise** — if one of you owns this code, weight their take
3. **Defer to the author** if both approaches are equally valid (data or design principle, not preference)
4. **Escalate** to a tech lead / arch council if you can't reach agreement and it matters

What *not* to do:
- Stalemate — leaving the PR open in conflict for days
- Approve grudgingly while logging a complaint elsewhere
- Override reviewer with admin merge

---

## Automation

### CODEOWNERS

Maintain `.github/CODEOWNERS` so the right reviewers are auto-requested:

```
# Backend
/services/auth/  @bryantleft @auth-team
/services/api/   @api-team

# Frontend
/apps/web/       @frontend-team
/packages/ui/    @design-system-owners

# Infra
/.github/        @platform-team
/terraform/      @platform-team
```

### Required checks

Before review humans look at it, the bot should have already verified:
- Build passes
- Tests pass
- Linter clean (Biome, ruff, clippy)
- Type-checker clean (tsc, mypy/ty, cargo check)
- No secrets committed (gitleaks / truffleHog)
- Coverage doesn't regress (optional)

### AI pre-review

Pattern adopted at Stripe, Shopify, GitHub: an AI reviewer runs first and posts comments, then a human reviews. Reports a 30–40% reduction in human review round-trips. The AI doesn't approve — it surfaces obvious issues so the human can focus on design.

---

## Anti-Patterns to Detect

| Smell | Symptom | What to do |
|-------|---------|-----------|
| **Rubber stamp** | Approval within seconds of opening | Re-request from someone who'll actually look |
| **Bikeshedding** | 30 comments on naming, 0 on the algorithm | Move nits to a follow-up; focus on design |
| **Drive-by nit** | Single nit comment from someone not on CODEOWNERS | Acknowledge but don't let it block |
| **Scope creep** | Reviewer asks for unrelated improvements | Politely decline: `"Good idea — tracking in BNLE-456 for follow-up"` |
| **Ghost PR** | Open > 5 days with no movement | Author re-pings or closes; reviewer apologizes or hands off |
| **Mega-merge** | 1000+ LOC PR | Send back with a splitting suggestion; don't review |
| **"LGTM 🚀" with no read** | Approver hasn't looked | Reviewer should retract; team should address |

---

## Review for Different Change Types

### Bug fixes

- Is there a regression test? (If not, push back)
- Is the root cause fixed, or just the symptom?
- Are similar bugs likely elsewhere?

### Refactors

- Is behavior provably unchanged? (Tests pass; ideally no test changes either)
- Was the refactor necessary, or polish-driven?
- Did public APIs change? (If yes, this isn't a pure refactor)

### Features

- Is the user-visible behavior documented somewhere (README, docstring, type)?
- Are failure modes handled (or explicitly out of scope)?
- Does it match the spec / ticket?

### Performance changes

Distinguish **anti-pattern fixes** from **claimed optimizations**:

**Anti-pattern fixes** (N+1 → eager load, `await`-in-loop → `Promise.all`, per-request client → singleton, sync I/O → async, missing index, unbounded concurrency → bounded). These don't need a benchmark — they're correctness-adjacent. Review checklist:
- Is the change a recognized anti-pattern → fast-path swap?
- Is correctness preserved?
- Are edge cases (empty input, single item, errors mid-batch) handled?

**Claimed optimizations** ("this is X% faster", "I rewrote this for speed"). These *do* need evidence:
- Is there a benchmark showing the improvement? (e.g. before/after p95, not a single timing)
- Is the optimization targeting a measured bottleneck?
- Is correctness preserved? Optimizations love to introduce subtle bugs.
- Is the complexity cost worth the gain? A 3% speedup that doubles code complexity usually isn't.

> The Knuth quote has a caveat: *"Yet we should not pass up our opportunities in that critical 3%."* Anti-pattern fixes are the 3%. Flag them aggressively; don't gate them behind benchmarks.

### Dependency updates

- Are the changelogs reviewed? Any breaking changes?
- Lockfile committed?
- Security advisories checked?

### Infra / config changes

- Reviewer should test in a non-prod environment
- Rollback plan documented
- Blast radius understood

---

## Quick Checklist

### Authoring
- [ ] PR < 400 LOC, or split, or justified
- [ ] Self-reviewed before requesting review
- [ ] Description includes Why + Test Plan
- [ ] Linked ticket; CI green
- [ ] UI: `/expect`-verified `## UI preview` (screenshots + recording, see `practices/ui-preview.md`); architecture: diagram
- [ ] Reviewer assigned (CODEOWNERS or manual)

### Reviewing
- [ ] Read the description first; understand the *Why*
- [ ] Followed linked ticket/resources; checked out the branch and recorded the head SHA
- [ ] Acceptance criteria rendered as a checklist
- [ ] Every finding validated by a probe, with a validation note
- [ ] Used Conventional Comments labels
- [ ] At most one design-level question; rest are tactical
- [ ] Ship verdict stated against the current head SHA
- [ ] Nothing posted without the user's confirmation

### Resolving
- [ ] Every comment replied to (resolved or discussed)
- [ ] Fixes pushed in 1–2 commits, not one per comment
- [ ] Re-requested review explicitly when done

---

## References

- [Google eng-practices — Code Review](https://google.github.io/eng-practices/review/) — the canonical reviewer/author guide
- [Conventional Comments](https://conventionalcomments.org/) — the labeling spec
- [GitHub blog: How to review code effectively](https://github.blog/developer-skills/github/how-to-review-code-effectively-a-github-staff-engineers-philosophy/) — staff engineer perspective
- [Software Engineering at Google, ch. 9](https://abseil.io/resources/swe-book/html/ch09.html) — long-form treatment
- [Banish "nitpick"](https://www.codetinkerer.com/2024/01/12/nitpick-code-reviews.html) — minority view worth reading
- [Bacchelli & Bird, *Expectations, Outcomes, and Challenges of Modern Code Review*](https://www.microsoft.com/en-us/research/publication/expectations-outcomes-and-challenges-of-modern-code-review/) — understanding the change dominates review cost
- [Cursor, *Building Bugbot*](https://cursor.com/blog/building-bugbot) — aggressive investigation plus a strict validation pass
- [Michael Lynch, *How to Do Code Reviews Like a Human*](https://mtlynch.io/human-code-reviews-1/) — critique code, not people
