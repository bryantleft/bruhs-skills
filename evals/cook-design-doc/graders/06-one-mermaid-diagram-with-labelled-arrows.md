---
type: llm
focus: trace
weight: 1
---

PASS if the doc contains one mermaid diagram with a title stating its type and scope, named boxes (for example dashboard, billing, the read path, the primary and whatever new store or replica the design adds), every arrow labelled with its intent (such as "reads balance", "writes charge"), and the new or changed parts highlighted or shown as before/after.

FAIL if there is no mermaid diagram, an arrow is unlabelled or labelled "uses", the change is not distinguishable, or the doc needs several diagrams to say what one could. FAIL if no doc is written.
