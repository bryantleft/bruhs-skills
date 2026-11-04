---
type: llm
focus: trace
weight: 1
---

PASS if the run shows this behavior: it reports that `POST /admin/refunds/bulk` never calls `authorize(user, 'refund:write')`, so a user without that permission can approve refunds, as a blocking issue (must-fix / `issue (blocking)`), with evidence such as a test or call that gets 200 for a user with no permissions.

FAIL if the finding is missing, demoted to non-blocking, or dropped because POST /admin/exports has the same gap, or if the run never reached the review.
