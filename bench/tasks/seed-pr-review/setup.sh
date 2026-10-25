#!/usr/bin/env bash
# Trusted, runs before the agent (and before the bench-base commit): install pinned deps,
# then put the repo where the user is: on feat/webhook-retries (two commits on top of
# main) with the review they got back in REVIEW.md. Only named paths are committed, so
# nothing the harness added (e.g. CLAUDE.md) ends up in the branch's own commits; the
# harness's "bench: base" commit lands on this branch.
set -euo pipefail
task="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
npm ci --no-audit --no-fund --loglevel=error
git config user.name "Jordan Reyes"
git config user.email "jordan.reyes@example.com"
export GIT_AUTHOR_DATE="2026-10-21T15:12:00-07:00" GIT_COMMITTER_DATE="2026-10-21T15:12:00-07:00"
git switch --quiet -c feat/webhook-retries
cp "$task/branch/src/backoff.ts" "$task/branch/src/deliver.ts" "$task/branch/src/index.ts" src/
cp "$task/branch/tests/deliver.test.ts" tests/
git add src/backoff.ts src/deliver.ts src/index.ts tests/deliver.test.ts
git commit --quiet -m "feat(deliver): retry failed webhook deliveries with backoff"
export GIT_AUTHOR_DATE="2026-10-21T16:40:00-07:00" GIT_COMMITTER_DATE="2026-10-21T16:40:00-07:00"
cp "$task/branch/README.md" README.md
git add README.md
git commit --quiet -m "docs: document delivery retries"
cp "$task/REVIEW.md" REVIEW.md
