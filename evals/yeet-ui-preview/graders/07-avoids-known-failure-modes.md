---
type: llm
focus: trace
weight: 1
---

PASS if the run avoids every failure below.

FAIL if any of these happens:
- Skips Step 7.5 entirely and opens the UI PR with no preview or a bare `<screenshot>` placeholder
- Embeds screenshots without running /expect first — a preview of an unverified UI
- Captures only a static screenshot and no screen recording of the interaction
- Claims the recording renders inline as a video player from a gh/CLI upload (it does not — only web-composer user-attachments inline-play); hallucinating a working hosting path
- References a local /tmp path in the PR body (renders as nothing for reviewers) instead of a hosted URL
- Writes a non-Conventional commit message or PR title
