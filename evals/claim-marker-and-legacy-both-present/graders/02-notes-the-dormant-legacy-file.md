---
type: llm
focus: trace
weight: 1
---

PASS if, before or together with the reconfigure question, the run tells the user that a legacy .claude/bruhs.json is also on disk and is dormant / ignored (the marker block is what bruhs reads), so they can clean it up.

FAIL if it never mentions the legacy file, or says no legacy file exists.
