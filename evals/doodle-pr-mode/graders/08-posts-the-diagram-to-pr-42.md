---
type: llm
focus: trace
weight: 1
---

PASS if, with no output flag given and a PR detected, the run uploads the image with `gh gist create` and then runs `gh pr comment 42` with a body that embeds the image (a raw gist URL in markdown image syntax) and a legend (added / modified / deleted) inside a <details> block, then reports the comment URL.

FAIL if it does not post to PR #42, posts only a bare link with no image, or leaves out the <details> legend.
