---
type: llm
focus: trace
weight: 1
---

PASS if the DayPicker usage it writes matches the installed dist/index.d.ts: mode="range", `selected` typed as DateRange, an `onSelect` handler taking (range: DateRange | undefined, ...), navigation limits (if any) through startMonth/endMonth, and the stylesheet (if imported) as "react-day-picker/style.css", the only path package.json exports.

FAIL if it uses names the installed version doesn't have, such as fromMonth/toMonth/fromDate/toDate, IconLeft/IconRight components, day_selected/day_range_start style classNames, or "react-day-picker/dist/style.css".
