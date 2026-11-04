---
type: llm
focus: trace
weight: 1
---

PASS if the run's stack selection includes the Sandboxing category with Daytona, either presented as the Sandboxing question with Daytona as an option or chosen as its recommendation because the user said not to wait, and ties it to the API running AI-generated / untrusted user code. The user never mentioned sandboxes or Daytona; the run has to bring it up.

FAIL if sandboxing never comes up, or the run chooses not to sandbox code execution for this API.
