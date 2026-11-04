---
type: llm
focus: trace
weight: 1
---

PASS if the hand-off includes: an adoption plan /bruhs:cook can follow (what to install, configure and wire into CI, in order); an exact gate spec (threshold, CI step or schedule, failure message); a tests-to-delete list (for example the assertion-free or weak tests the pilot exposes, or an advisory check the gate makes redundant, or an explicit "none, because ..."); and a rollback plan if the gate is noisy.

FAIL if any of the four is missing.
