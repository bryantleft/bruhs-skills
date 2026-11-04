---
type: llm
focus: last_message
weight: 1
---

PASS if the final message stops the ship and tells the user there is nothing to ship, in substance the command doc's "No changes to ship. Make some changes first!" (the exact wording is not required).

FAIL if the final message reports a commit, push, ticket or PR, or doesn't say that there were no changes.
