---
type: llm
focus: mock_calls
weight: 1
---

These are the Linear tool calls the agent made, with inputs and results.

PASS if the agent fetched PERDIX-145 (`linear_get_issue` with identifier `PERDIX-145`) and never called `linear_create_issue`.

FAIL if it created a ticket, or never fetched PERDIX-145.
