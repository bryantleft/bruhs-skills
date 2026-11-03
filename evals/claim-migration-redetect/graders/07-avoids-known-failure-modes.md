---
type: llm
focus: trace
weight: 1
---

PASS if the run avoids every failure below.

FAIL if any of these happens:
- Carries the stale framework='Astro' forward into the new bruhs:state block instead of re-detecting from code
- Skips the second 'delete legacy?' prompt because it isn't a migrate path — but the legacy file is still on disk and will keep being read by old tooling, so the user must still be asked
- Falls through into the Migrate path despite the user picking 'Re-detect from scratch'
- Refuses to re-detect on the grounds that 'a config already exists'
