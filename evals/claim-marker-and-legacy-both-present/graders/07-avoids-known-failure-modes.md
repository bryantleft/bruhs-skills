---
type: llm
focus: trace
weight: 1
---

PASS if the run avoids every failure below.

FAIL if any of these happens:
- Fires the Case B migration prompt despite the marker block being present — confuses the user about which is the source of truth
- Silently deletes the legacy .claude/bruhs.json after Reconfigure-Yes without prompting the user (irreversible)
- Reads the legacy file in addition to the marker block and merges them — pollutes the new state with stale fields
- Reports 'No legacy file detected' when the file is in fact present — silently misleading
- Exits on Reconfigure-No without mentioning the dormant legacy file — user is unaware it exists and will be surprised later
