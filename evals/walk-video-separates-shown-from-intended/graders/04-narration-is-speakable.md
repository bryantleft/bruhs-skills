---
type: llm
focus: { source: file, path: .git/bruhs/walk/pr-42/script.json }
weight: 1
---

This file is the video walkthrough script the agent wrote for PR #42. Each scene's "narration" is read aloud by a text-to-speech voice and shown as captions.

PASS if the narration reads as spoken English: no backticks, no raw file paths like src/middleware/rateLimit.ts, and no code syntax such as `()` or `=>`. Numbers or status codes may be written as digits or words. Paths and code belong in the visuals, and appearing there is fine.

FAIL if any scene's narration contains backticks, a file path, or code syntax.
