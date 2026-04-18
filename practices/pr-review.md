# Pull Request Review

How to author and review PRs. Distilled from Google's [eng-practices](https://google.github.io/eng-practices/), the [Conventional Comments](https://conventionalcomments.org) spec, GitHub's staff engineering writeups, and the empirical research on PR size and review latency.

**Used by:**
- `peep` — primary lens for analyzing review comments and proposing fixes
- `yeet` — PR description quality and reviewer assignment
- `cook` — informs final pre-PR self-review
- `slop` — review-specific anti-patterns

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
| **1. Design** | Does the change belong here? Is it integrated correctly? | Wrong design wastes everything below |
| **2. Functionality** | Does it do what it claims? Edge cases handled? | Bugs are cheaper here than in prod |
| **3. Complexity** | Could it be simpler? Over-engineered for hypothetical futures? | Future you will thank present you |
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
| `praise` | Highlight something genuinely good. Use sparingly so it lands |
| `nitpick` | Trivial preference. Author free to ignore |
| `suggestion` | Concrete proposal — author should consider but may decline |
| `issue` | Real problem the author should address |
| `question` | Honest question; might become an issue once answered |
| `thought` | Reflection that doesn't require action |
| `chore` | Process/cleanup ask (rebase, update changelog, etc.) |
| `note` | Pointer the author should read but no action needed |
| `typo` | Spelling/phrasing |
| `polish` | Quality improvement that doesn't change behavior |

### Decorations (what's the urgency?)

| Decoration | Meaning |
|------------|---------|
| `(blocking)` | Must be addressed before merge |
| `(non-blocking)` | Can be addressed now or in a follow-up |
| `(if-minor)` | Address only if cheap |

### Examples

```
nitpick: Consider naming this `userIds` to match the rest of the file.

suggestion (non-blocking): A `Map<string, User>` would let us drop the linear scan.

issue (blocking): This bypasses the auth check on line 42 — any logged-out user
can hit this endpoint.

praise: The fixture builder here is really clean — I'm going to copy this pattern.

question (blocking): What happens if `request.user` is null? I don't see the
guard.
```

### Why this matters

Without explicit labels, every comment looks the same urgency. Authors waste time arguing nits, miss real issues in the noise, or block on opinions. The format costs nothing and removes the entire class of "wait, was that blocking?" miscommunication.

> Default to `non-blocking` if you don't say otherwise. Reviewers earn the right to block by being right.

---

## Reviewer Etiquette

### DO

- **Reply within one business day** — long review cycles are the #1 reason PRs balloon
- **Approve with non-blocking comments** when the change is net positive — let the author land it and address polish
- **Ask, don't accuse** — `"What if X is null here?"` over `"This is broken."`
- **Suggest code blocks** with GitHub's `suggestion` syntax when you have an exact alternative — the author can apply with one click
- **Pull the branch and run it** for non-trivial UI/behavior changes — diffs lie, behavior doesn't
- **Defer to the author on judgment calls** when both approaches are valid
- **Praise good work** — use `praise:` so it doesn't read as sarcasm

### DON'T

- **Don't review while annoyed** — wait until you're not
- **Don't do a "drive-by"** — partial reviews leave the author guessing
- **Don't repeat the same comment** in 10 places — make it once, link the rest: `"Same as line 42."`
- **Don't make unrelated requests** — "while you're in there" is how PRs balloon
- **Don't gatekeep on personal style** when the team has no convention — write the convention down first, then enforce it
- **Don't leave only nits** on a major change — find at least one design-level question or `praise` so the author trusts the read was thorough

---

## Author Etiquette

### Before opening the PR

- [ ] Self-review the diff first — half the comments you'd get, you can fix
- [ ] Title is conventional (`feat(scope): description`); description has *Why*, not just *What*
- [ ] Test plan in the description — what you tested, what you didn't
- [ ] Linked to ticket / issue
- [ ] CI green (or you note what's flaky)
- [ ] Screenshots/diagrams for UI or architectural changes (try `/bruhs:doodle pr`)
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

- Is there a benchmark showing the improvement?
- Is the optimization targeting a measured bottleneck?
- Is correctness preserved? (Optimizations love to introduce subtle bugs)

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
- [ ] Screenshots/diagrams for UI/architecture changes
- [ ] Reviewer assigned (CODEOWNERS or manual)

### Reviewing
- [ ] Read the description first; understand the *Why*
- [ ] Pulled and ran (for non-trivial behavior changes)
- [ ] Used Conventional Comments labels
- [ ] At most one design-level question; rest are tactical
- [ ] Praised something genuine
- [ ] Approved with non-blocking comments OR clearly blocked with action items

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
