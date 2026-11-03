# Evaluations

Each folder in this directory is one test case: a realistic prompt plus graders
that say what a good run looks like. The layout is the one
[`claude plugin eval`](https://code.claude.com/docs/en/plugin-evals) reads, and it
is also what skill-creator reads. Every file is plain Markdown or YAML, so the same
cases work with any agent: Claude Code, Codex, Cursor, Gemini CLI, or anything else
that loads `SKILL.md` and reads `CLAUDE.md` / `AGENTS.md`.

The deterministic script tests are not here. They live in `tests/` and need no
model: `bash tests/run_script_tests.sh`.

## Case layout

```
evals/
└── cook-from-ticket-id/          # case name: what the test checks
    ├── prompt.md                 # run settings, then the user's message verbatim
    ├── case.yaml                 # name, preconditions, expected outcome
    └── graders/
        ├── 01-step-0-confirms-bruhs-state-block-in.md
        ├── ...
        └── 07-avoids-known-failure-modes.md
```

- **`prompt.md`**: the frontmatter holds the run limits (`max_turns`,
  `timeout_seconds`, `allowed_tools`) and `tags` (the command under test). The
  body is sent to the agent exactly as written. Any unknown frontmatter key makes
  the case fail to load, so free text goes in `case.yaml`.
- **`case.yaml`**: `schema_version: "1.1"` (quoted), `name` (same as the folder),
  `description` (the command under test, the preconditions, and the files the
  preconditions assume) and `expected_outcome`.
- **`graders/NN-*.md`**: one check per file, all `type: llm` with
  `focus: trace`, so the judge sees what the agent did and not just its last
  message. Each body is a PASS/FAIL rubric in prose. The last grader in each case
  turns the old `failure_modes` list into FAIL conditions.

### Keeping graders provider-neutral

Grade what the agent did, not which harness tool it used. Some graders still name
Claude Code tools (`AskUserQuestion`, `ToolSearch`, `Task`, `mcp__*` names),
because the command docs name them. Each of those graders ends with a note telling
the judge that the equivalent mechanism on another harness counts: asking the user
directly, calling the tool directly, the harness's own subagent facility, or the
same MCP server and tool under that harness's naming. Add the same note to any new
grader that names a harness tool. Better still, describe the behavior instead
("asks the user to pick an approach").

## Running the cases

**No case sets up its workspace yet.** Every case has preconditions in `case.yaml`
(a repo with a `bruhs:state` block, a Linear ticket, an open PR) that a fresh,
empty run does not have. Until a case gains a `context.scaffold_script` and, if it
calls Linear or another MCP server, mocks under `mocks/<server>/`, run it in a
scratch repo you set up by hand. Under `claude plugin eval` it will mostly score
low for lack of fixtures, not for faults in the skill.

### Claude Code (`claude plugin eval`, v2.1.269+)

From the repo root:

```bash
# one case, one run, no baseline: the cheapest smoke test
claude plugin eval . --case cook-from-ticket-id --runs 1 --ablation none \
  --allow-tools Write,Edit,Bash

# every case for one command, with the no-plugin baseline
claude plugin eval . --tag peep --allow-tools Write,Edit,Bash
```

These are real, billed model runs. The full suite is 59 cases × 3 runs × 2 arms,
which is roughly 350 agent runs, plus 3 judge calls per grader per run. Filter with
`--case` or `--tag`. Results go to `evals/results/` (gitignored).

### Any other agent

1. Open a fresh session with bruhs installed. Point the agent at
   `skills/bruhs/SKILL.md`, or install it however your agent loads Agent Skills.
2. Set up a scratch repo that matches the preconditions in `case.yaml`.
3. Send the body of `prompt.md` as the user message.
4. Grade the transcript against each file in `graders/`, recording pass/fail with
   evidence. A second model reading the transcript and the grader files does this
   well.

For runners that read the agentskills.io format (a single `evals/evals.json`),
generate one:

```bash
python3 tests/export_evals_json.py -o /tmp/bruhs-evals.json
```

Each case becomes one entry, with `prompt`, `expected_output`, `assertions` (one
per grader) and an extra `context` field holding the preconditions. Copy the file
to wherever your runner expects it, but not to `evals/evals.json` in this repo,
because skill-creator would then run every case twice.

## Adding a case

1. Create `evals/<case-name>/` (lowercase letters, digits and hyphens, starting
   with a letter, and none of `results`, `mocks`, `files`, `node_modules`,
   `true`, `false` or `null`). Start the name with the command, as in
   `yeet-no-linear`.
2. Copy `prompt.md`, `case.yaml` and one grader from an existing case and edit
   them.
3. Write one grader per observable behavior, plus one for the failure modes you
   expect. Several short graders give a steadier signal than one long one.
4. Run `python3 tests/export_evals_json.py --check`. It applies the rules that
   would make `claude plugin eval` refuse to load a case, costs nothing, and also
   runs as part of `tests/run_script_tests.sh`.

## Coverage

| Command | Cases |
|---|---|
| `/bruhs` (interactive) | `interactive-*` (3) |
| `/bruhs:claim` | `claim-*` (6) |
| `/bruhs:cook` | `cook-*` (10) |
| `/bruhs:deepen` | `deepen-*` (3) |
| `/bruhs:dip` | `dip-*` (3) |
| `/bruhs:doodle` | `doodle-*` (3) |
| `/bruhs:drill` | `drill-*` (3) |
| `/bruhs:peep` | `peep-*` (9) |
| `/bruhs:slop` | `slop-*` (7) |
| `/bruhs:spawn` | `spawn-*` (4) |
| `/bruhs:yeet` | `yeet-*` (8) |
| `/bruhs:verify`, `/bruhs:walk`, `/bruhs:land`, `/bruhs:recap` | none yet |

### Cross-cutting flows

These cases span several commands or test the invariants of the marker-block
system:

- `claim-legacy-bruhs-migration`: port `.claude/bruhs.json` to marker blocks
- `claim-migration-redetect`: ignore the legacy file and re-detect from code
- `claim-marker-and-legacy-both-present`: Case A wins when a marker block and the
  legacy file both exist
- `cook-persists-discovered-skills`: newly discovered skills round-trip back into
  `bruhs:state`
- `cook-no-receipt-no-number`: operational limits need evidence, and a missing
  receipt becomes measurement work
- `slop-landmine-tripwire`: delayed failures, false success and unguarded
  assumptions use the shared vocabulary

Run these whenever the migration path, the marker format, or the mirror invariant
(`CLAUDE.md` ≡ `AGENTS.md` inside the blocks) changes.
