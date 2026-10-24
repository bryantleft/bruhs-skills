# bruhs Benchmark Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** A reproducible A/B harness that runs the same coding tasks through Opus 5.5 (Claude Code), GPT-6.1-Sol (Codex), and Grok 4.7 (Grok Build) with and without bruhs, grades the outcomes, and publishes a report.

**Architecture:** A Python package `bruhsbench` under `bench/` with one module per stage: task loading → workspace prep (repo at base commit, bruhs blocks stripped or inserted) → isolated agent home per arm → headless CLI run → objective graders → screenshots → blind judging → aggregation/report. Every stage reads and writes plain JSON under `bench/results/<run-id>/`, so stages are rerunnable and resumable independently.

**Tech Stack:** Python 3.11, uv, pytest, Playwright (Python) for screenshots, the three agent CLIs (`claude` 2.1.308, `codex` 0.163.0, `grok` 1.0.70) for both running and judging, Jinja2 for the HTML report.

**Spec:** `docs/superpowers/specs/2026-10-24-bruhs-benchmark-design.md`

## Global Constraints

- Arms: `bare` and `bruhs`. Identical prompt, model, effort, tools, sandbox; only bruhs install + bruhs marker blocks differ.
- Models: `claude-opus-5-5` via `claude -p`; `gpt-6.1-sol` via `codex exec`; `grok-4.7` via `grok -p`. Reasoning effort `high` for all.
- Each run gets a fresh isolated agent home; only auth is copied in. No user skills, plugins, or MCPs leak into either arm.
- bruhs arm = bruhs (pinned commit of this repo) + `/expect` skill + chrome-devtools MCP. Both arms get Playwright in each fixture.
- No external MCPs (Linear, GitHub) in either arm. No pushes; no network writes.
- Same unattended preamble in both arms (exact text in Task 4).
- 3 repeats per (task × model × arm). Per-run timeout 45 min. No budget ceiling.
- Pilot: 3 tasks × 3 models × 2 arms × 1 repeat before the full run.
- Win rule and margins (frozen):

  | Category | Primary metric | Tie margin |
  |---|---|---|
  | feature / debug | all of (hidden tests pass, no regressions, honest-done) per repeat → 1/0 | 1 of 3 repeats |
  | audit | F1 vs known issues | 0.05 |
  | ui / copy | blind pairwise preference | 55/45 |
  | pr-review | all of (valid fixed, wrong pushed back, checks green) → 1/0 | 1 of 3 repeats |
  | ship | checklist score | 10% |

- Cost, time, scope creep never decide wins; reported beside them.
- Judges: the two model families other than the run's own. Judge/user agreement threshold 75% on ~20 sampled pairs; below that, UI/copy reported from user picks only.
- Hidden checklists frozen before any run; never edited after seeing agent output.
- Held-out: 4 tasks (2 real, 2 seeded) sealed, never run in pilot/full run.
- Private-repo source, prompts, checklists, and screenshots never committed; they live in gitignored `bench/tasks-private/` and `bench/results/`.

## Review Focus

- **Agent hangs or asks a question and waits** → the run times out at 45 min, is recorded as `status: "timeout"` with its partial diff graded, not dropped. (Task 5 test `test_timeout_recorded`.)
- **CLI auth expired mid-matrix** → the runner detects an auth-failure exit/output and stops the whole matrix instead of recording hundreds of zero-score runs. (Task 5 test `test_auth_failure_aborts_matrix`.)
- **Leakage of user's global config into the bare arm** → isolation probe fails loudly before any matrix starts. (Task 3 test `test_probe_detects_leaked_skill`.)
- **A real-repo base commit whose deps no longer install** (lockfile drift, removed packages) → setup failure marks the task `setup_failed` and excludes it from both arms equally, never one arm only. (Task 2 test `test_setup_failure_excludes_task`.)
- **Interrupted matrix** → rerunning skips completed runs (result.json present) and redoes partial ones. (Task 5 test `test_resume_skips_completed`.)

---

## File Structure

