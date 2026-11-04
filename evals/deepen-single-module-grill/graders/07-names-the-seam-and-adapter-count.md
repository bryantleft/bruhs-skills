---
type: llm
focus: trace
weight: 1
---

PASS if the run names deposit collection as a seam and says it is a real one because it has two adapters (Stripe in production, a fake in tests), and treats the existing ReservationRepository interface, which has a single Drizzle adapter, as a hypothetical seam (keep it internal or drop it, not grow it into a port).

FAIL if it never discusses adapter count, or adds or keeps a port for the database with only one adapter as part of the external interface.
