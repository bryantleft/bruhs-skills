---
type: llm
focus: trace
weight: 1
---

PASS if the shapes sent to create_diagram group files into module frames by directory (for example leaderboard, app, db, legacy, lib, components), with one geo box per changed file inside its module frame, and arrows bound to the file shapes.

FAIL if there are no frames, files are not inside module frames, or arrows are not bound to shapes.
