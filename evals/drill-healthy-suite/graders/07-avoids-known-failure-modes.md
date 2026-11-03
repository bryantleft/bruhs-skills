---
type: llm
focus: trace
weight: 1
---

PASS if the run avoids every failure below.

FAIL if any of these happens:
- Forces 5+ candidates despite the suite being healthy — pads the list with hypothetical bug classes
- Recommends raising coverage from 85% → 95% without a concrete failure case
- Treats a healthy ratchet-only mutation gate as 'advisory only' and proposes a hard gate when the team already chose the posture deliberately
- Proposes a second acceptance-spec harness because the docker-compose one is 'unusual'
- Misses the absence of a complexity composite (if it is in fact absent) because every other layer looks shiny
