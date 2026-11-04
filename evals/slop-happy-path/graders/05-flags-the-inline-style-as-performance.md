---
type: llm
focus: trace
weight: 1
---

PASS if the report flags the inline `style={{ objectFit: ..., width: ..., aspectRatio: ... }}` passed to FadeImage in src/components/HeroImage.tsx as a performance anti-pattern (a new object every render defeats the memo() on FadeImage) and ranks it as a performance issue (P3 / High or Medium), recommending hoisting the static object out of render.

FAIL if it is not reported, or is reported only as a style or readability nit (P7 / Low).
