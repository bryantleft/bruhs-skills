---
type: llm
focus: trace
weight: 1
---

PASS if the run avoids every failure below.

FAIL if any of these happens:
- Reports only type or style issues and misses the decision-quality failures
- Accepts the log message as sufficient error handling
- Replaces the values with fashionable defaults
- Treats the "always returns a userId" comment as an adequate guardrail
- Edits src/profile-client.ts even though the user asked for --report
