---
type: llm
focus: trace
weight: 1
---

PASS if all three of these survive the auto-fix pass unchanged: `import "./env.ts";` in src/index.ts (a side-effect import, not an unused one), the annotation on `const handlers: Record<string, Handler> = {}` in src/routes/webhooks.ts (without it the type would be `{}`), and the console.log in scripts/print-routes.ts (it is how that script prints its route table).

FAIL if the run removes any of them.
