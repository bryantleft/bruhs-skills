---
type: llm
focus: trace
weight: 1
---

PASS if the run shows this behavior: Step 5 deletes the local feature branch with `git branch -d perdix-139-make-model-form-image-upload-fully-rounded` (safe delete since it was merged) and attempts `git push origin --delete` for the remote

FAIL if it does not, or if the run never reached the step this describes.