```
bench/
  pyproject.toml                 # uv project, package bruhsbench, pytest config
  README.md                      # how to run, method summary
  .gitignore                     # results/, tasks-private/, .venv/
  bruhsbench/
    __init__.py
    types.py                     # dataclasses shared by all stages
    tasks.py                     # load task.toml dirs
    workspace.py                 # checkout at base, strip/insert bruhs blocks, setup.sh
    homes.py                     # isolated agent home per (cli, arm); isolation probe
    agents.py                    # per-CLI command builders + output parsers
    runner.py                    # run_one, run_matrix (parallel, resumable, timeout)
    graders/
      __init__.py
      commands.py                # build/typecheck/lint/hidden tests/regressions
      audit.py                   # findings extraction + F1 vs known issues
      honesty.py                 # final claims vs grader evidence
      scope.py                   # diff outside allowed paths
      checklist.py               # hidden checklist (script items + judge items)
    capture.py                   # Playwright screenshots
    judge.py                     # blind pairwise + checklist judging via CLIs
    score.py                     # primary metric per category, win rule, bootstrap CIs
    report.py                    # HTML + markdown report
    spotcheck.py                 # local blind-pick page for the user
    cli.py                       # `bruhsbench` entrypoint
  tests/                         # pytest, mirrors modules; fixtures/ holds sample CLI outputs
  tasks/                         # seeded tasks (public)
    <task-id>/task.toml prompt.md setup.sh hidden/ known_issues.json checklist.json fixture/
  tasks-private/                 # real tasks (gitignored)
  tasks-heldout/                 # sealed seeded tasks (committed, runner refuses unless --heldout)
  results/                       # gitignored except results/published/
```

## Shared types (`bench/bruhsbench/types.py`, defined in Task 1)

```python
Arm = Literal["bare", "bruhs"]
Cli = Literal["claude", "codex", "grok"]
Category = Literal["feature", "debug", "audit", "ui", "copy", "pr-review", "ship"]

@dataclass(frozen=True)
class ModelSpec: cli: Cli; model: str; effort: str        # MODELS: tuple[ModelSpec, ...] constant
@dataclass(frozen=True)
class Task:
    id: str; category: Category; dir: Path
    repo: Path | None; base: str | None                  # real tasks: local repo + commit; seeded: dir/fixture
    prompt: str; setup: Path | None
    allowed_paths: tuple[str, ...]                        # globs for scope grader
    pages: tuple[str, ...]                                # URL paths to screenshot (ui/copy)
    dev_cmd: str | None; dev_port: int | None
    checks: dict[str, str]                                # name -> shell cmd (build, typecheck, lint, test)
    hidden_tests: Path | None; known_issues: Path | None; checklist: Path | None
    heldout: bool
@dataclass(frozen=True)
class RunSpec: task: Task; model: ModelSpec; arm: Arm; repeat: int  # run_id = f"{task.id}__{model.cli}__{arm}__r{repeat}"
@dataclass
class RunResult:
    run_id: str; status: Literal["ok", "timeout", "error", "setup_failed"]
    wall_s: float; turns: int | None; input_tokens: int | None; output_tokens: int | None; cost_usd: float | None
    final_message: str; diff_path: Path; transcript_path: Path
```

---

### Task 1: Package scaffold, types, task loader

**Files:**
- Create: `bench/pyproject.toml`, `bench/.gitignore`, `bench/bruhsbench/__init__.py`, `bench/bruhsbench/types.py`, `bench/bruhsbench/tasks.py`
- Test: `bench/tests/test_tasks.py`, `bench/tests/fixtures/tasks/sample-feature/{task.toml,prompt.md}`

**Interfaces:**
- Produces: the types above; `MODELS = (ModelSpec("claude","claude-opus-5-5","high"), ModelSpec("codex","gpt-6.1-sol","high"), ModelSpec("grok","grok-4.7","high"))`; `load_task(dir: Path) -> Task`; `load_tasks(root: Path, *, include_heldout: bool = False) -> list[Task]`.

task.toml shape:
```toml
id = "seed-feature-leaderboard"
category = "feature"
repo = "~/Documents/bryantleft/mints"   # omit for seeded; then fixture/ is used
base = "55ddb370"
allowed_paths = ["app/**", "components/**"]
pages = ["/grade"]
dev_cmd = "pnpm dev --port {port}"
dev_port = 3100
[checks]
build = "pnpm build"
test = "pnpm test"
```

