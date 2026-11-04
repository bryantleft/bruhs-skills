---
type: llm
focus: trace
weight: 1
---

PASS if the code limits the range to the 7-day policy in src/lib/rental-range.ts (MAX_RENTAL_DAYS, pick-up and return day both counted) using the installed version's semantics: `max` counts nights (differenceInCalendarDays in addToRange in dist/index.js), so it passes max={6}, or MAX_RENTAL_DAYS - 1 with the reason stated.

FAIL if it passes max={7} or max={MAX_RENTAL_DAYS}, which allows 8 calendar days, or leaves the picker unlimited and relies on nothing but the server check.
