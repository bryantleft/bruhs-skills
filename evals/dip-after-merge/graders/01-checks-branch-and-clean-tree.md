---
type: llm
focus: trace
weight: 1
---

PASS if the run shows this behavior: it starts by checking the current branch (`git branch --show-current`) and the working tree (`git status`), sees it is on perdix-139-make-model-form-image-upload-fully-rounded with a clean tree, and does not ask about uncommitted changes.

FAIL if it does not, or if the run never reached the step this describes.
