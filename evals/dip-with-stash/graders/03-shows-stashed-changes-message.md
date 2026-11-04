---
type: llm
focus: trace
weight: 1
---

PASS if the run shows this behavior: it tells the user they have stashed changes from before their last feature, showing the entry (e.g. "💡 You have stashed changes from before your last feature:" followed by `stash@{0}: On main: bruhs: stashed before add-dark-mode`).

FAIL if it does not, or if the run never reached the step this describes.
