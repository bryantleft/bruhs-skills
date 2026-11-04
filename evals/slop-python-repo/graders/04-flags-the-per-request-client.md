---
type: llm
focus: trace
weight: 1
---

PASS if the report flags `async with httpx.AsyncClient(base_url=WAREHOUSE_URL)` inside availability() in app/routes/inventory.py as per-request client construction, a performance anti-pattern (P3, a bug rather than an optimization) that defeats connection pooling, and recommends one shared client (module scope or owned by the app lifespan).

FAIL if it is missing, or reported only as a style issue.
