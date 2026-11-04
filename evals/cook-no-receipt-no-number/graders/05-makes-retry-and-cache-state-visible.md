---
type: llm
focus: trace
weight: 1
---

PASS if the design makes retry and cache behavior visible in the interface: the result type or response distinguishes a fresh profile from a cached or stale one, and an exhausted retry policy surfaces as an error that says how many attempts were made and why it stopped.

FAIL if a cached or stale profile is returned as an ordinary success indistinguishable from a fresh one, or retries happen silently inside the client.
