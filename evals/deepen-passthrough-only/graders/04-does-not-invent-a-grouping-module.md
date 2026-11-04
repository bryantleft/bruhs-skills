---
type: llm
focus: trace
weight: 1
---

PASS if the run does not propose grouping the utilities into an invented module such as "DateUtils", "TextUtils", "NumberUtils", "FormattingModule" or a "utils service", even for the three date-fns wrappers (formatDate, formatRelative, parseIsoDate), because they share no invariant.

FAIL if it proposes any such grouping module as a deepening.
