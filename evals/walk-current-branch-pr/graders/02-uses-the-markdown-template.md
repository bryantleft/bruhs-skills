---
type: llm
focus: trace
weight: 1
---

PASS if the walkthrough printed in chat follows the command's markdown template: a `# Walkthrough — PR #42: <title>` heading, an Author / Base / Size line with the real numbers (+74 / -9 across 8 files, `main` ← `feat/api-rate-limit`), then TL;DR, Where to start, Core changes, Moved code, Mechanical changes, Risk callouts and Test plan sections. Minor wording differences in the headings are fine.

FAIL if several of those sections are missing, the size line is missing or wrong, or the output is a free-form summary instead of the template.
