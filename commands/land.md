---
description: Watch PR checks and iterate on CI failures until green — uses `gh pr checks` as source of truth, diagnoses first actionable failure, applies minimal fix, repeats. Use after `yeet` when CI needs babysitting, or any time a PR is red and you want it green.
---

# land - Get the PR to Green

`yeet` opens the PR. `land` gets it to green. Watches `gh pr checks`, surfaces the first actionable failure, applies the smallest safe fix, and re-checks until the full check set is passing.

## Contents

- [Invocation](#invocation)
- [Why `gh pr checks`](#why-gh-pr-checks)
- [Workflow](#workflow)
- [Failure Triage](#failure-triage)
- [Guardrails](#guardrails)
- [Examples](#examples)
- [Tips](#tips)

---

## Invocation

- `/bruhs:land` — Watch CI for the current branch's PR and fix until green
- `/bruhs:land <PR#>` — Same, against a specific PR (switches branch if needed)
- `/bruhs:land --no-fix` — Watch only, surface failures, do not auto-edit
- `/bruhs:land --max-iterations 3` — Cap the fix loop (default: 5)

## Why `gh pr checks`

GitHub PRs accumulate checks from many sources — GitHub Actions, Vercel, third-party CI, status APIs. `gh run list` only sees GitHub Actions. **`gh pr checks` is the only source of truth that covers every required check the PR is blocked on.**

```bash
# Always use this — full PR check set
gh pr checks --json name,bucket,state,workflow,link

# Use this ONLY for diving into a GHA-specific failure
gh run view <run-id> --log-failed
```

## Workflow

### Step 0: Resolve the PR

```bash
# Default: PR for current branch
pr=$(gh pr view --json number,url,headRefName,state,mergeable,mergeStateStatus 2>/dev/null)

# Or argument
gh pr view <PR#> --json number,url,headRefName,state,mergeable,mergeStateStatus
```

If no PR exists for the branch:

```javascript
AskUserQuestion({
  questions: [{
    question: "No PR found for this branch. What do you want to do?",
    header: "PR",
    multiSelect: false,
    options: [
      { label: "Run /bruhs:yeet first (Recommended)", description: "Ship the branch, then come back to /bruhs:land" },
      { label: "Specify a PR number", description: "Provide a PR# and I'll check out the branch" },
      { label: "Abort", description: "Nothing to do" },
    ]
  }]
})
```

If the user picked a PR# different from the current branch, check out that branch first:

```bash
gh pr checkout <PR#>
```

### Step 1: Inspect Current Check State

```bash
gh pr checks --json name,bucket,state,workflow,link
```

`bucket` values are normalized: `pass`, `fail`, `pending`, `cancel`, `skipping`. Read this **before** waiting — checks may already be failed or already green.

| State | Action |
|---|---|
| All `pass` | Done. Output success summary, exit. |
| Any `fail` / `cancel` | Go to [Failure Triage](#failure-triage) immediately. Do not wait. |
| Mix of `pending` + no failures | Watch with `--watch --fail-fast` (Step 2). |
| All `pending` | Watch with `--watch --fail-fast` (Step 2). |

### Step 2: Watch Pending Checks

```bash
gh pr checks --watch --fail-fast
```

`--fail-fast` exits the moment any check goes red so we can diagnose immediately instead of waiting for the full suite. If everything goes green, the command exits 0 and we're done.

### Step 3: Diagnose the First Actionable Failure

After a red state, re-read the full check set (it may have grown):

```bash
gh pr checks --json name,bucket,state,workflow,link --jq '.[] | select(.bucket == "fail" or .bucket == "cancel")'
```

Pick the first failure and pull logs:

- **GitHub Actions check** — has `workflow` set and `link` points to a GHA run:
  ```bash
  # Extract run id from the link, then:
  gh run view <run-id> --log-failed
  ```
- **Non-GHA check** (Vercel, Codecov, third-party) — follow `link` (use `WebFetch` or surface the URL to the user; do not fabricate fixes from a check name alone).

Extract the **first actionable error** — the topmost stack trace, build failure, or assertion. Do not try to fix everything at once.

### Step 4: Apply the Smallest Safe Fix

The fix should be:
- scoped to a single failure cause
- behavior-preserving where possible
- not a `// @ts-ignore` / `eslint-disable` / `--no-verify` band-aid
- not a sweeping refactor while CI is red

Common failure → fix patterns are in [Failure Triage](#failure-triage). If the failure looks unrelated to this PR (e.g. flake, infra outage, broken main), see [Escape Hatches](#guardrails) instead of bloating the PR.

### Step 5: Commit and Push

```bash
git add <files>
git commit -m "fix: <one-line description of CI fix>"
git push
```

Do not use `--no-verify`. If a pre-commit hook fails, fix it — that's a real signal.

### Step 6: Re-Check and Repeat

After the push, the check set can change (workflows may add/remove checks based on path filters):

```bash
gh pr checks --json name,bucket,state,workflow,link
```

Loop Step 1 → Step 5 until all checks pass or `--max-iterations` is reached. After each iteration print a one-line progress update:

```
iteration 2/5 — typecheck ✓, lint ✓, test (1 failure: components/Toast.test.tsx)
```

### Step 7: Output Summary

```
PR #46 — sonner/main ← son-m7-api-sdk
3 iterations, 2 fixes pushed

Fixes applied:
  • iter 1 — Toast.test.tsx assertion was checking removed prop (af1d2c3)
  • iter 2 — biome flagged unused import in api/route.ts (b94e5d1)

✓ All checks passing — PR ready for review/merge
https://github.com/sonner-labs/sonner/pull/46
```

If hit `--max-iterations`:

```
PR #46 — hit 5/5 iteration cap, 3 still red

Remaining failures:
  • build (vercel) — link: https://vercel.com/...
  • test (e2e)    — flake-suspect, 2/3 retries passed locally

Stopping. Recommended next step:
  /bruhs:land --no-fix  # to surface the failures without editing
  /bruhs:slop apps/web  # if the same code keeps re-breaking
```

## Failure Triage

Common CI failure shapes → first-line fix:

| Failure | Fix |
|---|---|
| `tsc` error in file you touched | Open that line, fix the type. Do not `as any`. |
| `tsc` error in a file you didn't touch (cascading change) | Trace the breaking export; either fix at source or revert the API change scope. |
| Lint error (biome/eslint) | Run the project's `lint:fix` if available, then re-check the diff for behavior changes. |
| Test failure — assertion changed | Decide: is the new behavior correct? Update the test. Is it a regression? Fix the code. |
| Test failure — flake | Re-run once. If still red, it's not flake — diagnose. |
| Build failure — missing env var in CI | Add it to the workflow's `env`, not to source. |
| Vercel preview build red | Check the Vercel link. Common: missing dep, missing env var, Edge runtime incompatibility. |
| Codecov / coverage drop | If the drop is real (uncovered new code), add a focused test; don't disable coverage. |
| Required check "expected — Waiting" forever | Workflow file may not be on the branch yet, or the check name in branch protection doesn't match. Surface to user; don't try to fix. |
| Merge conflict / `mergeStateStatus: DIRTY` | `git fetch origin && git merge origin/main` (or rebase per repo convention), resolve, push. See [Guardrails](#guardrails). |

## Guardrails

- **Never bypass hooks** (`--no-verify`, `--no-gpg-sign`) to force progress.
- **Never silence a real failure** with `@ts-ignore`, `eslint-disable-next-line`, or `xit`/`it.skip` to get green. If a test must be skipped, surface it to the user with a reason and a Linear ticket.
- **One failure cause per iteration.** If you fix 3 unrelated things in one push and one of them breaks the build worse, you can't tell which.
- **Re-fetch checks after every push.** The set changes — new workflows trigger, old ones drop.

### Escape Hatches

- **Failure is clearly unrelated to this PR and main is green**: pull latest main into the branch rather than carrying an unrelated fix.
  ```bash
  git fetch origin main && git merge origin/main
  # resolve conflicts if any, push
  ```
- **Failure is on main too (broken main)**: stop. Surface to user — landing this PR won't help. Suggest filing a Linear ticket against main.
- **Persistent flake (≥ 2 reruns to pass)**: surface flake evidence (timestamps, log excerpts), don't keep retrying. The reviewer needs to see this.

## Examples

### Typical case — TS + lint clean up

```
> /bruhs:land

Resolving PR…
  PR #46 — son-m7-api-sdk

Inspecting checks…
  typecheck   fail
  lint        pass
  test        pass
  vercel      pending

iteration 1/5
  First actionable failure: typecheck
  apps/web/src/lib/people/sources/github.ts:42
    error TS2322: Type 'string | undefined' is not assignable to type 'string'.
  Fix: add explicit null-check on `repo.description` before assignment.

  Committing… ✓ fix: handle undefined description from github source
  Pushing… ✓

Inspecting checks…
  typecheck   pending
  lint        pending
  test        pass
  vercel      pending

Watching with --fail-fast…
  ✓ All checks passing

PR #46 — 1 iteration, 1 fix pushed
✓ Ready for review
https://github.com/sonner-labs/sonner/pull/46
```

### Escape hatch — unrelated flake

```
> /bruhs:land

iteration 2/5
  First actionable failure: e2e
  e2e/people-search.spec.ts › "filters by location"
    Error: locator.click: Test timeout of 30000ms exceeded.

  Checking main… origin/main e2e is passing. Local rerun: 3/3 passing.

  Diagnosis: flake-suspect, unrelated to this PR.

  Recommended: skip this iteration, re-trigger CI once more.
```

```javascript
AskUserQuestion({
  questions: [{
    question: "e2e looks like flake. What do you want to do?",
    header: "Flake",
    multiSelect: false,
    options: [
      { label: "Re-trigger CI once (Recommended)", description: "Push an empty commit to retry; if it stays red, it's real" },
      { label: "Skip and continue waiting", description: "Don't push; just wait — GitHub may rerun on its own" },
      { label: "Stop and surface", description: "Hand back to me with the evidence" },
    ]
  }]
})
```

## Tips

- **Run `/bruhs:land` right after `/bruhs:yeet`** for the full ship-to-green loop.
- **Run with `--no-fix` first** if you want to see the failures before letting it edit anything.
- **Pair with `/bruhs:verify`** when the CI failure looks like a behavior bug — verify in isolation, fix, then `land` to confirm CI agrees.
- **If you hit `--max-iterations`** that's a signal the PR has multiple unrelated issues; consider splitting it.
