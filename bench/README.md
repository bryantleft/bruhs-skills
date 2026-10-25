# bruhsbench

An A/B benchmark for bruhs. The same coding tasks run through three agent CLIs, each in two
arms:

- **bare**: no skill installed.
- **bruhs**: bruhs as a user installs it, plus the `/expect` skill and the chrome-devtools MCP.

| Model | CLI | Effort |
|---|---|---|
| claude-opus-5-5 | `claude -p` | high |
| gpt-6.1-sol | `codex exec` | high |
| grok-4.7 | `grok -p` | high |

The prompt, model, effort, tools, sandbox and preamble are the same in both arms. The only
differences are the bruhs install and the bruhs marker blocks in the repo's
CLAUDE.md/AGENTS.md. The question is whether the same request gives a better result with bruhs
installed.

## Setup

macOS only: the sandbox uses `sandbox-exec`.

```sh
cd bench
uv sync
uv run playwright install chromium     # screenshots for ui/copy tasks
```

Each CLI must be installed, on `PATH` and logged in:

- **claude**: run `claude setup-token`, then put the token in `bench/.env` (gitignored):

  ```sh
  CLAUDE_CODE_OAUTH_TOKEN=<token>
  ```

  `ANTHROPIC_API_KEY` also works. The macOS keychain login is never used, and no claude
  process starts without a token.
- **codex**: log in as usual. Only `~/.codex/auth.json` is copied into each run's home.
- **grok**: log in as usual. Only `~/.grok/auth.json` is copied into each run's home.

