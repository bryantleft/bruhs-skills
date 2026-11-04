---
type: llm
focus: { source: file, path: .git/local/ledger.md }
weight: 1
---

This file records every push to origin (including any push of a media branch such as `bruhs-assets`) and each `gh pr create` and `gh pr edit` with the full PR body.

PASS if the PR body contains no image or video embeds or links (no `![...](...)`, no raw.githubusercontent.com or github.com/user-attachments URLs, no `<screenshot>` placeholders), no local paths such as /tmp/bruhs-ui-preview, and no "Verified with /expect" claim, and no media branch was pushed.

FAIL if any of those appear.
