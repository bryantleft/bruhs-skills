---
type: llm
focus: trace
weight: 1
---

PASS if the arrows between file boxes match the real relative imports, for example index -> store, index -> cart, store -> cart, store -> persist, store -> session, cart -> money, persist -> errors, hooks -> selectors, selectors -> cart, and the arrows are bound to the file shapes. A few omissions are fine; invented edges are not.

FAIL if internal arrows are missing wholesale, point at the wrong files, or are not bound to shapes.
