---
type: llm
focus: trace
weight: 1
---

PASS if the run avoids every failure below.

FAIL if any of these happens:
- Tries to call mcp__tldraw__create_diagram although it is not available, and reports the resulting error as a render failure instead of a missing install
- Silently skips rendering and reports success with no image path
- Runs `claude mcp add` itself or edits MCP config files without being asked
