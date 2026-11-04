---
type: llm
focus: trace
weight: 1
---

PASS if the run treats packages/store as the module root (it is a workspace member with a package.json, @acme/store) and diagrams that module, rather than the whole monorepo or a freeform sketch.

FAIL if it diagrams something other than packages/store, or invents structure without reading the package.
