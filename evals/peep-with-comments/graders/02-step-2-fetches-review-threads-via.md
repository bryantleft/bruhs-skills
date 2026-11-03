---
type: llm
focus: trace
weight: 1
---

PASS if the run shows this behavior: Step 2 fetches review threads via the gh api graphql query on reviewThreads(first: 100) to get isResolved, path, line, comments with author/body

FAIL if it does not, or if the run never reached the step this describes.
