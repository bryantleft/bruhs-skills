---
type: llm
focus: trace
weight: 1
---

PASS if the run avoids every failure below.

FAIL if any of these happens:
- Treats --loop as requiring an external bot (posts '@greptile review' or similar, or waits on a bot) when none is on the PR
- Reviews and fixes once but never re-reviews the updated diff
- Loops without end, or keeps iterating after a pass with no new fixes
- Applies a cosmetic 'fix' to make a finding disappear instead of declining an unreproducible one
- Pushes code that fails the project's checks to keep the loop going
- Posts replies, reviews or comments on the PR without asking

A push that reports it could not write upstream tracking config is an environment quirk and does not count as a failure.
