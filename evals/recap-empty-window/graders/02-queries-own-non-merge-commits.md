---
type: llm
focus: trace
weight: 1
---

PASS if the agent's git log query filters to the current git user (jordan@example.com, via --author or an equivalent filter), excludes merge commits (--no-merges or equivalent), and covers the resolved yesterday range.

FAIL if the query includes all authors, keeps merge commits in what it reports, or uses a different window.
