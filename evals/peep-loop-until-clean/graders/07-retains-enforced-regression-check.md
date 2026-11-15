---
type: llm
focus: trace
weight: 1
---

PASS if the final pushed fix includes a retained executable regression check for
the demonstrated attempt-count bug: with three allowed attempts, an operation
that fails twice and then succeeds must succeed on the third call. The check must
be tracked in the repository, discovered by the normal `npm test` command, and
shown rejecting the original implementation and accepting the corrected one.
Extending an existing test is sufficient. Judge the executed commands, file edits,
and committed diff, rather than assurances in the final response.

FAIL if the agent fixes the retry loop but deletes its only reproduction, leaves
the check in a scratch directory outside normal test discovery, excludes it from
the pushed commit, or substitutes a prompt/documentation reminder for an executable
check. A suite covering only first-attempt success does not catch this bug.
