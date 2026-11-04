---
type: llm
focus: trace
weight: 1
---

PASS if the scaffold command the run chooses for the Python FastAPI API is the command doc's `uv init code-runner && cd code-runner && uv add fastapi` (equivalent uv steps count).

FAIL if it scaffolds with pip, poetry, cookiecutter or a JS tool, or never attempts the uv scaffold.
