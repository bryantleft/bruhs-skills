---
type: llm
focus: trace
weight: 1
---

PASS if the run checks the user's MCP configuration for Linear servers (detect_mcp_servers.py, or reading ~/.claude.json and the other agent configs), concludes that none is configured (only notion and context7 are), and says Linear is optional and how to add it (register mcp-server-linear in the agent's MCP config).

FAIL if it never checks, claims a Linear server exists, or treats notion / context7 as Linear.
