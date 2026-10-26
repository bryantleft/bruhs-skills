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
  `PLAYWRIGHT_BROWSERS_PATH` and `RUSTUP_HOME` point back at the real (read-only) installs,
  so agents in both arms can launch Playwright's browsers and run cargo.
- **Work outside `~`.** Run dirs, workspaces and homes live under `$BRUHSBENCH_WORK`
  (default `/private/tmp/w/<12 hex>/`), so a CLI walking parent directories never
  picks up `~/.claude` or similar. Only artifacts are copied into `bench/results/`.
- **Opaque paths (ruling R40).** Nothing an agent sees names its arm or the benchmark: the
  work root, each run's dir (`<work root>/<12 hex>/{home,workspace}`) and its `TMPDIR` are
  opaque hashes under neutral bases (`/private/tmp/w`, `/private/tmp/t`). Only
  `<results>/work_ids.json` maps a run dir back to its run id. (The bruhs install itself,
  in the bruhs arm's home, is named bruhs: that is the treatment.) The workspace's git is
  neutral too (R42): the base commit is `dev <dev@localhost>`, "setup", tagged `base`
  (seeded fixtures start from an "initial" commit). Checklists frozen earlier that say
  `bench-base` get that tag only in the graders' own clones. Before an agent starts, the
  runner scans its prepared workspace for anything the harness or setup wrote that names the
  benchmark or an arm (`bruhsbench/visibility.py`: paths, added lines, decoded hex/base64,
  symlink targets, git metadata and reflogs); a hit fails the run with status `error`
  ("visibility: …") and the agent never runs (ruling R47; a few seconds per workspace).
  `uv run pytest -m private` runs the same scan over every private task in both arms.
- **OS sandbox.** Agents, judges, probes, grader check commands and capture dev servers all run
  under `sandbox-exec`. They cannot read or write the real home (except a read-only
  allowlist of tool installs: the CLIs, node, uv's Pythons, `~/.cargo/{bin,registry,git}`,
  rustup's toolchains and Playwright's browser dirs, never Playwright's `mcp-*` browser
  profiles or cargo's credentials and config), other runs, or the keychain, and they get no clipboard,
  app-launching or process inspection. Each process writes only to its own run root and a
  private `TMPDIR`. Network access stays on.
- **Short private `TMPDIR`.** The Convex local backend binds a unix socket under `TMPDIR`,
  and macOS caps a socket path at 104 bytes, so `TMPDIR` must be 77 characters or fewer. Each
  process's `TMPDIR` is therefore `/private/tmp/t/<12 hex>` (a hash of its root; the base is
  `$BRUHSBENCH_TMP`, an absolute path whose resolved form is measured), whatever the results-dir name or run id. Only that process can reach
  it. It is deleted with its run dir or scratch dir. `run`, `pipeline` and workspace setup
  stop at once if `$BRUHSBENCH_TMP` would make it too long.
- **Hardened harness.** Git runs on agent-controlled repos with hooks, fsmonitor and filters
  disabled. Agent-written files are read without following symlinks. Transcripts are piped
  straight out of the sandbox, so an agent can't rewrite its own.
- **Contamination check.** Each transcript and CLI session log is scanned for paths under
  the real home or the task's source repo, other than the tool installs the sandbox lets
  every run read (Playwright's browsers, node, the CLIs). A contaminated run drops its
  (task, model, repeat) pair from both arms.
- **Blind judging.** Judges run with no tools. They see redacted diffs, final messages and
  screenshots in a seeded A/B order, and never judge their own model family's runs.
- **Accepted limitations.** Localhost TCP between sandboxed processes is open. In the bruhs
  arm, chrome-devtools can reach the web, while native web tools are off in both arms.
  Writes to the shared `/tmp` are denied (ruling R39): parallel runs of a task would
  otherwise share and clobber the same scratch names. Agents in both arms reach for
  `/tmp` (scratch scripts, screenshots, build output), get "Operation not permitted" and
  retry in the workspace or in `$TMPDIR`, which works. The pilot showed this in both arms
  at similar rates; it costs turns and can add out-of-scope files, which never decide a
  task.

## Commands

Every stage reads and writes plain files under one results dir and skips work that's already
done, so you can rerun or resume any stage. `--force` redoes it. The default results dir is
`bench/results/full`; `--pilot` switches to `bench/results/pilot`, and `--results DIR`
picks any other dir.

| Command | What it does |
|---|---|
| `uv run bruhsbench probe [--models claude codex grok]` | Isolation probe for every CLI x arm: each sees exactly its arm's skills and MCPs, and the two arms differ only by bruhs. Prints setup steps when the claude token is missing. |
| `uv run bruhsbench digest [--out FILE]` | Writes `tasks-private/_digest.md` (gitignored) for review before freezing. For every non-held-out real task it lists the id, category, verbatim prompt, and each checklist item or known issue with its source (from `*_src.py` or the task's NOTES.md) and any `flag_for_user` note. Seeded tasks get one line each. |
| `uv run bruhsbench freeze [--tasks ID…]` | Pins every task's definition and grading: one SHA-256 per task, private tasks in `tasks-private/_frozen.sha256` (gitignored), public ones in `bench/frozen.sha256` (committed), each with a `*.manifest.json` of per-file hashes. `--tasks` refreezes only those ids. It refuses, unless you pass `--force`, to freeze a task at a definition other than the one an existing `bench/results/*/matrix.json` pinned. What is hashed is documented in `bruhsbench/freeze.py`. In short: every file in the task dir (fixture, seed data by content hash, hidden tests, checklist and known-issues JSON, scripts) plus the `_shared/<name>/` dirs its scripts name, minus `NOTES.md`, `*_src.py` and caches. |
| `uv run bruhsbench run [--pilot] [--tasks ID…] [--models …] [--repeats N] [--heldout] [--parallel N] [--timeout MIN] [--allow-unfrozen]` | Runs the matrix. Defaults: all non-held-out tasks, 3 models, 2 arms, 3 repeats, 45-minute timeout. `--pilot` runs the tasks in `bench/pilot.toml` with 1 repeat and can't be combined with `--tasks`. Runs that already have `result.json` are skipped. Outside `--pilot` it refuses to start if a selected task is missing from the freeze or differs from it, and it names the files that changed. `--allow-unfrozen` overrides that, for development only. Every start records the task hashes it ran with in `matrix.json`, along with any unfrozen tasks and the override. The first start's hashes are pinned (pilot included), and so is a content hash of the exported bruhs skill (not the repo commit: a commit that changes only the harness doesn't block a resume; each start records its harness commit). A resume with a changed task or a changed bruhs skill is refused, and so are `grade`, `capture`, `judge` and the pipeline's per-run capture and grade for a task that no longer matches its pinned hash, so runs are always graded against what they ran with. |
| `uv run bruhsbench pipeline [same options as run] [--no-cleanup] [--post-parallel 2]` | `run`, plus capture (ui/copy), grade and cleanup for each run as soon as it finishes, still in parallel across runs. Once a run is captured and fully graded, its work dir (workspace and home) is deleted and `result.json` records `workspace_deleted: true`. Runs whose grading fails partway, or whose capture hit a harness error (the dev server didn't start, say; page errors alone don't count), keep their workspace, and the next `pipeline` or `capture` call retries them. Use this for the full matrix. |
| `uv run bruhsbench capture` | Screenshots ui/copy runs and each task's starting state at desktop and mobile sizes, in light and dark. If a run's checklist was already graded without screenshots, a successful capture regrades the checklist and then honesty. The old checklist grade is kept as `grades/checklist.superseded.json`. `pipeline` does the same. |
| `uv run bruhsbench grade` | Grades every finished run in this order: commands, scope, checklist, audit, honesty. The checklist judges see the screenshots, so run `capture` first (`grade` warns about ui/copy runs without screenshots). Runs with a grader error or an invalid checklist are retried on the next call. |
| `uv run bruhsbench clean [--all] [--force]` | Deletes the work dirs of runs that are already captured and graded, after you ran the stages one by one. It lists runs kept because their capture failed, and any files it couldn't delete. `--all` deletes this results dir's whole work root. It refuses while a `run`, `pipeline`, `capture` or `grade` is using that work root (they hold a shared lock on `<work root>.lock`, which sits next to the work root rather than inside it, and `clean --all` holds that lock exclusively for the whole deletion); `--force` overrides. It never touches `bench/results` or `bench/tasks*`. It removes symlinks without following them and clears immutable flags it finds. |
| `uv run bruhsbench judge` | Blind pairwise verdicts for ui/copy: each (task, model, repeat) is judged by both other model families. Judge errors are retried on the next call. |
| `uv run bruhsbench spotcheck [-n 20] [--seed 0] [--port 8765] [--force]` | A local page (127.0.0.1 only) where you blind-pick ~20 ui/copy pairs. Picks are saved to `spotcheck.json`, and it prints how often the judges agreed with you. The first sample drawn is reused on later runs; `--force` draws a new one and clears the picks (the old file is kept as `spotcheck.json.bak`). |
| `uv run bruhsbench report [--public] [--out DIR]` | Writes an HTML report and its markdown twin. The private report goes to `<results>/report/`; `--public` writes to `bench/results/published/<date>/`. |

Held-out tasks (anything under `tasks-heldout/`, or with `heldout = true`) are refused unless
you pass `--heldout`. With `--heldout` and no `--tasks`, `run` runs only the held-out set.

Before the full matrix, review `digest` once and run `freeze`. Then run the stages in order:
`probe`, `run`, `capture`, `grade`, `judge`, `spotcheck`, `report`, or `probe`, `pipeline`,
`judge`, `spotcheck`, `report`. `capture` and `grade` need each
run's workspace, which lives in the work root under `/private/tmp`. Finish both before a
reboot clears it. Judging, spot-checks and reports only read the results dir, so they work
after cleanup.

### Disk

A full matrix is about 290 runs, and each run's workspace holds a checkout plus installed
dependencies. That is about 0.1 GB for the mints tasks, whose node_modules, Convex binary and
seed data are APFS clones, and 0.1 to 0.5 GB for seeded `npm ci` tasks. Kept workspaces
would add up to tens of GB, so use `pipeline`, or `clean` after `grade`.

- **Free-space guard.** `run`, `pipeline`, `capture` and `grade` check free space on the
  work and results filesystems before each run, capture or grade. The threshold is
  `BRUHSBENCH_MIN_FREE_GB`, 10 by default (a non-number is an error). When space is short and other runs are live, the
  guard waits up to 20 minutes for their cleanup. If space still doesn't free up, no new
  work starts, live runs finish normally, and the command exits with code 4. Rerun the same
  command to resume. Each `result.json` records `free_gb_at_start`.
- **Contention.** Under `pipeline`, capture and grading run next to the agent runs and
  compete with them for CPU (builds, test suites, the capture browser) and local ports (dev
  servers on free ports, so they don't collide). `--post-parallel` (default 2) caps how
  many runs capture or grade at once. A slow grade holds its agent slot until it finishes.
  A run waits for disk space before it takes a slot, and a run with only cleanup left
  never waits or takes a slot, because cleanup is what frees the space.
- **Clones, not copies.** Grading and capture work in APFS clones (`cp -c`) of the
  workspace. Real-repo checkouts fetch only the base commit's history. A task's `setup.sh`
  should copy large seed data with `cp -c` (see `tasks-private/_shared/mints/install.sh`).

## Method

- **Tasks.** Public seeded fixtures (`tasks/`) and real tasks from past sessions in private
  repos (`tasks-private/`, gitignored). Each task has one category and a frozen hidden
  checklist, hidden tests or known issues.
  A task's `setup.sh` (installing deps, or putting the repo on the branch a review was
  left on) runs before the base commit (tagged `base`); an optional `after_base.sh` runs after it,
  for tasks that start from uncommitted work. Hidden tests (`hidden/`) are copied into a
  copy of the finished workspace and run by the task's `checks.hidden`, which is
  self-contained: tasks that test in a browser build and serve the app themselves. Reference
  solutions live in `tests/reference/<task>/`, outside every workspace, and
  `tests/test_seeded_tasks.py` checks that each seeded task scores low untouched and full
  with its reference solution.
- **Audit scoring.** Each finding is matched to a known issue by the lines it cites (an
  issue can list several valid sites), with a judge deciding when the location is
  ambiguous, lands only on a decoy, or hits nothing. A finding that matches no known issue
  is judged against the code it cites: a real problem the task didn't plant
  (`valid_unlisted`) doesn't lower precision, while a wrong one or a flagged decoy does.
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

- **Regressions (R31).** A regression is a test that passed at base and is still there but
  failing after the run. A base-passing test that is missing afterwards, such as a renamed
  one, is listed in `removed_tests` and doesn't count as a regression. The exception is a
  test file that fails to load (a pytest collection error, or a jest/vitest suite with no
  results). In that case missing tests can't be told apart from tests that never ran, so
  all of them count as regressions.
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
  work_ids.json                       # opaque work-dir name -> run id (R40)
  matrix.json, excluded.json          # pinned bruhs content hash, models, seed, repeats,
                                      # task hashes; per start: harness commit, CLI versions
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
