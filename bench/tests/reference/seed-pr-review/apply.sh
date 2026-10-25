#!/usr/bin/env bash
# Reference solution: fix review comments 1-4, decline 5 with the reason, reply in
# REVIEW.md under each comment, commit on the branch. Runs in the workspace;
# $REFERENCE_DIR is this dir.
set -euo pipefail
cp -R "$REFERENCE_DIR/files/." .
python3 - "$REFERENCE_DIR/replies.json" <<'PY'
import json, sys
from pathlib import Path

replies = json.loads(Path(sys.argv[1]).read_text())
review = Path("REVIEW.md")
parts = review.read_text().split("\n---\n")
# parts[0] is the header; parts[1..5] are comments 1..5
for i, reply in enumerate(replies, start=1):
    parts[i] = parts[i].rstrip("\n") + f"\n\n**Reply:** {reply}\n"
review.write_text("\n---\n".join(parts))
PY
git add src/backoff.ts src/deliver.ts tests/review-fixes.test.ts README.md
git commit --quiet -m "fix(deliver): cap backoff, honour Retry-After, stop retrying 4xx, count attempts right"
