---
type: llm
focus: trace
weight: 1
---

PASS if the run recognizes the legacy .claude/bruhs.json with no bruhs:state block (the Case B migration path) and, as the user asked, takes "Re-detect from scratch": it ignores the legacy file's values and runs fresh detection.

FAIL if it migrates the legacy JSON, treats the project as already configured with a marker block, or refuses to re-detect because a config exists.
