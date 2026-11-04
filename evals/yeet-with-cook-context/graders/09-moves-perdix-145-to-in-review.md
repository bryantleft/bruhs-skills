---
type: llm
focus: mock_calls
weight: 1
---

These are the Linear tool calls the agent made, with inputs and results.

PASS if there is a `linear_edit_issue` call whose `issueId` is PERDIX-145's id, `7d1c2e4a-0000-4000-b000-000000000145` (the UUID, not the identifier), and whose `stateId` is the In Review state, `9ffd07ac-0000-4000-8000-000000000004` (looked up from `linear_get_teams`).

FAIL if there is no such call, it passes `PERDIX-145` as the issueId, or it sets another state.

Tool names above are Claude Code's. On another agent harness the equivalent mechanism counts: the same MCP server and tool under that harness's naming.
