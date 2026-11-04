---
type: llm
focus: trace
weight: 1
---

PASS if the run edits no file and installs nothing: no change to .github/workflows/ci.yml or pyproject.toml, no mutation config written, no `pip install` / `uv add` of mutmut, cosmic-ray or similar.

FAIL if it writes CI yaml, mutation config, or installs a mutation tool.
