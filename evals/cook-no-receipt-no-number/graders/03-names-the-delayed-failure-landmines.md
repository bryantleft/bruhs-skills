---
type: llm
focus: trace
weight: 1
---

PASS if the plan names the delayed failures this change could create: retry amplification that overloads profile-service when it is already struggling, stale profile data served from the cache, and degraded or cached results that look identical to fresh successes. Naming retry amplification and upstream overload together as one landmine is fine.

FAIL if any of the three is missing, or the plan lists generic code smells instead of the delayed failure each causes.
