# Writing for Humans

Applies to everything a person reads: chat replies, PR bodies, ticket descriptions, review comments and replies, commit messages, recaps, Slack drafts. Write per *Rules*, then scan per *AI text tells* before sending.

## Contents

- Rules
- Chat vs documents
- Document shape
- AI text tells
- Read it back

## Rules

- **Fewest words that keep the meaning.** If a shorter version says the same thing, it wins. Cut until the next cut would lose meaning, not past it.
- **Lead with the point.** The first sentence is the takeaway; evidence follows. A reader who stops after one line still has it.
- **Short paragraphs.** One idea each. Past 4–5 lines, something inside wants to be its own paragraph, a list, or deleted.
- **Diagram or table instead of a wall of text.** When the point is a flow, branch, sequence, state change or case matrix, show it. Replace the prose, don't repeat it.
- **Lists for parallel items only.** Three independent items make a list, never a comma or semicolon chain. Cases with outcomes make a table. Three clauses of one argument stay prose.
- **Sequences of 3+ steps use a numbered list, not an arrow chain.** `read X → call Y → attach Z` can't be referenced ("step 2 failed"). Two-step `A → B` inline is fine, except in review findings.
- **Review findings use no arrows (`→`) and no em dashes (`—`).** Use sentence breaks, parentheticals, or a numbered list.
- **Bold sparingly.** For the 1–2 things a scanner can't miss.
- **Cut hedges and restatements.** "just", "really", "basically", "this ensures…". Most drafts are 20–30% too long.

Reference docs (this file, `practices/`) can be denser. They're re-read, not read once.

## Chat vs documents

| Surface | Case | Structure |
|---|---|---|
| Chat: Slack, PR/review comments, ticket comments, review replies | lowercase | only what the point needs |
| Documents: PR bodies, ticket descriptions, Notion pages, Google Docs | sentence case, headings included | see *Document shape* |
| Commit messages, PR titles | `type(scope): description` | per `_common.md` |

Lowercase chat reads peer-to-peer; sentence case in a three-line comment reads corporate. In documents, once bullets hold full sentences, lowercase hides where each sentence starts. Proper nouns, acronyms, code identifiers and ticket IDs keep their case everywhere.

## Document shape

- **Keep the surface's existing structure.** The repo's PR template, the project's ticket headings, the doc's outline. Add bold lead-in labels inside sections, not new headings.
- **First sentence is the point.** Then what a reader needs to act. Decisions and deviations go in one labeled place, never mid-paragraph.
- **PR bodies state behavior, not a diff walkthrough.** Two readers: a reviewer deciding where to look, and an agent checking each claim against the diff. Lead with what changes after merge and why, list changes as checkable behavior, put judgment calls under **Decisions**, and name where a bug would hide.
- **Background goes in a collapsed section** so the body stays one screen.
- **Read-back gate** before creating or updating a document: a fresh subagent reads only the document and states the point, the riskiest part, and any decision a reader might question. Fix what it gets wrong.

| Surface | Diagram | Collapsed background |
|---|---|---|
| GitHub | ```` ```mermaid ```` block | `<details><summary>` |
| Linear | ```` ```mermaid ```` block | `>>>` collapsible |
| Notion | mermaid code block | toggle block |
| Google Docs | table or rendered PNG (no mermaid) | appendix at the end |
| Slack | table or short ASCII sketch | thread reply |

## AI text tells

Zero tolerance in anything another person reads. Once a reader clocks one message as machine-written, every later message from the account reads that way. Silence beats an AI-sounding reply.

- **Em-dash chains.** Three per paragraph, or stacked mid-sentence (`— it's not just X, it's Y —`). Use commas, parens or a new sentence.
- **Parallel triads.** "Cleaner, faster, more maintainable." Collapse to one item or drop it.
- **"This ensures…" / "This allows…" closings.** The code already ensures it. Delete.
- **Rhetorical-question openers.** "What does this do?" then the answer. Write the answer.
- **Buried lede.** Mechanics or history before the point.
- **Diff narration in PR bodies.** "X reads Y, then Z sends it" retells the diff. State behavior and invariants.
- **Packed sentences.** Three or more cases chained with commas and semicolons. One case per line: a list, or a table when each case has an outcome.
- **Stacked fragments.** "copy matches verbatim. 283 chars, GSM-7, 2 segments" makes the reader rebuild the sentence. Write short full sentences with verbs.
- **Colon as the default connector.** "at most once per phone: keyed on the row" hides whether the second half is a reason, mechanism or example. Say which with "because", "by", "so". Colons stay for labels and lists.
- **Negation where a positive works.** "isn't reversing an opt-out" makes the reader undo a step. Name the positive case: "first-time START".
- **Opaque plan or requirement IDs.** "per R4", "AC3 is met" with no link. Say the rule, and link the plan if the citation matters.
- **Chatbot signoffs.** "Let me know if…", "Feel free to…", "Happy to…", "Great question".
- **Bold + italic stacks** (`***critical***`) and bolding every other clause.
- **Markdown in plain-text surfaces.** `## Summary` in a commit message, headers in a Slack thread.
- **Unprompted summaries** of what you just said.
- **Overexplaining a one-line change.** Three paragraphs for one line means the change is bigger than it looks, or the text is padding.
- **Curly quotes** (`“ ” ‘ ’`) in code, commits, or anything a shell touches. ASCII only there.

## Read it back

Paul Graham, *Write Simply*: *"The easier something is to read, the more deeply readers will engage with it."* Say it out loud; if you wouldn't say it that way, rewrite or cut.
