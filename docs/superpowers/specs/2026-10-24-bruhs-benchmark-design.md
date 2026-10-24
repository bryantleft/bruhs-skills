# bruhs benchmark — design

Date: 2026-10-24
Status: draft, awaiting approval (builder check done)

## Intent

Prove, with numbers someone else would believe, that a coding agent does better work with bruhs installed than the same model without it. "Better" means better against what each skill promises: features that actually work, audits that find real problems, UI that doesn't look AI-generated, copy without jargon, and "done" claims that are true. It does not mean "followed the bruhs ritual".

The result is the pitch for using bruhs: a headline chart per model plus side-by-side examples that make the difference obvious.

## Goals

- A/B comparison, same model, same task, same prompt: **bare** vs **bruhs**.
- Three models, each in its native agent CLI:
  - Claude Opus 5.5 in Claude Code (`claude -p`)
  - GPT-6.1-Sol in Codex (`codex exec`)
  - Grok 4.7 in Grok Build (`grok -p`)
- Tasks drawn mostly from real past work (recovered from session history), weighted toward what the user actually does: feature builds, UI polish, copy cleanup, verification, audits, debugging.
- Scoring that is mostly automated and objective, with blind judging only where taste is the point (UI, copy).
- Reproducible: anyone with the repo and API access can rerun it and get comparable numbers.

## Non-goals

- Ranking the three models against each other. The comparison that matters is bare vs bruhs within each model. Cross-model numbers will be visible but aren't the headline.
- Testing Linear, GitHub pushes, or PR creation end-to-end. Those touch external services; ship-style tasks are scored on the local result (commit, branch, PR body draft).
- Re-testing command activation and step adherence — that's what `evals/` already does.

## Anti-goals (would make this a failure even if it runs)

- **Rigged scoring.** No points for bruhs-specific behavior (creating a ticket, using bruhs vocabulary, printing a plan). Only outcomes a user would care about.
- **Cherry-picking.** Task list, rubrics, and run count are frozen before the first full run. Every run is reported, including ones where bruhs loses.
- **Training on the test.** If bruhs is changed in response to results, the claim must be re-proven on held-out tasks that weren't looked at.
- **Leaking private code.** Several source repos are private (mints, ogling, bruhs-ai, degrees-of-freedom). Published output must not include their source.
- **Hiding cost.** If bruhs makes runs slower or more expensive, the report says so.

## The two arms

Both arms get an isolated, fresh config home per run so the user's global skills (superpowers, impeccable, etc.) never leak in:

