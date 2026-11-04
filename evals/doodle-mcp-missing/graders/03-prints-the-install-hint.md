---
type: llm
focus: trace
weight: 1
---

PASS if the run tells the user how to install a renderer with one of the commands from the doodle doc: `claude mcp add --scope user --transport stdio tldraw -- npx -y tldraw-mcp` or the tldraw-render variant (`... -- npx -y tldraw-render`). Mentioning the equivalent config for another agent harness as well is fine.

FAIL if it gives no install command, or invents a different package name.
