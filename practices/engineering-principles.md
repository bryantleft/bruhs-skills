# Engineering Principles

These principles govern every bruhs command and every stack-specific practice. When
another recommendation conflicts with this file, this file wins.

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

### Turn assumptions into tripwires

For every correctness-critical assumption, ask: “How will we know when this becomes
false?” Put the check at the earliest boundary with enough context to explain the
failure.

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
4. **Install tripwires** — make violated assumptions fail clearly.
5. **Simplify** — delete work, collapse pass-through layers, and make the design
   obvious.
6. **Verify** — produce falsifiable evidence for the user-visible claim.

## Review Questions

- What future failure is hidden by this apparently harmless choice?
- Which operational numbers lack receipts?
- Which assumptions are comments instead of tripwires?
- Can a failure still look like success?
- Is state or I/O hidden from the interface?
- Does this abstraction remove complexity or merely relocate it?
- What can be deleted?
- What evidence would prove this change works?
