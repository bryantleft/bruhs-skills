---
type: llm
focus: trace
weight: 1
---

PASS if, on the migrate path, the run does not re-run stack detection or the Linear setup to rebuild the config: no linear_get_teams / linear_list_projects calls, no team or project questions, no stack-confirmation question. Reading files to report what was migrated is fine.

FAIL if it re-detects the stack or re-selects Linear team/project and writes those results instead of the legacy JSON.
