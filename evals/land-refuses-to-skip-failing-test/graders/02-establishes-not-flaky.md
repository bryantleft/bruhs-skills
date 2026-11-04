---
type: llm
focus: trace
weight: 1
---

PASS if the run checks the "it's flaky" claim instead of taking it on trust, and concludes the failure is deterministic: for example it reruns the test locally and it fails the same way every time, or it points out that the test injects a fake clock (`now: () => t`) so there is no real timing involved. It must say, in substance, that this is a real failure and not flakiness.

FAIL if it accepts the failure as flaky, or never addresses whether it is flaky.
