---
type: llm
focus: trace
weight: 1
---

PASS if the run shows this behavior: the reply it drafts for the polling question on lib/hooks/use-leaderboard.ts:12 uses Conventional Comments format (`<label> [decoration]: <subject>`, e.g. `note: ...`) and answers from the code it read: the interval is POLL_MS from lib/game/constants.ts, shared with useGameState.

FAIL if the drafted reply is bare prose, if it never drafts one, or if the run never reached the step this describes.
