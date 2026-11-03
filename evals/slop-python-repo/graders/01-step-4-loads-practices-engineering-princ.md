---
type: llm
focus: trace
weight: 1
---

PASS if the run shows this behavior: Step 4 loads practices/engineering-principles.md as GOVERNING, then detects language=python and framework=fastapi, loads practices/python.md as the base, stacks practices/python-fastapi.md on top, and still loads practices/type-driven-design.md as PRIMARY plus practices/_common.md

FAIL if it does not, or if the run never reached the step this describes.
