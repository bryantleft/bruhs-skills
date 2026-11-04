---
type: llm
focus: trace
weight: 1
---

PASS if the report flags the useEffect in src/components/UserCard.tsx that copies firstName/lastName into displayName/initials state as a derived-state anti-pattern, and recommends computing both values during render.

FAIL if this effect is not reported.