The bruhs arm also needs the `expect` skill at `~/.agents/skills/expect` (it is copied into
the bruhs arm's home) and `npx`, which starts chrome-devtools-mcp.

## Isolation and sandbox

- **Fresh home per run.** Every run gets its own `HOME` (and `CODEX_HOME` for codex) holding
  only auth, so the user's own skills, plugins, MCPs and account-synced
  extensions stay out of both arms. `bruhsbench probe` proves this for each CLI and arm.
- **Work outside `~`.** Run dirs, workspaces and homes live under `$BRUHSBENCH_WORK`
  (default `/private/tmp/bruhsbench/<results-id>/`), so a CLI walking parent directories never
  picks up `~/.claude` or similar. Only artifacts are copied into `bench/results/`.
- **OS sandbox.** Agents, judges, probes, grader check commands and capture dev servers all run
  under `sandbox-exec`. They cannot read or write the real home (except an allowlist of tool
  install dirs and caches), other runs, or the keychain, and they get no clipboard,
  app-launching or process inspection. Each process writes only to its own run root and a
  private `TMPDIR`. Network access stays on.
- **Hardened harness.** Git runs on agent-controlled repos with hooks, fsmonitor and filters
  disabled. Agent-written files are read without following symlinks. Transcripts are piped
  straight out of the sandbox, so an agent can't rewrite its own.
- **Contamination check.** Each transcript and CLI session log is scanned for paths under
  the real home or the task's source repo. A contaminated run drops its (task, model, repeat)
  pair from both arms.
- **Blind judging.** Judges run with no tools. They see redacted diffs, final messages and
  screenshots in a seeded A/B order, and never judge their own model family's runs.
- **Accepted limitations.** Localhost TCP between sandboxed processes is open. In the bruhs
  arm, chrome-devtools can reach the web, while native web tools are off in both arms.

## Commands

Every stage reads and writes plain files under one results dir and skips work that's already
done, so you can rerun or resume any stage. `--force` redoes it. The default results dir is
`bench/results/full`; `--pilot` switches to `bench/results/pilot`, and `--results DIR`
picks any other dir.

| Command | What it does |
|---|---|
| `uv run bruhsbench probe [--models claude codex grok]` | Isolation probe for every CLI x arm: each sees exactly its arm's skills and MCPs, and the two arms differ only by bruhs. Prints setup steps when the claude token is missing. |
| `uv run bruhsbench run [--pilot] [--tasks ID…] [--models …] [--repeats N] [--heldout] [--parallel N] [--timeout MIN]` | Runs the matrix. Defaults: all non-held-out tasks, 3 models, 2 arms, 3 repeats, 45-minute timeout. `--pilot` runs the tasks in `bench/pilot.toml` with 1 repeat and can't be combined with `--tasks`. Runs that already have `result.json` are skipped. |
| `uv run bruhsbench capture` | Screenshots ui/copy runs and each task's starting state at desktop and mobile sizes, in light and dark. |
| `uv run bruhsbench grade` | Grades every finished run in this order: commands, scope, checklist, audit, honesty. The checklist judges see the screenshots, so run `capture` first (`grade` warns about ui/copy runs without screenshots). Runs with a grader error or an invalid checklist are retried on the next call. |
| `uv run bruhsbench judge` | Blind pairwise verdicts for ui/copy: each (task, model, repeat) is judged by both other model families. Judge errors are retried on the next call. |
| `uv run bruhsbench spotcheck [-n 20] [--seed 0] [--port 8765] [--force]` | A local page (127.0.0.1 only) where you blind-pick ~20 ui/copy pairs. Picks are saved to `spotcheck.json`, and it prints how often the judges agreed with you. The first sample drawn is reused on later runs; `--force` draws a new one and clears the picks (the old file is kept as `spotcheck.json.bak`). |
| `uv run bruhsbench report [--public] [--out DIR]` | Writes an HTML report and its markdown twin. The private report goes to `<results>/report/`; `--public` writes to `bench/results/published/<date>/`. |

Held-out tasks (anything under `tasks-heldout/`, or with `heldout = true`) are refused unless
you pass `--heldout`. With `--heldout` and no `--tasks`, `run` runs only the held-out set.

Run the stages in order: `probe`, `run`, `capture`, `grade`, `judge`, `spotcheck`, `report`.
`capture` and `grade` need each run's workspace, which lives in the work root under
`/private/tmp`. Finish both before a reboot clears it.

## Method

- **Tasks.** Public seeded fixtures (`tasks/`) and real tasks from past sessions in private
  repos (`tasks-private/`, gitignored). Each task has one category and a frozen hidden
  checklist, hidden tests or known issues.
- **Win rule (frozen).** Each category has one primary metric. For audit and ship, a task is
  a bruhs win or loss when the bruhs mean minus the bare mean is more than the margin. For
  the 1/0 categories, one arm needs at least two more passing repeats than the other, however
  many repeats survived. Anything else is a tie.

  | Category | Primary metric | Tie margin |
  |---|---|---|
  | feature / debug | hidden tests pass, no regressions and honest "done" claims, all three (1/0 per repeat). Tasks without hidden tests count "hidden tests pass" as satisfied. | 1 passing repeat: a win needs 2 or more |
  | audit | F1 vs known issues | 0.05 |
  | ui / copy | blind pairwise preference (bruhs 1, tie 0.5, bare 0, per judge verdict) | win at 55% or more, loss at 45% or less |
  | pr-review | full checklist hit, checks green and hidden tests pass (1/0) | 1 passing repeat: a win needs 2 or more |
  | ship | checklist score | 10 points |

- **Exclusions.** A run that is contaminated, errored, or timed out with no diff drops its
  (task, model, repeat) pair from both arms. So does a missing grade, such as an invalid
  checklist. Judge errors are excluded and counted.
- **Headline.** Per model, the bruhs win rate counts ties as half, so 50% means no
  difference. It comes with a 95% bootstrap CI (10,000 resamples over tasks) and is shown
  next to the same numbers for the seeded tasks only, which anyone can reproduce.
- **Reported alongside.** Cost, time, turns and scope creep never decide a task; they're
  reported next to the result. So are run health per arm (errors, timeouts, contamination,
  orphaned output, judge errors), how often bruhs actually loaded in the bruhs arm, and any
  mention of bruhs in a bare-arm transcript.
- **Judge check.** If the judges agree with your spot-check picks less than 75% of the time,
  ui/copy results come from your picks only, and the report says so.

## Where results go

```
bench/results/<name>/                 # gitignored, except published/
  matrix.json, excluded.json          # pinned bruhs commit, CLI versions, models, seed
  <task>__<cli>__<arm>__r<n>/         # result.json, transcript.jsonl, stderr.txt, diff.patch,
                                      # final.txt, grades/*.json, screens/*.png
  _before/<task>/                     # starting-state screenshots
  _pairs/                             # pairwise verdicts + pairs_key.json (A/B -> run)
  spotcheck.json                      # your blind picks
  report/report.{html,md}             # private report
bench/results/published/<date>/       # public report (committed)
```

The public report shows private-repo tasks only by category and score. Their prompts, paths,
repo names and screenshots are left out.
