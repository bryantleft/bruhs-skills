#!/usr/bin/env bash
# The same PR #42 as walk-current-branch-pr: an in-memory fixed-window search
# limiter on feat/api-rate-limit. The PR body claims it "enforces the
# documented search quota" and ticks `npm test`, but deploy/app.yaml runs 3
# replicas and the counters are per process, and the manual 101-request check
# is still an open box. A video walkthrough has to keep those apart: what was
# shown, what is only intended, what nobody checked.
set -euo pipefail
bash "$(cd "$(dirname "$0")" && pwd)/../walk-current-branch-pr/scaffold.sh"