- Claude Code: `CLAUDE_CONFIG_DIR=<run>/home/claude`
- Codex: `CODEX_HOME=<run>/home/codex`
- Grok: isolated `HOME` (or the CLI's config-dir override if one exists) with only auth copied in

Auth credentials are copied into each home; nothing else from the user's config is.

| | bare | bruhs |
|---|---|---|
| Skill installed | none | bruhs only, at the version under test (pinned commit of this repo) |
| Project instructions | the repo's CLAUDE.md / AGENTS.md as they were at the base commit, **with any bruhs-managed blocks stripped** | same file, with the bruhs `state`/`rules` blocks as `/bruhs:claim` would write them |
| Prompt | identical natural-language task | identical |
| Model, effort, tools, sandbox | identical | identical |

Why natural-language prompts and not `/bruhs:cook`: the session history shows bruhs almost always kicks in implicitly (from the AGENTS.md block or the installed skill), not from typed commands. The fair question is "same request, does having bruhs installed make the outcome better?"

Skill install per CLI (all three load skills natively; verified on this machine): Claude Code via the plugin in `CLAUDE_CONFIG_DIR`, Codex via `<home>/.agents/skills/bruhs` (the user's current Codex install path), Grok via `<home>/.grok/skills/bruhs`. Same pinned bruhs commit in all three, so each model's bruhs arm measures the same thing.

**Browser tooling (decided: bruhs ships with its companions).** The bruhs arm is "bruhs as a user would actually install it": bruhs + the `/expect` skill + chrome-devtools MCP, which `practices/ui-preview.md` requires for UI verification. Both arms get the same baseline browser tooling (Playwright installed in each fixture) so bare isn't handicapped on raw capability; the difference measured is bruhs's workflow and the tools it wires in. The report states this plainly.

Both arms get the same unattended preamble: the agent is running without a human, should make reasonable calls instead of asking, and must stop when it believes the task is done. External MCPs (Linear etc.) are not configured in either arm.

Reasoning effort: `high` for all three models (each CLI's closest equivalent). Recorded in results.

## Task suite

About 16 tasks. Each task is a folder: base repo snapshot (git commit), prompt, setup script (install deps, seed data, start services if needed), and graders. Two sources:

### A. Real tasks from history (~10)

Picked from the session-history mining (candidate list below). Each has a recoverable base commit, and many have the user's *follow-up complaints* on record, which become a hidden checklist of "things a good agent would have gotten right the first time".

Starting candidates (builder finalizes; drop any that can't be made to run offline):

| Task | Repo @ base | Category | Hidden checklist source |
|---|---|---|---|
| Restyle /grade so it doesn't look AI-generated, cut jargon | mints @ `55ddb370` | UI + copy | user's later edits |
| Make all skeletons match loaded layout | mints @ `ee21906a` | UI polish + verify | "did you verify with agent-browser" |
| Fix /riftbound/products/zh error, add Korean | mints @ `5a17d9c0` | debug + feature | later test fix `a5d11935` |
| Complete refactor audit | mints @ `c5bf3011` | audit | items user had to push for |
| Toolbar UI/UX consistency audit | mints @ `767dcfea` | audit + UI | "same height?", "sort is useless" |
| Improve profile page UI/UX | mints @ `9e11008e` | UI polish | "extra space at bottom" |
| Binder pages from north-star reference | mints @ `f7ef57f1` | feature + copy | 5 follow-up corrections |
| Fix all obvious bad UI/UX site-wide | ogling @ `f669787` | UI audit + fix | breadcrumb bar, dark toggle |
| Full best-practices audit (Rust/Tauri) | bruhs-ai @ `e23bf0f` | audit | later remediation commits |
| Music lab workbench UI + copy cut | degrees-of-freedom @ (by date) | UI + copy | explicit style rules in prompt |

The prompt used is the user's original first message, lightly cleaned (typos kept; only private context that can't be reproduced is removed). Follow-up messages are *not* given — they're what the agent should have anticipated.

### B. Seeded tasks (~6)

Small fixture repos built for objective scoring, covering what history doesn't:

- **Planted-bug audit** (TS + Rust): ~15 planted issues of known severity plus decoys that look wrong but aren't. Scores recall, precision, and severity accuracy. This is the cleanest "slop" measurement.
- **Feature with hidden tests**: a spec'd feature in a small Next.js app; hidden test suite + existing tests (catches regressions).
- **PR review response**: a branch plus a fixture of review comments (some valid, one hallucinated/wrong). Scores: valid ones fixed, wrong one pushed back on, checks still green. (peep has little real history, so this is synthetic.)
- **"Is it actually fixed?" debug**: a bug whose obvious fix passes a unit test but still breaks in the browser. Scores whether the agent verified for real and whether its final claim is true.
- **Ship it**: messy staged diff; score commit message quality, scope of commit, branch name, PR body draft accuracy (all local, no push).
- **Copy pass**: a page full of jargon and filler; blind-judged plus objective word-count / banned-pattern checks.

## Scoring

Every run gets scored on the same dimensions where they apply:

**Objective (automated)**
- Build, typecheck, lint pass
- Hidden tests pass; existing tests still pass (regressions)
- Hidden checklist hit rate (each item checked by script where possible, otherwise by judge)
- Audits: recall / precision vs planted or known issues
- **Honest-done rate**: did the agent's final "done/fixed/verified" claims hold up when the graders checked? (Directly targets the #1 complaint in history.)
- **Scope creep**: files/lines changed outside what the task needed
- Cost: tokens, $ estimate, wall time, turns

**Blind judged (UI and copy)**
- Screenshots of affected pages (desktop + mobile, light + dark) captured by a headless browser after each run.
- Pairwise A vs B comparisons with arm labels removed and order randomized. Judges are the *other two* model families (no model grades its own runs). Report judge agreement.
- Rubric: looks intentional vs AI-generated, spacing/alignment details, copy clarity/brevity, matches the request.
- **Human spot-check**: the user blind-picks on ~20 random pairs. Judges are only trusted if they agree with the user most of the time; the report states the agreement rate.

**Win rule (my call, frozen before the pilot's full run):** each task category has one primary metric; a task is a bruhs win/loss if the mean primary metric over repeats differs by more than a set margin, otherwise a tie.

| Category | Primary metric | Tie margin |
|---|---|---|
| Feature / debug | hidden tests pass + no regressions + honest-done (all three = 1, else 0) | 1 of 3 repeats |
| Audit | F1 vs known issues | 0.05 |
| UI / copy | blind pairwise preference (judges, validated by user) | 55/45 |
| PR review | valid comments fixed, wrong one pushed back, checks green | 1 of 3 repeats |
| Ship | checklist score | 10% |

Cost, time, and scope creep do not decide wins; they're reported beside the win-rate so the trade-off is visible.

**Headline number per model**: bruhs win-rate vs bare across tasks (with ties), plus the per-dimension deltas. Confidence intervals from repeated runs. The headline covers all tasks; a second number for the seeded (publicly reproducible) subset is shown next to it.

**Hidden checklists (my call):** written from the mined session history (follow-up complaints and later fix commits) *before* any run, never adjusted after seeing agent output. The user reviews them once before the full run. Mining output lives in `/tmp/bench_out/` today and gets copied into `bench/` (private-repo details kept out of anything published).

**Judge validation (my call):** judges must agree with the user's blind picks on at least 75% of the ~20 sampled pairs. If they don't, UI/copy results are reported from user picks only, on a reduced sample, and labeled as such. The rubric is not revised.

**Held-out set (my call):** 4 tasks (2 real, 2 seeded) are sealed and not run until bruhs is next changed in response to results. Pilot tasks count as seen.

## Runs

- 3 repeats per (task × model × arm). ~16 × 3 × 2 × 3 ≈ 290 agent runs, plus judging.
- No budget ceiling (user decision). Full 3 repeats; no cuts.
- **Pilot first**: 3 tasks × 3 models × 2 arms × 1 repeat, to shake out the harness before the full run (not for budget).
- Runs execute in parallel in isolated worktrees/temp dirs; per-run timeout (e.g. 45 min).
- Everything a run produces is kept: transcript, final diff, screenshots, grader output.

## Output

- `bench/results/<date>/` — raw per-run data (JSON) and a generated report.
- A self-contained HTML report: headline chart per model, per-category breakdown, cost table, and a handful of side-by-side before/after examples.
- A short README section in this repo with the headline chart and a link to the method.
- Published artifacts from private repos: scores and synthetic-task examples only by default; screenshots from private repos only if the user OKs each one.

## Where it lives

`bench/` in this repo (bruhs-skills), alongside the existing `evals/`. Python for the runner and graders, matching `scripts/`. Task fixtures for private repos reference local paths + commits rather than copying the source into this public repo.

## Left to the builder

- Exact runner architecture, file formats, and parallelism.
- Which screenshot tool (Playwright is the default).
- Final task list within the shape above, dropping any real task that can't run offline/reproducibly.
- Planted-bug fixture contents.
- Per-CLI flags for headless, permissions, and isolated config.