- [ ] **Step 1: Write failing tests** — `test_load_task_reads_toml_and_prompt` (all fields populated; `repo` expanded; `prompt` == prompt.md text), `test_missing_prompt_raises` (`TaskError`), `test_load_tasks_excludes_heldout_by_default` (a task under `tasks-heldout/` only returned with `include_heldout=True`), `test_unknown_category_raises`.
- [ ] **Step 2: Run** `cd bench && uv run pytest tests/test_tasks.py -v` → FAIL (module missing).
- [ ] **Step 3: Implement** types and loader with `tomllib`. `.gitignore`: `results/*`, `!results/published/`, `tasks-private/`, `.venv/`.
- [ ] **Step 4: Run** → PASS.
- [ ] **Step 5: Commit** `feat(bench): scaffold bruhsbench package and task loader`

### Task 2: Workspace prep

**Files:**
- Create: `bench/bruhsbench/workspace.py`
- Test: `bench/tests/test_workspace.py`

**Interfaces:**
- Consumes: `Task`, `Arm`.
- Produces: `prepare_workspace(task: Task, arm: Arm, dest: Path) -> Path`; `strip_bruhs_blocks(text: str) -> str`; `insert_bruhs_blocks(root: Path) -> None`; `SetupFailed(Exception)`; `check_task_setup(task: Task, scratch: Path) -> bool` (runs setup once; used to exclude a task from *both* arms).

Behavior:
- Real task: `git clone --no-hardlinks --quiet <repo> dest` then `git -C dest checkout --detach <base>`; remove all remotes (no pushes possible). Seeded: copy `fixture/` and `git init` + initial commit.
- Both arms: `strip_bruhs_blocks` on `CLAUDE.md` and `AGENTS.md` (removes `<!-- bruhs:<kind>:begin … -->…<!-- bruhs:<kind>:end -->` for every kind, and a now-empty `## bruhs-managed` heading). Remove `.claude/bruhs.json` if present.
- bruhs arm only: `insert_bruhs_blocks` runs this repo's `scripts/detect_stack.py`, `scripts/derive_stack_rules.py`, then `scripts/sync_bruhs_block.py --kind state` and `--kind rules` against `dest`, with state JSON omitting `integrations.linear`.
- Commit the prepared state as `bench: base` and tag it `bench-base` so graders diff against it.
- Run `setup.sh` (cwd=dest, timeout 15 min); non-zero → `SetupFailed`.

- [ ] **Step 1: Write failing tests** — `test_strip_removes_all_kinds_and_empty_heading` (input with state+rules blocks + hand-written rules → only hand-written remain), `test_strip_noop_without_markers`, `test_bare_and_bruhs_differ_only_in_blocks` (prepare both arms from a tmp git repo; `diff -r` minus `.git` shows only CLAUDE.md/AGENTS.md), `test_remotes_removed`, `test_setup_failure_excludes_task` (setup.sh `exit 1` → `check_task_setup` returns False).
- [ ] **Step 2: Run** `uv run pytest tests/test_workspace.py -v` → FAIL.
- [ ] **Step 3: Implement.**
- [ ] **Step 4: Run** → PASS.
- [ ] **Step 5: Commit** `feat(bench): workspace prep with bruhs block strip/insert`

### Task 3: Isolated agent homes + isolation probe

**Files:**
- Create: `bench/bruhsbench/homes.py`
- Test: `bench/tests/test_homes.py`

**Interfaces:**
- Consumes: `Cli`, `Arm`.
- Produces: `build_home(cli: Cli, arm: Arm, run_dir: Path, bruhs_src: Path) -> dict[str, str]` (env vars to pass the CLI); `probe_isolation(cli: Cli, arm: Arm, env: dict[str,str]) -> ProbeResult(skills: set[str], mcps: set[str])`; `assert_isolated(result, arm)` raises `LeakError`.

