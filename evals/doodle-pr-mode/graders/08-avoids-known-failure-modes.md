---
type: llm
focus: trace
weight: 1
---

PASS if the run avoids every failure below.

FAIL if any of these happens:
- Invokes pr mode on a branch without a PR and still runs the full pipeline instead of aborting or prompting
- Skips the old-vs-new import diff and renders every file as 'modified' with no distinct green/red edges
- Posts the gist URL as a plain text comment without the <details> legend or with no image rendered
