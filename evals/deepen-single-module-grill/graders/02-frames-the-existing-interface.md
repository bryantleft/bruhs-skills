---
type: llm
focus: trace
weight: 1
---

PASS if, before proposing alternatives, the run restates the problem concretely: the 11-argument createReservation (including the smoking / vip / depositRequired booleans and the stripePaymentIntentId parameter), updateReservation taking arbitrary partial fields, the validation copied into three callers that disagree (for example party size capped at 20 only in admin, "today" allowed only in admin), and what the module should hide, with illustrative caller code.

FAIL if it jumps to designs without describing the current interface and its problems, or describes them only in the abstract.
