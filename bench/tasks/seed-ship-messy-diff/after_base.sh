#!/usr/bin/env bash
# Trusted, runs after the bench-base commit: leaves the user's work in progress uncommitted.
#   staged:    src/format/csv.ts (new), README.md, and an unrelated reformat of
#              src/util/dates.ts (no semicolons/one-line ifs, against .prettierrc)
#   unstaged:  src/cli.ts (the --format flag, plus a stray console.log("DEBUG ...")
#   untracked: test/csv.test.ts
set -euo pipefail
wip="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)/wip"
git config user.name "Sam Okafor"
git config user.email "sam.okafor@example.com"
cp -R "$wip"/. .
git add src/format/csv.ts README.md src/util/dates.ts
