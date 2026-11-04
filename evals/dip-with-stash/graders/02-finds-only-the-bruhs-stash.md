---
type: llm
focus: trace
weight: 1
---

PASS if the run shows this behavior: it lists stashes filtered for the `bruhs:` prefix (`git stash list | grep "bruhs:"` or equivalent) and identifies stash@{0} "On main: bruhs: stashed before add-dark-mode" as the one from cook, not the user's own "try serif headings" stash.

FAIL if it does not, or if the run never reached the step this describes.
