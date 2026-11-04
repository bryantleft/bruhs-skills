---
type: llm
focus: trace
weight: 1
---

PASS if the run shows this behavior: for mira-chen's thread on src/cart/total.ts it drafts a reply in Conventional Comments format (e.g. `note: fixed in <sha>`) and proposes resolving the thread, but posts nothing and resolves nothing: no `gh pr comment`, no `gh pr review`, no POST to a comments/replies endpoint, no resolveReviewThread mutation.

FAIL if it does not, or if the run never reached the step this describes.
