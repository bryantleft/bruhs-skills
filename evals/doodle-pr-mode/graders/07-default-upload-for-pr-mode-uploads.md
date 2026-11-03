---
type: llm
focus: trace
weight: 1
---

PASS if the run shows this behavior: Default upload for pr mode: uploads image to a gist via `gh gist create` and posts a PR comment on #42 via `gh pr comment 42 --body` containing the image and a legend in <details>

FAIL if it does not, or if the run never reached the step this describes.
