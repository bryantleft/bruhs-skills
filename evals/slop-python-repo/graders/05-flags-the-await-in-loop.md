---
type: llm
focus: trace
weight: 1
---

PASS if the report flags `for sku in skus: resp = await client.get(...)` in availability() as an await inside a loop over independent items (P3 performance), and recommends running the lookups concurrently (for example asyncio.gather or a TaskGroup), ideally bounded with a semaphore whose size needs a receipt rather than a made-up number.

FAIL if it is missing, or the fix proposes an unbounded gather over user input with no mention of a bound, or a specific magic concurrency number presented as correct.
