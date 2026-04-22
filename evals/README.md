# Evaluations

Per Anthropic's skill-authoring guidance: *"Create evaluations BEFORE writing extensive documentation. This ensures your Skill solves real problems rather than documenting imagined ones."*

Each file in this directory is a JSON scenario that tests one command or the top-level skill. Run them manually against Haiku / Sonnet / Opus and observe:

- Does the right command activate for the natural-language query?
- Does the agent follow the documented workflow?
- Are load-bearing rules (e.g. peep's local validation, yeet's Conventional Commits, slop's priority order) actually applied?

## Running an evaluation manually

There's no built-in runner. The lightweight process:

1. Open a fresh Claude Code session with the bruhs plugin installed.
2. Paste the `query` as the user message (with any `files` staged in a scratch repo).
3. Observe the assistant's response and tool use.
4. Compare against `expected_behavior`. Record pass/fail with notes.
5. Repeat across the model tiers you care about.

## Scenario schema

```json
{
  "skills": ["bruhs"],
  "command": "<slash command under test, or 'interactive' for /bruhs>",
  "query": "<user message verbatim>",
  "files": ["<optional staged files>"],
  "context": "<optional pre-conditions — branch state, config, etc.>",
  "expected_behavior": [
    "Specific observable outcome 1",
    "Specific observable outcome 2",
    "..."
  ],
  "failure_modes": [
    "Common ways this can go wrong — watch for these"
  ]
}
```

## Coverage

| Command | Scenarios |
|---|---|
| `/bruhs` (interactive) | `interactive-*.json` |
| `/bruhs:claim` | `claim-*.json` |
| `/bruhs:cook` | `cook-*.json` |
| `/bruhs:dip` | `dip-*.json` |
| `/bruhs:doodle` | `doodle-*.json` |
| `/bruhs:peep` | `peep-*.json` |
| `/bruhs:slop` | `slop-*.json` |
| `/bruhs:spawn` | `spawn-*.json` |
| `/bruhs:yeet` | `yeet-*.json` |

At least three scenarios per command (happy path, edge case, adversarial).
