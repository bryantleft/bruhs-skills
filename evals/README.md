# Evaluations

Per Anthropic's skill-authoring guidance: *"Create evaluations BEFORE writing extensive documentation. This ensures your Skill solves real problems rather than documenting imagined ones."*

Each file in this directory is a JSON scenario that tests one command, a script in `scripts/`, or a cross-cutting flow. Run them manually against Haiku / Sonnet / Opus and observe:

- Does the right command activate for the natural-language query?
- Does the agent follow the documented workflow?
- Are load-bearing rules (e.g. peep's local validation, yeet's Conventional Commits, slop's priority order) actually applied?
- For script-level scenarios: does the script produce the expected stdout / stderr / exit code, and are its file-system side effects safe (atomic, idempotent, non-destructive outside the markers)?

## Running an evaluation manually

There's no built-in runner. The lightweight process:

1. Open a fresh AI coding agent session with the bruhs plugin installed (Claude Code, Codex, or any agent that reads CLAUDE.md / AGENTS.md).
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

### Commands (≥ 3 scenarios each: happy / edge / adversarial)

| Command | Scenarios |
|---|---|
| `/bruhs` (interactive) | `interactive-*.json` |
| `/bruhs:claim` | `claim-*.json` |
| `/bruhs:cook` | `cook-*.json` |
| `/bruhs:deepen` | `deepen-*.json` |
| `/bruhs:dip` | `dip-*.json` |
| `/bruhs:doodle` | `doodle-*.json` |
| `/bruhs:drill` | `drill-*.json` |
| `/bruhs:peep` | `peep-*.json` |
| `/bruhs:slop` | `slop-*.json` |
| `/bruhs:spawn` | `spawn-*.json` |
| `/bruhs:yeet` | `yeet-*.json` |

### Scripts (script-level scenarios)

| Script | Scenarios |
|---|---|
| `scripts/sync_bruhs_block.py` | `sync-bruhs-block-*.json` |
| `scripts/read_bruhs_block.py` | `read-bruhs-block-*.json` |
| `scripts/derive_stack_rules.py` | `derive-stack-rules-*.json` |

Script scenarios assert on stdout, stderr, exit code, and observable file-system side effects (atomicity, idempotency, hand-written content preservation outside the markers).

### Cross-cutting flows

Scenarios that span multiple commands or test invariants of the marker-block system itself:

- `claim-legacy-bruhs-migration.json` — port `.claude/bruhs.json` → marker blocks
- `claim-migration-redetect.json` — ignore the legacy file, re-detect from code
- `cook-persists-discovered-skills.json` — newly discovered skills round-trip back into `bruhs:state`

Run these whenever the migration path, the marker format, or the mirror invariant (CLAUDE.md ≡ AGENTS.md inside the blocks) is touched.
