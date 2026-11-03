---
type: llm
focus: trace
weight: 1
---

PASS if the run shows this behavior: When docs/memory and the source disagree, the agent treats the installed source as ground truth and pins to the lockfile version, not `latest`

FAIL if it does not, or if the run never reached the step this describes.
