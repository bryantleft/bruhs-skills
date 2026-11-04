---
type: llm
focus: trace
weight: 1
---

PASS if the design doc's body stays within about three pages (roughly 1,500 words or fewer outside any appendix), and any implementer-only detail it includes (PR breakdown, field lists, migration steps) sits in a collapsed `<details>` appendix rather than the body.

FAIL if the body runs well past three pages, or implementer-only detail such as file-by-file steps or a PR table fills the main sections. FAIL if no doc is written.
