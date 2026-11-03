---
type: llm
focus: trace
weight: 1
---

PASS if the run shows this behavior: Step 1 parses 'add a leaderboard to the game page' as a feature description (not a ticket ID), outputs a Feature/Goal/Scope summary, and does NOT call linear_get_issue

FAIL if it does not, or if the run never reached the step this describes.
