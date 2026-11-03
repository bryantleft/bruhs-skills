---
type: llm
focus: trace
weight: 1
---

PASS if the run shows this behavior: Prints the install hint from the command doc: `claude mcp add --scope user --transport stdio tldraw -- npx -y tldraw-mcp` (or the tldraw-render alternative)

FAIL if it does not, or if the run never reached the step this describes.
