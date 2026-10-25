#!/usr/bin/env bash
# Reference solution: ship the CSV feature only. Runs in the workspace after after_base.sh;
# $REFERENCE_DIR is this dir.
set -euo pipefail
git switch --quiet -c feat/report-csv-format
# the stray debug line stays out of history
grep -v 'console.log("DEBUG report opts"' src/cli.ts > src/cli.ts.tmp
mv src/cli.ts.tmp src/cli.ts
# the dates.ts reformat is unrelated (and against .prettierrc): leave it uncommitted
git restore --staged src/util/dates.ts
git add src/format/csv.ts src/cli.ts README.md test/csv.test.ts
git commit --quiet -m "feat(report): add --format csv to tally report" \
  -m "Prints RFC 4180 CSV (header row, one row per group, no total row) so reports can go
straight into a spreadsheet. The table stays the default."
cp "$REFERENCE_DIR/PR.md" PR.md