Approach (verify each empirically in Step 3; if a mechanism fails, use the fallback and note it in the module docstring):
- All CLIs: `HOME=<run_dir>/home`, plus `XDG_CONFIG_HOME=<home>/.config`. Keep `PATH`, `LANG`, `TERM`.
- claude: auth via `CLAUDE_CODE_OAUTH_TOKEN` (from `claude setup-token`, stored once in `bench/.env`, gitignored) or `ANTHROPIC_API_KEY`. bruhs arm: `--plugin-dir <bruhs_src>` (pinned commit exported to `<run_dir>/bruhs` via `git archive`), `<home>/.claude/skills/expect` copied, `--mcp-config <home>/mcp.json --strict-mcp-config` with chrome-devtools (`npx -y chrome-devtools-mcp@latest --headless --isolated`). bare arm: `--strict-mcp-config` with empty config.
- codex: `CODEX_HOME=<home>/.codex`, copy `~/.codex/auth.json` only; bruhs arm puts bruhs + expect in `<home>/.agents/skills/` and chrome-devtools in `<home>/.codex/config.toml` `[mcp_servers.chrome-devtools]`.
- grok: copy `~/.grok/auth.json` into `<home>/.grok/`; bruhs arm puts bruhs + expect in `<home>/.grok/skills/` and chrome-devtools via `grok mcp add` run with the isolated HOME.
- Probe: ask the CLI headlessly "List the names of every skill and MCP server available to you as JSON {skills:[],mcps:[]}" (use each CLI's JSON-schema/structured mode where available) — bare must have no `bruhs`, `expect`, `superpowers`, or any MCP; bruhs must have `bruhs` and `expect` and `chrome-devtools`, and no `superpowers`/`impeccable`.

- [ ] **Step 1: Write failing unit tests** — `test_build_home_bare_has_no_skills_dir_content`, `test_build_home_bruhs_installs_bruhs_and_expect` (per cli, files present at expected paths), `test_only_auth_copied` (no other files from real `~/.codex` / `~/.grok`), `test_probe_detects_leaked_skill` (`assert_isolated(ProbeResult({"superpowers"}, set()), "bare")` raises `LeakError`).
- [ ] **Step 2: Run** `uv run pytest tests/test_homes.py -v` → FAIL.
- [ ] **Step 3: Implement**, then add a live test `test_live_isolation[cli-arm]` marked `@pytest.mark.live` that builds a real home and runs the probe for all 6 combinations.
- [ ] **Step 4: Run** `uv run pytest tests/test_homes.py -v` → PASS; `uv run pytest -m live tests/test_homes.py -v` → 6 PASS. Fix mechanisms until all six pass; do not proceed with any leak.
- [ ] **Step 5: Commit** `feat(bench): isolated agent homes with isolation probe`

### Task 4: Agent adapters

**Files:**
- Create: `bench/bruhsbench/agents.py`
- Test: `bench/tests/test_agents.py`, `bench/tests/fixtures/cli_output/{claude.json,codex.jsonl,grok.json}` (captured from real tiny runs)

**Interfaces:**
- Consumes: `ModelSpec`, env from `build_home`.
- Produces: `PREAMBLE: str`; `build_command(spec: ModelSpec, arm: Arm, prompt: str, workdir: Path, home: Path) -> list[str]`; `parse_output(cli: Cli, stdout: str) -> ParsedRun(final_message: str, turns: int|None, input_tokens: int|None, output_tokens: int|None, cost_usd: float|None)`; `is_auth_failure(cli: Cli, stdout: str, stderr: str, code: int) -> bool`.

Exact preamble (prepended to every prompt, both arms):
```
You are working unattended: no human will answer questions. Make reasonable decisions yourself instead of asking. Do not push, open PRs, or contact external services. When you believe the task is complete, stop and summarize what you did and how you verified it.

Task:
```

Commands:
- claude: `claude -p <prompt> --model claude-opus-5-5 --effort high --output-format json --dangerously-skip-permissions --strict-mcp-config --mcp-config <home>/mcp.json [--plugin-dir <bruhs>]`, cwd=workdir.
- codex: `codex exec --json -m gpt-6.1-sol -c model_reasoning_effort="high" --dangerously-bypass-approvals-and-sandbox --skip-git-repo-check -C <workdir> -o <run_dir>/final.txt <prompt>`.
- grok: `grok -p <prompt> -m grok-4.7 --reasoning-effort high --output-format json --always-approve --cwd <workdir> --disable-web-search`. Apply `--disable-web-search` (or equivalent) to all three if supported, else none — same for both arms.

- [ ] **Step 1: Capture fixtures** — run each CLI once on "reply with the word ok" with an isolated home; save stdout into `tests/fixtures/cli_output/`.
- [ ] **Step 2: Write failing tests** — `test_build_command_identical_across_arms_except_bruhs_flags` (diff of bare vs bruhs argv is only `--plugin-dir …` for claude and nothing for codex/grok), `test_preamble_prepended`, `test_parse_output_<cli>` (final_message == "ok"; tokens > 0 where the CLI reports them), `test_is_auth_failure_<cli>` (from a captured or hand-written auth error sample).
- [ ] **Step 3: Run** `uv run pytest tests/test_agents.py -v` → FAIL.
- [ ] **Step 4: Implement.** Cost: claude reports `total_cost_usd`; for codex/grok compute from tokens using a `PRICES` table in this module (fill from current published prices; leave `None` if unknown).
- [ ] **Step 5: Run** → PASS.
- [ ] **Step 6: Commit** `feat(bench): headless adapters for claude, codex, grok`

### Task 5: Runner

**Files:**
- Create: `bench/bruhsbench/runner.py`
- Test: `bench/tests/test_runner.py` (uses a fake agent: a shell script installed as the CLI via a `command_override` hook)

**Interfaces:**
- Consumes: Tasks 1–4.
- Produces: `run_one(spec: RunSpec, out_root: Path, *, timeout_s: int = 2700) -> RunResult` writing `out_root/<run_id>/{result.json, transcript.*, diff.patch, final.txt, workspace/}`; `run_matrix(tasks, models, arms, repeats: int, out_root: Path, *, parallel: int = 6) -> list[RunResult]`; `AuthAbort(Exception)`.

Behavior: tasks failing `check_task_setup` are excluded for all arms and logged to `out_root/excluded.json`. Runs execute in a `ThreadPoolExecutor`; each run builds its own home and workspace. On timeout: kill the process group, still write diff + `status="timeout"`. Diff = `git -C workspace add -A && git diff --cached bench-base` (tag `bench-base` set in Task 2). Matrix order is shuffled with a fixed seed so arms interleave in time (rate limits / provider drift hit both arms equally).

- [ ] **Step 1: Write failing tests** — `test_run_one_writes_artifacts`, `test_timeout_recorded` (fake agent sleeps; timeout_s=2 → status timeout, diff still written), `test_resume_skips_completed`, `test_auth_failure_aborts_matrix` (fake agent prints the auth error sample → `AuthAbort`, no further runs started), `test_setup_failed_task_excluded_both_arms`, `test_matrix_interleaves_arms`.
- [ ] **Step 2: Run** `uv run pytest tests/test_runner.py -v` → FAIL.
- [ ] **Step 3: Implement.**
- [ ] **Step 4: Run** → PASS.
- [ ] **Step 5: Commit** `feat(bench): parallel resumable runner with timeouts`

### Task 6: Objective graders

**Files:**
- Create: `bench/bruhsbench/graders/{__init__,commands,scope,audit,honesty}.py`
- Test: `bench/tests/graders/test_{commands,scope,audit,honesty}.py`

**Interfaces:**
- Consumes: `Task`, run dir from Task 5.
- Produces: each grader `grade(task: Task, run_dir: Path) -> dict` written into `run_dir/grades/<grader>.json`; `grade_all(task, run_dir) -> dict` merging them.
  - `commands`: `{checks: {name: bool}, hidden_pass: int, hidden_total: int, regressions: list[str]}`. Hidden tests are copied in from `task.hidden_tests` *after* the agent finished (never visible during the run). Regressions = tests passing at base that fail after.
  - `scope`: `{files_outside: list[str], lines_outside: int}` from diff vs `allowed_paths`.
  - `audit`: agent's findings are extracted from `final.txt` + any files it wrote (e.g. `AUDIT.md`) by a judge call (`judge.extract_findings`, Task 8) into `[{file, line, summary, severity}]`; matched to `known_issues.json` entries (`{id, file, lines:[a,b], severity, decoy: bool}`) by file + line overlap, ambiguous matches resolved by judge. Output `{tp, fp, fn, decoys_flagged, precision, recall, f1, severity_accuracy}`.
  - `honesty`: claims extracted from `final.txt` by judge (`judge.extract_claims` → `[{claim, kind: "done"|"verified"|"fixed"|"tests_pass"}]`), each checked against the other graders' evidence; `{claims: int, false_claims: int, honest_done: bool}` where `honest_done` = no false claims.
- Note: audit and honesty depend on Task 8's extraction functions; implement those graders with the judge call injected as a parameter (`extract: Callable`) so tests use a stub.

- [ ] **Step 1: Write failing tests** — `test_hidden_tests_not_present_during_run` (assert hidden dir absent from workspace before grading), `test_regression_detected`, `test_scope_counts_lines_outside_allowed`, `test_audit_f1_with_decoy` (3 known + 1 decoy; stub findings hit 2 known + decoy → precision 2/3, recall 2/3, decoys_flagged 1), `test_honest_done_false_when_claims_tests_pass_but_failing`.
- [ ] **Step 2: Run** `uv run pytest tests/graders -v` → FAIL.
- [ ] **Step 3: Implement.**
- [ ] **Step 4: Run** → PASS.
- [ ] **Step 5: Commit** `feat(bench): objective graders`

### Task 7: Screenshot capture

**Files:**
- Create: `bench/bruhsbench/capture.py`
- Test: `bench/tests/test_capture.py` (serves a static HTML fixture with `python -m http.server`)

**Interfaces:**
- Produces: `capture(task: Task, workspace: Path, out: Path) -> list[Path]` — starts `task.dev_cmd` on `task.dev_port`, waits for HTTP 200 (timeout 180 s), screenshots each of `task.pages` at 4 variants `{desktop 1440×900, mobile 390×844} × {light, dark}` (`color_scheme` emulation), full-page, named `<page-slug>__<viewport>__<scheme>.png`; kills the dev server. Captures the base commit once per task as `before/`.

- [ ] **Step 1: Write failing tests** — `test_capture_produces_four_variants_per_page`, `test_dev_server_killed_after_capture`, `test_server_never_ready_returns_empty_and_logs` (no exception; grader records `capture_failed`).
- [ ] **Step 2: Run** → FAIL. **Step 3: Implement** with `playwright.sync_api`; `uv run playwright install chromium` in README setup. **Step 4: Run** → PASS.
- [ ] **Step 5: Commit** `feat(bench): playwright screenshot capture`

### Task 8: Judging

**Files:**
- Create: `bench/bruhsbench/judge.py`, `bench/bruhsbench/graders/checklist.py`
- Test: `bench/tests/test_judge.py`, `bench/tests/graders/test_checklist.py`

**Interfaces:**
- Consumes: `agents.build_command`-style headless calls (judges run with a bare isolated home, effort high, read-only, no tools needed beyond reading attached files).
- Produces:
  - `judge_call(judge: ModelSpec, prompt: str, images: list[Path], schema: dict) -> dict` — structured JSON out (claude `--json-schema` / codex `--output-schema` / grok `--json-schema`; validate, retry once on invalid).
  - `judges_for(run_cli: Cli) -> list[ModelSpec]` — the two other families.
  - `pairwise(task, a_dir, b_dir, judge) -> {"winner": "A"|"B"|"tie", "reasons": str}` — arms hidden; A/B order randomized with seed `hash(task.id, repeat, judge)` and the mapping stored separately in `pairs_key.json`; inputs: the prompt, screenshots, diff (truncated to 60k chars), final message with arm-revealing strings redacted (`bruhs`, `/cook`, `/slop`, `/expect`, marker comments).
  - Rubric text in `PAIRWISE_RUBRIC`: looks intentional vs AI-generated; spacing/alignment/detail; copy clarity and brevity; matches the request; nothing broken. Judges must decide by these, not by process narration.
  - `extract_findings(final_text, files) -> list[dict]`, `extract_claims(final_text) -> list[dict]` (used by Task 6).
  - `checklist.grade(task, run_dir, judges) -> {items: [{id, hit: bool, by: "script"|"judge"}], score: float}`; checklist.json items: `{id, text, check: "script"|"judge", script?: str}`. Judge items: majority of the two judges; tie → miss.

- [ ] **Step 1: Write failing tests** (judge_call stubbed) — `test_judges_exclude_own_family`, `test_pairwise_hides_arm` (prompt sent to judge contains neither "bruhs" nor arm names), `test_pairwise_order_randomized_and_recoverable`, `test_invalid_json_retried_once`, `test_checklist_script_and_judge_items`.
- [ ] **Step 2: Run** → FAIL. **Step 3: Implement.** **Step 4: Run** → PASS.
- [ ] **Step 5: Live smoke** `uv run pytest -m live tests/test_judge.py -v` — one real call per judge CLI returns schema-valid JSON.
- [ ] **Step 6: Commit** `feat(bench): blind pairwise and checklist judging`

### Task 9: Scoring, report, spot-check, CLI

**Files:**
- Create: `bench/bruhsbench/{score,report,spotcheck,cli}.py`, `bench/bruhsbench/templates/report.html.j2`
- Test: `bench/tests/test_score.py`, `bench/tests/test_report.py`, `bench/tests/test_spotcheck.py`

**Interfaces:**
- Produces:
  - `primary_metric(task: Task, grades: dict) -> float` per the Global Constraints table.
  - `decide(task, bare: list[float], bruhs: list[float], prefs: list[str] | None) -> Literal["win","loss","tie"]` with the frozen margins.
  - `summarize(results_root) -> Summary` — per model: win/tie/loss counts, win-rate with 95% bootstrap CI (10k resamples over tasks), per-category deltas, cost/time/turns/scope means per arm; also the seeded-only subset.
  - `render(summary, out_dir, *, private: bool)` → `report.html` (self-contained, inline CSS/PNG) + `report.md`. `private=False` omits private-task screenshots, prompts, and file paths (only task category + scores). Chart per model built per the `dataviz` skill.
  - `spotcheck.serve(results_root, n=20, seed)` — local page showing random UI/copy pairs blind; records user picks to `spotcheck.json`; `agreement(results_root) -> float`; if < 0.75 the report marks UI/copy as user-picks-only.
  - CLI: `bruhsbench probe | run [--pilot] [--tasks …] [--models …] [--repeats N] [--heldout] | grade | capture | judge | spotcheck | report [--public]`. `--pilot` = tasks listed in `bench/pilot.toml`, 1 repeat.

- [ ] **Step 1: Write failing tests** — `test_decide_margins` (one case per category at, just under, just over the margin), `test_cost_does_not_affect_decision`, `test_bootstrap_ci_contains_point_estimate`, `test_public_report_has_no_private_paths` (render with a private task; output contains no `tasks-private`, no repo path, no prompt text), `test_spotcheck_agreement`.
- [ ] **Step 2: Run** → FAIL. **Step 3: Implement.** **Step 4: Run** → PASS.
- [ ] **Step 5: Commit** `feat(bench): scoring, report, spot-check, and CLI`

### Task 10: Seeded tasks (8, incl. 2 held-out)

**Files:**
- Create: `bench/tasks/seed-audit-ts/`, `seed-audit-rust/`, `seed-feature-hidden-tests/`, `seed-pr-review/`, `seed-debug-not-really-fixed/`, `seed-ship-messy-diff/`, `seed-copy-jargon/`; held-out in `bench/tasks-heldout/`: `seed-heldout-feature/`, `seed-heldout-ui/`.

(Moving 2 seeded tasks to held-out keeps the 6 public seeded categories from the spec intact.)

Each task: `task.toml`, `prompt.md` (written like a real user message — short, informal, no hints about method), `fixture/` (small runnable repo, deps pinned + lockfile), `setup.sh`, and its graders' inputs:
- `seed-audit-ts` / `seed-audit-rust`: ~15 planted issues each across security, correctness, perf, types, error handling, at mixed severity + 4 decoys; `known_issues.json`. Prompt: "audit this repo for anything that's wrong or sloppy, write findings to AUDIT.md".
- `seed-feature-hidden-tests`: Next.js app; spec in prompt; `hidden/` vitest suite (≥ 12 tests incl. edge cases the prompt implies but doesn't spell out) + existing suite.
- `seed-pr-review`: repo on a feature branch + `REVIEW.md` with 5 comments (4 valid, 1 wrong — would introduce a bug); checklist: each valid fixed (hidden test per fix), wrong one declined with reason, checks green.
- `seed-debug-not-really-fixed`: bug whose naive fix passes the existing unit test but still breaks rendering at 390px; hidden Playwright test is the arbiter; honesty grader decisive.
- `seed-ship-messy-diff`: staged diff mixing a feature, an unrelated formatting change, and a stray debug log; checklist: conventional commit, debug log not committed, unrelated change separate or excluded, branch name descriptive, PR body draft accurate (judge).
- `seed-copy-jargon`: marketing/settings page full of jargon and filler; checklist: word count down ≥ 30% on targeted sections, banned patterns gone (emoji, "seamless", "leverage", "unlock", em-dash bullet stacks), meaning preserved (judge); pairwise judged.

- [ ] **Step 1:** For each task, write graders' inputs first (known_issues / hidden tests / checklist), then the fixture.
- [ ] **Step 2: Validate each fixture** — `bruhsbench grade` against (a) the untouched fixture → low score, (b) a hand-written reference solution kept in `bench/tests/reference/<task>/` (not visible to agents) → full marks. Run: `uv run pytest tests/test_seeded_tasks.py -v` (parametrized over tasks) → PASS.
- [ ] **Step 3: Commit** `feat(bench): seeded tasks with graders and reference solutions` (one commit per task is fine).

### Task 11: Real tasks from history (12, incl. 2 held-out)

**Files:**
- Create (gitignored): `bench/tasks-private/<id>/` for the 10 spec candidates (mints ×7, ogling, bruhs-ai, degrees-of-freedom) + 2 more from `/tmp/bench_out/` candidates (e.g. ogling MangaDex import with a mocked API, bruhs-ai top bar) marked `heldout = true`.
- Copy `/tmp/bench_out/{all.jsonl,complaints.txt}` → `bench/tasks-private/_mining/` (it's in /tmp and will vanish).

Per task:
- `prompt.md` = the user's original first message verbatim (typos kept), minus unreproducible private context.
- `checklist.json` built from the user's follow-up complaints and later fix commits for that thread (source noted per item). Written now, before any run.
- `setup.sh` installs deps at that commit; `checks` from the repo's package.json/Cargo scripts; `pages` for UI tasks; mock external APIs where needed (MangaDex).
- degrees-of-freedom base: find by date (`git log --before=<session date> -1`) from the session timestamp.

- [ ] **Step 1:** For each candidate, run `check_task_setup`; drop any that can't install/build offline, and replace from the candidate list. Record drops in `bench/tasks-private/_dropped.md` with the reason.
- [ ] **Step 2:** Write prompt + checklist for each surviving task.
- [ ] **Step 3: Validate** — `bruhsbench capture` on the base commit for each UI task produces screenshots; `bruhsbench grade` on base runs without errors.
- [ ] **Step 4: User checkpoint** — hand the user the 12 checklists (one markdown digest) to review once. Freeze after their OK: write `bench/tasks-private/_frozen.sha256` (hash of all task dirs); the runner refuses to start a non-pilot matrix if hashes changed.
- [ ] **Step 5: Commit** only the frozen-hash check code (task dirs are gitignored).

### Task 12: Pilot

- [ ] **Step 1:** Write `bench/pilot.toml`: `seed-audit-ts`, `seed-debug-not-really-fixed`, one real UI+copy task (mints /grade). These become "seen".
- [ ] **Step 2:** `uv run bruhsbench probe` → all 6 cli×arm combos isolated.
- [ ] **Step 3:** `uv run bruhsbench run --pilot` then `grade`, `capture`, `judge`, `report`. Expected: 18 runs, zero `error` status, every grader produced output, report renders.
- [ ] **Step 4:** Read 3–4 transcripts per arm by hand: did bruhs actually activate in the bruhs arm (look for command doc reads / bruhs workflow) and never in bare? If bruhs didn't activate for some CLI, fix the install (Task 3), not the prompt.
- [ ] **Step 5:** Fix harness bugs found; rerun pilot until clean. No changes to rubrics, margins, checklists, or prompts of non-pilot tasks.
- [ ] **Step 6: Commit** `chore(bench): pilot fixes`

### Task 13: Full run and publish

- [ ] **Step 1:** `uv run bruhsbench run --repeats 3` (all non-held-out tasks, 3 models, 2 arms). Expected: ~(14 + 10 − pilot overlap) tasks × 18 runs; resumable if interrupted.
- [ ] **Step 2:** `grade`, `capture`, `judge`.
- [ ] **Step 3:** `uv run bruhsbench spotcheck` — user blind-picks 20 pairs; compute agreement; apply the 75% rule.
- [ ] **Step 4:** `uv run bruhsbench report` (private, full) and `report --public` → `bench/results/published/<date>/`. Verify public report with `test_public_report_has_no_private_paths` logic run against the real output.
- [ ] **Step 5:** Add a "Does it actually help?" section to repo `README.md`: headline chart per model (win-rate + CI), one line on method, cost delta, link to `bench/README.md` and the published report. Every task's result included, losses too.
- [ ] **Step 6:** Ask the user which (if any) private-repo screenshots may be published before adding them. Then commit `docs: publish bruhs benchmark results`.
