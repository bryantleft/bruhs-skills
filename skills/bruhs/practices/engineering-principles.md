# Engineering Principles

These principles govern every bruhs command and every stack-specific practice. When
another recommendation conflicts with this file, this file wins.

## Fundamental Feedback Loop

> Every agent mistake becomes a lint rule, not a prompt.

**Find the failure → fix it → encode what would catch it → enforce it on future
changes.** Apply this during implementation, review, and CI triage, from the first
confirmed occurrence. Each correction should improve the repository's ability to
reject that failure in a fresh agent session. Corrected behavior and retained
executable prevention are both part of the fix. An unresolved enforcement gap must
remain visible; a passing suite alone does not close it.

## Shared Vocabulary

### Landmine

A choice that looks harmless now but creates a delayed failure. Common landmines:

- a limit copied from an example
- a fallback that converts failure into plausible-looking output
- state that changes somewhere the interface does not reveal
- an abstraction built for hypothetical future variation
- an assumption that is documented but never checked

Name the delayed failure, not merely the code smell:

> Landmine: this unbounded fan-out turns one large request into enough downstream
> calls to exhaust the connection pool.

### Receipt

The evidence or reasoning behind a decision. A useful receipt is inspectable and
close enough to the decision that a maintainer can update it.

Valid receipts include:

- production measurements or a reproducible benchmark
- downstream quotas or protocol requirements
- capacity math tied to a measured resource budget
- user research or accessibility guidance
- an incident, issue, ADR, or compatibility contract
- an explicit user requirement

For operational numbers—timeouts, retry counts, memory budgets, concurrency limits,
queue bounds, cache sizes, pagination limits—no receipt, no number.

Examples and protocol constants are not automatically receipts. If a safety limit is
needed before production data exists, derive it from a stated worst-case resource
budget, instrument it, and record what evidence should replace the estimate.

### Tripwire

An executable guardrail that fails loudly when an assumption stops being true.
Healthy code should not reach it. Broken code should produce an actionable failure
at the closest useful boundary.

Tripwires include:

- schema validation at ingress
- startup validation for required configuration
- exhaustive state handling
- database constraints for domain invariants
- assertions for states proved impossible by an earlier boundary
- CI checks that enforce architectural or generated-code invariants

A comment is not a tripwire. A log followed by success is not a tripwire.

### Simple

Logic that decomposes naturally: one responsibility per component, explicit data
flow, and steps that follow from one another. Simple code removes complexity; it
does not move complexity behind indirection.

### Obvious

Code whose purpose, state, errors, and next change are visible in one pass. Obvious
code minimizes the context a maintainer must load and avoids cleverness that needs a
tour guide.

## Principles

### Think from first principles

Identify the invariant, user outcome, and real constraints before preserving an
existing design. Accidental complexity is not a requirement.

### Every operational number needs a receipt

Before adding or changing an operational limit:

1. Name the resource or failure the number controls.
2. Gather the best available evidence.
3. Derive the value from that evidence.
4. Record the receipt next to the configuration, test, ADR, or runbook.
5. Add observability or a tripwire that reveals when the evidence stops matching
   reality.

When reviewing existing code, do not invent a replacement number. Surface the
missing receipt and describe the measurement needed.

### Fail loudly and actionably

An error should say:

- what operation failed
- why it failed
- which input, invariant, dependency, or limit was involved
- what the caller or operator can do next

Do not return partial, empty, cached, or default data unless the interface explicitly
promises degraded behavior and makes that state observable.

When a reader hits state an invariant says can't exist, fix the writers, not the
reader. A tolerance flag (`missingAsZero`, `allowBlank`) hides the broken rows from the
check that found them and spreads to every later reader. Create dependent state when
it's first needed, backfill rows that predate the rule, and keep the reader failing.

### Turn assumptions into tripwires

For every correctness-critical assumption, ask: “How will we know when this becomes
false?” Put the check at the earliest boundary with enough context to explain the
failure.

### Turn mistakes into tripwires

Treat “lint rule” as shorthand for executable enforcement. When fixing a confirmed
agent mistake, identify the failure pattern and strengthen the smallest check that
would have caught it:

- **Static pattern or dependency violation:** enable or extend an existing lint or
  architecture rule before writing a custom checker.
- **Behavioral bug:** retain a regression test at the module's public interface.
- **Invalid state or input:** tighten the type, schema, or database constraint at
  the boundary that owns the invariant.
- **Agent workflow failure:** use a deterministic tool check where possible, or a
  realistic behavioral eval when judgment is involved.

Prove the check rejects the known failure and accepts the corrected case. Wire it
into the normal validation path so the next occurrence is caught automatically.
Retain the check in the repository with the fix. A temporary reproduction that is
deleted after debugging proves this fix worked once; it provides no future
protection. Prefer checks that catch the demonstrated failure class across relevant
call sites over checks tied to the exact text of one patch.

If an existing check already catches it, fix why that check was skipped or ignored;
do not add a duplicate. Keep enforcement scoped to the demonstrated failure class,
without turning an isolated typo or preference into a universal rule.

If reliable automation is not practical within the task, state the remaining gap
and the verification used. A prompt reminder may explain the invariant, but does
not count as enforcement. Report which check now catches the mistake, or which
gap remains.

### Understand before optimizing

Remove unnecessary work and known pathological shapes such as N+1 I/O first. When a
performance change trades away readability, flexibility, or correctness, measure the
real path before and after.

### Prefer obvious over clever

Prefer direct control flow, narrow interfaces, explicit state, and names from the
domain. Add an abstraction only when it removes duplication, centralizes an
invariant, or hides real complexity.

### Minimize hidden state

Make mutation, caching, retries, fallbacks, I/O, and lifecycle ownership visible in
types, names, configuration, or module boundaries. Surprising behavior is a design
bug even when it works.

### Design for maintenance

Optimize for the next change:

- delete obsolete code and checks
- keep decisions and receipts discoverable
- place invariants where one change updates every caller
- prefer reversible changes
- avoid seams until variation is real

## Working Method

Use this loop during planning, implementation, review, and verification:

1. **Understand** — state the outcome, invariants, and evidence already available.
2. **Hunt landmines** — identify delayed failures, hidden state, and unvalidated
   assumptions.
3. **Collect receipts** — justify limits and trade-offs with evidence.
4. **Install tripwires** — make violated assumptions fail clearly. For each confirmed
   mistake, fix the cause and retain the smallest check that catches its recurrence.
5. **Simplify** — delete work, collapse pass-through layers, and make the design
   obvious.
6. **Verify** — produce falsifiable evidence for the user-visible claim and show the
   retained check rejects the original failure through normal validation. Report any
   remaining enforcement gap explicitly.

## Review Questions

- What future failure is hidden by this apparently harmless choice?
- Which operational numbers lack receipts?
- Which assumptions are comments instead of tripwires?
- Which executable check catches this mistake next time?
- Can a failure still look like success?
- Is state or I/O hidden from the interface?
- Does this abstraction remove complexity or merely relocate it?
- What can be deleted?
- What evidence would prove this change works?
