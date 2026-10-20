# Technical Design Docs

A design doc gets a decision right before code makes it expensive to change. A good one is short, explains the problem better than anyone else could, and has one diagram a reader understands without the prose.

## Contents

- When to write one
- Length
- Shape
- The problem section
- The diagram
- What to leave out
- Review gates
- Template

## When to write one

Write one when two or more apply. Otherwise build it, or write a paragraph in the ticket.

- The right design is unclear, or reasonable people would pick differently
- More than a few weeks of work, or more than one PR in sequence
- Another team, service, or public API depends on the result
- A choice is hard to reverse: storage, schema, protocol, language, vendor
- Security, privacy, money, or data loss is at stake

A doc that only says how to build something, with no trade-offs or alternatives, is an implementation manual. Skip it and write the code.

## Length

**One to three pages.** That covers most features. A large multi-quarter project still keeps the body short and links sub-docs for each hard sub-problem. If the doc specifies every detail, it has become the implementation.

Keep a decision in the doc only if it's expensive to get wrong. Ask "what's the penalty for being wrong?" A button label or a swappable library can change in an hour, so leave it out. Storage, data model, and public interfaces stay in.

## Shape

| Section | Holds | Size |
|---|---|---|
| Summary | Problem and proposal in 2–3 sentences. Write it last | 3 lines |
| Problem | Current state, who it hurts, evidence, why now | the largest section |
| Goals / non-goals | Outcomes, measurable. Non-goals are things that could reasonably be goals but are excluded | 3–6 bullets |
| Design | The diagram, then the key idea, then only the hard-to-reverse decisions | about a page |
| Alternatives | Each strong option and why it lost. A table works | a few lines |
| Risks and rollout | Only the cross-cutting concerns that apply: security, privacy, failure modes, observability, migration, rollback, and what happens if the flag is turned off after launch | one line each |
| Open questions | Each states the question, the options, and the next step. Resolved ones become one-line decisions | as needed |

Detail that only implementers need (PR breakdown, API field lists, migration steps) goes in a collapsed appendix or a linked doc.

## The problem section

Most weak docs are weak here. A reviewer who doesn't understand the problem can't judge the design, however good the design is.

- **Readable cold.** Someone outside the team should get it from the first page alone.
- **Evidence, not adjectives.** "p95 lookup went from 100 ms to 600 ms as the table passed 40M rows; 95% of reads hit 3% of rows" beats "lookups are slow".
- **No solution in the problem.** "We need a cache" is a proposal. "Reads are slow because X" is the problem.
- **Why now.** What changed, or what breaks if this waits a quarter.
- **Goals as impact, not implementation.** "Deploys cause no user-visible errors", not "move to Kubernetes". Name the number that proves it ("p95 < 150 ms at 2× current load").

## The diagram

One diagram that explains the design without the prose. Usually that's a system-context view (what talks to what) or the main flow. Add a second only if it shows something the first can't.

- **Title** states the type and scope: "Flow: card authorization with the new cache".
- **Every box** is named and says what it does. Name the technology where it matters.
- **Every arrow** points one way and is labelled with its intent ("reads balance", "publishes OrderPaid"), never "uses".
- **Legend** for any color, shape, or dashed line that carries meaning. Spell out acronyms.
- **Show the change.** Highlight new or changed parts, or show before and after side by side.
- **Keep it editable.** Mermaid in the doc (GitHub, Linear and Notion render it), or `/bruhs:doodle` for richer layouts with the source linked. Never a whiteboard photo.

Fewer boxes beat completeness. If the diagram needs a paragraph to explain, split it or cut boxes.

## What to leave out

- Background the reader already has, and history that doesn't change the decision
- Code, except a novel algorithm; link a prototype instead
- Full API and schema definitions. Sketch only the parts that carry a trade-off
- Sections that don't apply. Delete them rather than writing "N/A"
- Long write-ups of rejected options. A few lines each is enough

Prose follows `practices/writing.md`: fewest words that keep the meaning, point first, lists and tables over paragraphs.

## Review gates

Before asking anyone for review:

1. **Cold read.** A fresh subagent reads only the doc, then states the problem, the proposal, the riskiest part, and the decision a reviewer would push back on. Fix whatever it gets wrong or misses.
2. **Skeptic test.** Read it as the toughest reviewer and answer their objections in the doc.
3. **Hand-off test.** Could a teammate implement it from the doc alone, as intended?

Write the doc before the code. A prototype that proves a risky part is good evidence; link it. Update the doc while the design is unshipped. After it ships, the doc records why, and new decisions get a new doc that links back.

## Template

````markdown
# <Title>

**Status:** draft | in review | approved | shipped · **Author:** <name> · **Reviewers:** <names> · **Updated:** <YYYY-MM-DD>

<Summary: the problem and the proposal in 2–3 sentences.>

## Problem

<Current state, who it hurts, numbers, why now.>

## Goals

- <Measurable outcome>

**Non-goals:** <reasonable goals we're excluding>

## Design

```mermaid
<one diagram: title, labelled arrows, the change highlighted>
```

<Key idea in a paragraph. Then the hard-to-reverse decisions, one short subsection or bullet each.>

## Alternatives

| Option | Why not |
|---|---|
| <option> | <one line> |

## Risks and rollout

- **<Concern that applies>:** <one line>

## Open questions

- **<Question>:** <options> → next step: <who does what>

<details><summary>Appendix</summary>

<PR breakdown, field lists, migration steps.>

</details>
````
