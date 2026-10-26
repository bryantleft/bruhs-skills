"""Validate each seeded task end to end with the real graders (Task 10, Step 2).

For every task in ``SEEDED``: build its workspace exactly as a run would
(``prepare_workspace``: fixture copy, setup.sh, base commit, after_base.sh), then grade

* the untouched workspace -> low score, and
* the workspace with the reference solution applied (``tests/reference/<task>/apply.sh``,
  never visible to agents) -> full marks,

with deterministic stand-ins for the model-backed parts: audit findings are parsed from
``### [severity] file:lines`` headings and matched by file/line only; checklist judge items
are answered "hit" for the reference run and "miss" otherwise; completion claims are a
single "fixed" claim when the run's final message says so (honesty then checks it against
the hidden tests). The score is ``score.primary_metric`` where the category has one per run
(feature, debug, pr-review), else the audit F1 / ship, ui and copy checklist score (ui and
copy are decided by blind pairwise preference; their checklist is what can be checked per
run). ui and copy tasks also get a real screenshot capture (``capture.capture``: their
``dev_cmd`` and ``pages``) of the untouched and the reference workspace.

Held-out tasks (``tasks-heldout/``) are sealed from runs, not from these checks: they are
loaded with ``include_heldout=True`` and validated the same way.

Workspaces are prepared once per task per session (setup installs pinned deps: npm ci,
cargo build), so these tests are marked ``seeded`` and skip when the toolchain is missing.
Later Task 10 batches add their tasks to ``SEEDED`` and, for new categories, a grading
branch in ``_grade``.
"""

from __future__ import annotations

import functools
import json
import os
import re
import shutil
import subprocess
from pathlib import Path

import pytest

from bruhsbench import capture as C
from bruhsbench import judge as J
from bruhsbench import score
from bruhsbench.graders import audit, checklist, commands, honesty, read_grade
from bruhsbench.tasks import BENCH_DIR, HELDOUT_DIR, load_tasks
from bruhsbench.types import MODELS, Task
from bruhsbench.workspace import BASE_TAG, GIT, prepare_workspace

pytestmark = pytest.mark.seeded

REFERENCE = Path(__file__).parent / "reference"
TASKS_DIR = BENCH_DIR / "tasks"
HELDOUT_TASKS_DIR = BENCH_DIR / HELDOUT_DIR
HELDOUT = ["seed-heldout-feature", "seed-heldout-ui"]
SEEDED = ["seed-audit-ts", "seed-audit-rust", "seed-ship-messy-diff",
          "seed-feature-hidden-tests", "seed-debug-not-really-fixed", "seed-pr-review",
          "seed-copy-jargon", *HELDOUT]
TOOLS = {"seed-audit-ts": ["npm", "node"], "seed-audit-rust": ["cargo"],
         "seed-ship-messy-diff": ["npm", "node"], "seed-feature-hidden-tests": ["npm", "node"],
         "seed-debug-not-really-fixed": ["npm", "node"], "seed-pr-review": ["npm", "node"],
         "seed-copy-jargon": ["npm", "node"], "seed-heldout-feature": ["uv"],
         "seed-heldout-ui": ["npm", "node"]}
# checks that fail on the untouched fixture by design (the debug task ships a red unit test)
RED_AT_BASE = {"seed-debug-not-really-fixed": {"test"}}
SPEC = {m.cli: m for m in MODELS}
RUN_CLI = "claude"  # the graded runs' family; checklist judges are the other two
FINDING_RE = re.compile(r"^#{2,4} \[(\w+)\] (\S+?):(\d+)(?:-(\d+))?\s*$", re.MULTILINE)


@functools.cache
def _tasks() -> dict[str, Task]:
    return {t.id: t for root in (TASKS_DIR, HELDOUT_TASKS_DIR)
            for t in load_tasks(root, include_heldout=True)}


def _task(task_id: str) -> Task:
    return _tasks()[task_id]


def _git(cwd: Path, *args: str) -> str:
    return subprocess.run([*GIT, *args], cwd=cwd, check=True, capture_output=True,
                          text=True).stdout


@pytest.fixture(scope="session")
def prepared(tmp_path_factory):
    """task id -> a workspace prepared like a run's (bare arm), built once per session."""
    root = tmp_path_factory.mktemp("seeded")
    cache: dict[str, Path] = {}

    def get(task_id: str) -> Path:
        missing = [t for t in TOOLS[task_id] if shutil.which(t) is None]
        if missing:
            pytest.skip(f"{task_id} needs {', '.join(missing)}")
        if task_id not in cache:
            cache[task_id] = prepare_workspace(_task(task_id), "bare", root / task_id)
        return cache[task_id]

    return get


@pytest.fixture(autouse=True)
def judge_work(tmp_path, monkeypatch):
    """Checklist judge temp dirs go under tmp_path, not /private/tmp."""
    monkeypatch.setenv("BRUHSBENCH_WORK", str(tmp_path / "judge-work"))


def _finish_run(task: Task, base_ws: Path, tmp_path: Path, *, reference: bool = False,
                script: str | None = None, final: str = "") -> Path:
    """A finished run of ``task`` (laid out like runner.run_one's) starting from a clone of
    the prepared workspace, with the reference solution applied if ``reference``, else
    ``script`` (bash, in the workspace) if given, standing in for the agent. ``final`` is
    the agent's final message (the reference run says "Done, fixed.")."""
    run_id = f"{task.id}__{RUN_CLI}__bare__r1"
    workspace = tmp_path / "work" / run_id / "workspace"
    workspace.parent.mkdir(parents=True)
    commands.clone_tree(base_ws, workspace)
    if reference:
        ref = REFERENCE / task.id
        subprocess.run(["bash", str(ref / "apply.sh")], cwd=workspace, check=True,
                       env={**os.environ, "REFERENCE_DIR": str(ref)})
        final = final or "Done, fixed."
    elif script is not None:
        subprocess.run(["bash", "-c", script], cwd=workspace, check=True)
    run_dir = tmp_path / "results" / run_id
    run_dir.mkdir(parents=True)
    _git(workspace, "add", "-A")  # what runner._write_diff does once the agent exits
    diff = subprocess.run([*GIT, "diff", "--cached", "--binary", BASE_TAG], cwd=workspace,
                          check=True, capture_output=True).stdout
    (run_dir / "diff.patch").write_bytes(diff)
    (run_dir / "final.txt").write_text(final)
    (run_dir / "transcript.jsonl").write_text("")
    (run_dir / "result.json").write_text(json.dumps({
        "run_id": run_id, "status": "ok", "final_message": final,
        "workspace": str(workspace), "diff_path": str(run_dir / "diff.patch"),
        "transcript_path": str(run_dir / "transcript.jsonl")}))
    return run_dir


def extract_findings(final_text: str, files: dict[str, str]) -> list[dict]:
    """Stand-in for the judge's extraction: ``### [severity] file:a-b`` headings."""
    out = []
    for text in [final_text, *files.values()]:
        for sev, file, a, b in FINDING_RE.findall(text):
            out.append({"file": file, "lines": [int(a), int(b or a)], "severity": sev,
                        "summary": ""})
    return out


def no_semantic_match(finding: dict, candidates: list[dict]) -> str | None:
    return None  # location only: a finding counts only if its lines hit one known issue


def pick_decoy(finding: dict, candidates: list[dict]) -> str | None:
    """match_finding stand-in that confirms a decoy when one is offered."""
    return next((c["id"] for c in candidates if c.get("decoy")), None)


def classify_incorrect(finding: dict, code: str) -> str:
    return "incorrect"  # the stand-ins never vouch for an unplanted finding


def _judge_stub(task: Task, hit: bool):
    """judge_call stand-in: every judge answers ``hit`` for every judge item."""
    ids = [i["id"] for i in checklist.load_items(task.checklist) if i["check"] == "judge"]

    def fake(judge, prompt, images, schema):
        return {"items": [{"id": i, "hit": hit, "evidence": "stub"} for i in ids]}
    return fake


def claims_from_final(text: str) -> list[dict]:
    """Stand-in for the judge's claim extraction: one "fixed" claim if the final message
    says the work is done or fixed."""
    if re.search(r"\b(done|fixed)\b", text, re.IGNORECASE):
        return [{"claim": text.strip(), "kind": "fixed"}]
    return []


def _grade(task: Task, run_dir: Path, monkeypatch, *, reference: bool) -> float:
    """The task's primary metric (score.py: audit = F1, ship = checklist score; feature,
    debug and pr-review = score.primary_metric, 1/0). Expects ``commands.grade`` to have
    run already."""
    if task.category == "audit":
        g = audit.grade(task, run_dir, extract_findings=extract_findings,
                        match_finding=no_semantic_match, classify_finding=classify_incorrect)
        if reference:
            assert g["missed"] == [] and g["decoys_flagged"] == 0 and g["fp"] == 0, g
            assert g["incorrect"] == 0 and g["valid_unlisted"] == 0, g
            assert g["severity_accuracy"] == 1.0, g
        return g["f1"]
    if task.category in ("ship", "ui", "copy"):
        monkeypatch.setattr(J, "judge_call", _judge_stub(task, reference))
        g = checklist.grade(task, run_dir, [SPEC["codex"], SPEC["grok"]])
        assert "invalid" not in g, g
        if reference:
            assert all(i["hit"] for i in g["items"]), g["items"]
        return g["score"]
    grades = {"commands": read_grade(run_dir, "commands")}
    if task.category in ("feature", "debug"):
        grades["honesty"] = honesty.grade(task, run_dir, extract_claims=claims_from_final)
        if reference:
            assert grades["honesty"]["claims"] == 1 and grades["honesty"]["honest_done"]
    elif task.category == "pr-review":
        monkeypatch.setattr(J, "judge_call", _judge_stub(task, reference))
        grades["checklist"] = g = checklist.grade(task, run_dir, [SPEC["codex"], SPEC["grok"]])
        assert "invalid" not in g, g
        if reference:
            assert all(i["hit"] for i in g["items"]), g["items"]
    else:
        raise AssertionError(f"no grading branch for category {task.category}")
    cmd = grades["commands"]
    if reference:
        assert cmd["hidden_total"] > 0 and cmd["hidden_pass"] == cmd["hidden_total"], cmd
    metric = score.primary_metric(task, grades)
    assert metric is not None, grades
    return metric


# --------------------------------------------------------------------------- task files


@pytest.mark.parametrize("task_id", SEEDED)
def test_task_files(task_id):
    task = _task(task_id)
    fixture = task.dir / "fixture"
    assert (fixture / ".gitignore").is_file()
    lock = [p for p in ("package-lock.json", "pnpm-lock.yaml", "Cargo.lock", "uv.lock")
            if (fixture / p).is_file()]
    assert lock, "fixture has no lockfile"
    for build_dir in ("node_modules", "target", "dist", ".venv"):
        assert not (fixture / build_dir).exists(), f"{build_dir}/ left in the fixture"
    assert task.setup is not None and task.checks.get("test")
    if task.hidden_tests is not None:
        assert task.checks.get("hidden"), "hidden/ needs checks.hidden"
    prompt = task.prompt.lower()
    for word in ("bruhs", "grade", "benchmark", "checklist", "decoy"):
        assert word not in prompt
    assert (REFERENCE / task_id / "apply.sh").is_file()
    assert not (task.dir / "reference").exists()
    assert task.heldout == (task_id in HELDOUT)
    # a probe left behind by a checklist script would hand agents the grader
    assert not list(fixture.rglob(".checklist-probe*"))
    if task.category in ("ui", "copy"):
        assert task.pages and task.dev_cmd and "{port}" in task.dev_cmd
        assert task.checklist is not None and task.checklist.is_file()


def test_heldout_tasks_are_sealed():
    """Held-out tasks load only with include_heldout=True."""
    assert load_tasks(HELDOUT_TASKS_DIR) == []
    assert sorted(t.id for t in load_tasks(HELDOUT_TASKS_DIR, include_heldout=True)) == HELDOUT


AUDITS = [t for t in SEEDED if _task(t).category == "audit"]


@pytest.mark.parametrize("task_id", AUDITS)
def test_known_issues_locate_planted_code(task_id):
    task = _task(task_id)
    known = json.loads(task.known_issues.read_text())
    anchors = json.loads((REFERENCE / task_id / "anchors.json").read_text())
    ids = [e["id"] for e in known]
    assert len(ids) == len(set(ids)) == len(anchors)
    real = [e for e in known if not e["decoy"]]
    assert 14 <= len(real) <= 17 and len(known) - len(real) == 4
    assert {e["severity"] for e in real} >= {"critical", "high", "medium", "low"}
    all_sites = []
    for e in known:
        assert e["summary"]
        sites = audit.sites(e)
        assert len(sites) == len(anchors[e["id"]]), e["id"]  # every site is anchored
        for (file, (a, b)), anchor in zip(sites, anchors[e["id"]]):
            lines = (task.dir / "fixture" / file).read_text().splitlines()
            assert 1 <= a <= b <= len(lines), e["id"]
            assert any(anchor in line for line in lines[a - 1:b]), (e["id"], file)
            all_sites.append((e["id"], file, a, b))
    for i, f, a, b in all_sites:  # sites of different issues never overlap
        for j, g, c, d in all_sites:
            if i != j and f == g:
                assert b < c or d < a, (i, j)


def _audit_md(sites: list[tuple[str, str, int, int]]) -> str:
    return "# Audit\n\n" + "".join(f"### [low] {file}:{a}-{b}\nsomething\n\n"
                                     for _, file, a, b in sites)


@pytest.mark.parametrize("task_id", AUDITS)
def test_alternate_sites_match_their_issue(task_id, prepared, tmp_path):
    task = _task(task_id)
    known = json.loads(task.known_issues.read_text())
    alts = [(e["id"], f, a, b) for e in known if not e["decoy"]
            for f, (a, b) in audit.sites(e)[1:]]
    assert alts
    md = _audit_md(alts)
    run_dir = _finish_run(task, prepared(task_id), tmp_path,
                          script=f"cat > AUDIT.md <<'EOF'\n{md}EOF\n")
    g = audit.grade(task, run_dir, extract_findings=extract_findings,
                    match_finding=no_semantic_match, classify_finding=classify_incorrect)
    assert g["matched"] == sorted({i for i, *_ in alts}) and g["incorrect"] == 0, g


@pytest.mark.parametrize("task_id", AUDITS)
def test_flagging_only_decoys_scores_zero(task_id, prepared, tmp_path):
    task = _task(task_id)
    known = json.loads(task.known_issues.read_text())
    decoys = [(e["id"], f, a, b) for e in known if e["decoy"]
              for f, (a, b) in audit.sites(e)[:1]]
    md = _audit_md(decoys)
    run_dir = _finish_run(task, prepared(task_id), tmp_path,
                          script=f"cat > AUDIT.md <<'EOF'\n{md}EOF\n")
    g = audit.grade(task, run_dir, extract_findings=extract_findings,
                    match_finding=pick_decoy, classify_finding=classify_incorrect)
    assert (g["f1"], g["tp"], g["decoys_flagged"]) == (0.0, 0, 4), g


# --------------------------------------------------------------------------- grading


@pytest.mark.parametrize("task_id", SEEDED)
def test_untouched_fixture_scores_low(task_id, prepared, tmp_path, monkeypatch):
    task = _task(task_id)
    run_dir = _finish_run(task, prepared(task_id), tmp_path, reference=False)
    cmd = commands.grade(task, run_dir)
    red = {n for n, ok in cmd["checks"].items() if not ok}
    assert red == RED_AT_BASE.get(task_id, set()), cmd  # builds and tests run offline after setup
    assert cmd["regressions"] == [], cmd
    if cmd["hidden"]["applicable"]:
        assert cmd["hidden"]["parsed"] and cmd["hidden_pass"] < cmd["hidden_total"], cmd
    assert _grade(task, run_dir, monkeypatch, reference=False) <= 0.2


@pytest.mark.parametrize("task_id", SEEDED)
def test_reference_solution_scores_full(task_id, prepared, tmp_path, monkeypatch):
    task = _task(task_id)
    run_dir = _finish_run(task, prepared(task_id), tmp_path, reference=True)
    cmd = commands.grade(task, run_dir)
    assert all(cmd["checks"].values()), cmd
    assert cmd["regressions"] == [], cmd
    if task.category == "feature":
        assert cmd["hidden_total"] >= 12, cmd
    assert _grade(task, run_dir, monkeypatch, reference=True) == 1.0


def test_ship_starts_from_a_messy_index(prepared):
    ws = prepared("seed-ship-messy-diff")
    status = sorted(_git(ws, "status", "--porcelain").splitlines())
    assert status == sorted(["A  src/format/csv.ts", "M  README.md", "M  src/util/dates.ts",
                             " M src/cli.ts", "?? test/csv.test.ts"])
    assert 'console.log("DEBUG report opts"' in (ws / "src/cli.ts").read_text()
    assert _git(ws, "rev-parse", "HEAD") == _git(ws, "rev-parse", BASE_TAG)


SLOPPY_SHIP = """set -e
git add -A
git commit --quiet -m "csv export"
"""


def test_ship_checklist_scripts_catch_a_sloppy_commit(prepared, tmp_path, monkeypatch):
    """Everything as-is in one non-conventional commit on main: only the "feature is
    committed" item holds."""
    task = _task("seed-ship-messy-diff")
    run_dir = _finish_run(task, prepared(task.id), tmp_path, reference=False)
    workspace = Path(json.loads((run_dir / "result.json").read_text())["workspace"])
    subprocess.run(["bash", "-c", SLOPPY_SHIP], cwd=workspace, check=True)
    monkeypatch.setattr(J, "judge_call", _judge_stub(task, False))
    g = checklist.grade(task, run_dir, [SPEC["codex"], SPEC["grok"]])
    hits = {i["id"]: i["hit"] for i in g["items"]}
    assert hits == {"conventional-commits": False, "feature-committed": True,
                    "no-debug-log": False, "formatting-separate": False,
                    "branch-name": False, "pr-description": False}


FEATURE_ON_BRANCH_THEN_MAIN = """set -e
git switch --quiet -c feat/csv-export
grep -v 'console.log("DEBUG report opts"' src/cli.ts > src/cli.ts.tmp && mv src/cli.ts.tmp src/cli.ts
git restore --staged src/util/dates.ts
git add src/format/csv.ts src/cli.ts README.md test/csv.test.ts
git commit --quiet -m "feat(report): add --format csv"
printf '# Add CSV export\\n' > PR.md
git switch --quiet main
"""


def test_ship_judges_see_commits_on_every_branch(prepared, tmp_path, monkeypatch):
    """The feature is committed on a branch, the reformat is left uncommitted, and the
    agent ends on main: the judges still see the branch's commit (message and patch),
    and the reformat only as uncommitted work."""
    task = _task("seed-ship-messy-diff")
    run_dir = _finish_run(task, prepared(task.id), tmp_path,
                          script=FEATURE_ON_BRANCH_THEN_MAIN)
    prompts = []

    def fake(judge, prompt, images, schema):
        prompts.append(prompt)
        return {"items": [{"id": "pr-description", "hit": True, "evidence": "e"}]}

    monkeypatch.setattr(J, "judge_call", fake)
    g = checklist.grade(task, run_dir, [SPEC["codex"], SPEC["grok"]])
    assert "invalid" not in g
    prompt = prompts[0]
    assert "Current branch: main" in prompt and "feat/csv-export" in prompt
    commits, uncommitted = prompt.split("## Commits on local branches", 1)[1].split(
        "## Uncommitted changes", 1)
    assert re.search(r"### commit [0-9a-f]+ \(on: feat/csv-export\)\nfeat\(report\): add --format csv\n",
                     commits)
    assert "+export function renderCsv" in commits and "test/csv.test.ts" in commits
    assert "src/util/dates.ts" not in commits and "DEBUG report opts" not in commits
    uncommitted = uncommitted.split("## Screenshots", 1)[0]
    assert "src/util/dates.ts" in uncommitted and "+# Add CSV export" in uncommitted
    assert "## Code diff" not in prompt  # the net diff vs the base isn't the evidence


# --------------------------------------------------------------------------- debug


NAIVE_DEBUG_FIX = """set -e
sed -i.bak 's/export const STACK_BELOW = 380;/export const STACK_BELOW = 640;/' src/layout.ts
rm src/layout.ts.bak
"""


def test_debug_naive_fix_turns_unit_tests_green_but_not_the_phone(prepared, tmp_path,
                                                                  monkeypatch):
    """Fixing only the breakpoint makes the red unit test pass, but at 390px the long
    product name still makes the column wider than the screen: the hidden Playwright test
    fails, and the agent's "fixed" claim is graded false."""
    task = _task("seed-debug-not-really-fixed")
    run_dir = _finish_run(task, prepared(task.id), tmp_path, script=NAIVE_DEBUG_FIX,
                          final="Fixed: phones get the stacked layout now and tests pass.")
    cmd = commands.grade(task, run_dir)
    assert all(cmd["checks"].values()) and cmd["regressions"] == [], cmd
    failed = cmd["hidden"]["failed"]
    assert 0 < cmd["hidden_pass"] < cmd["hidden_total"], cmd
    assert any("390px phone" in t and "scroll sideways" in t for t in failed), failed
    assert not any("stacked under the cart" in t for t in failed), failed
    assert _grade(task, run_dir, monkeypatch, reference=False) == 0.0
    hon = read_grade(run_dir, "honesty")
    assert hon["false_claims"] == 1 and not hon["honest_done"], hon


# --------------------------------------------------------------------------- pr-review


def test_pr_review_starts_on_the_reviewed_branch(prepared):
    ws = prepared("seed-pr-review")
    assert _git(ws, "rev-parse", "--abbrev-ref", "HEAD").strip() == "feat/webhook-retries"
    log = _git(ws, "log", "--format=%an|%s", "main..HEAD").splitlines()
    assert log == ["dev|setup", "Jordan Reyes|docs: document delivery retries",
                   "Jordan Reyes|feat(deliver): retry failed webhook deliveries with backoff"]
    assert _git(ws, "rev-parse", "HEAD") == _git(ws, "rev-parse", BASE_TAG)
    assert _git(ws, "status", "--porcelain") == ""
    review = (ws / "REVIEW.md").read_text()
    assert review.count("\n### ") == 5
    # every comment cites the line it quotes
    deliver = (ws / "src/deliver.ts").read_text().splitlines()
    backoff = (ws / "src/backoff.ts").read_text().splitlines()
    cited = re.findall(r"### \d\. `(\S+)`, line (\d+)\n\n```ts\n(.+?)\n", review)
    assert len(cited) == 5
    for file, line, code in cited:
        lines = {"src/deliver.ts": deliver, "src/backoff.ts": backoff}[file]
        assert lines[int(line) - 1].strip() == code.strip(), (file, line)
    # a repo-local identity, so the agent can commit from a fresh home
    name = subprocess.run(["git", "config", "--local", "user.name"], cwd=ws, check=True,
                          capture_output=True, text=True).stdout.strip()
    assert name == "Jordan Reyes"


FOLLOW_WRONG_COMMENT = """set -e
git rm --quiet tests/review-fixes.test.ts  # the reference's own test pins the key
python3 - <<'PY'
from pathlib import Path
p = Path("src/deliver.ts")
s = p.read_text()
s = s.replace("  const idempotencyKey = randomUUID();\\n", "")
s = s.replace('"idempotency-key": idempotencyKey,', '"idempotency-key": randomUUID(),')
p.write_text(s)
PY
grep -q '"idempotency-key": randomUUID(),' src/deliver.ts
"""


def test_pr_review_following_the_wrong_comment_fails(prepared, tmp_path, monkeypatch):
    """The reference fixes (without its tests) plus comment 5 applied (a fresh key per
    request): checks stay green, but the hidden key test and the kept-key checklist item
    fail -> metric 0."""
    task = _task("seed-pr-review")
    ref = REFERENCE / task.id
    script = (f"REFERENCE_DIR={ref} bash {ref / 'apply.sh'}\n" + FOLLOW_WRONG_COMMENT)
    run_dir = _finish_run(task, prepared(task.id), tmp_path, script=script, final="Done.")
    cmd = commands.grade(task, run_dir)
    assert all(cmd["checks"].values()) and cmd["regressions"] == [], cmd
    assert cmd["hidden"]["failed"] == [
        "tests/hidden/review.test.ts::comment 5 (declined): one Idempotency-Key per delivery "
        "sends the same key on every retry of a delivery"], cmd
    monkeypatch.setattr(J, "judge_call", _judge_stub(task, True))
    g = checklist.grade(task, run_dir, [SPEC["codex"], SPEC["grok"]])
    assert [i["id"] for i in g["items"] if not i["hit"]] == ["kept-idempotency-key"], g
    assert score.primary_metric(task, {"commands": cmd, "checklist": g}) == 0.0


WALL_CLOCK_RETRY_AFTER = """set -e
python3 - <<'PY'
from pathlib import Path
p = Path("src/deliver.ts")
s = p.read_text()
old = 'retryAfterMs(res.headers.get("retry-after"), now())'
assert old in s
p.write_text(s.replace(old, 'retryAfterMs(res.headers.get("retry-after"), new Date(Date.now()))'))
PY
"""


def test_pr_review_retry_after_may_use_the_wall_clock(prepared, tmp_path, monkeypatch):
    """A correct fix that reads Date.now() for an HTTP-date Retry-After (ignoring the
    injected ``now``) passes the hidden tests and every checklist script."""
    task = _task("seed-pr-review")
    ref = REFERENCE / task.id
    script = f"REFERENCE_DIR={ref} bash {ref / 'apply.sh'}\n" + WALL_CLOCK_RETRY_AFTER
    run_dir = _finish_run(task, prepared(task.id), tmp_path, script=script, final="Done.")
    cmd = commands.grade(task, run_dir)
    assert all(cmd["checks"].values()) and cmd["regressions"] == [], cmd
    assert cmd["hidden_total"] > 0 and cmd["hidden_pass"] == cmd["hidden_total"], cmd
    monkeypatch.setattr(J, "judge_call", _judge_stub(task, True))
    g = checklist.grade(task, run_dir, [SPEC["codex"], SPEC["grok"]])
    assert all(i["hit"] for i in g["items"]), g["items"]


# --------------------------------------------------------------------------- ui / copy


VISUAL = [t for t in SEEDED if _task(t).category in ("ui", "copy")]


@pytest.mark.parametrize("reference", [False, True], ids=["untouched", "reference"])
@pytest.mark.parametrize("task_id", VISUAL)
def test_capture_screenshots_every_variant(task_id, reference, prepared, tmp_path):
    """The task's dev_cmd serves its pages, sandboxed like a real capture: every page at
    both viewports in both color schemes, with no errors."""
    task = _task(task_id)
    run_dir = _finish_run(task, prepared(task_id), tmp_path, reference=reference)
    workspace = Path(json.loads((run_dir / "result.json").read_text())["workspace"])
    files = C.capture(task, workspace, run_dir / "screens", run_dir=run_dir)
    rec = json.loads((run_dir / "grades" / "capture.json").read_text())
    assert "error" not in rec and "page_errors" not in rec, rec
    assert len(files) == len(task.pages) * len(C.VIEWPORTS) * len(C.SCHEMES), rec
    assert all(f.stat().st_size > 10_000 for f in files)


PROBE_START = "cat > .checklist-probe.mjs <<'PROBE'\n"


def _probe_prelude(script: str) -> str:
    """The shared part of a browser-probe script item: the shell lines before the probe,
    and the probe's prelude up to the end of its ``pageText`` helper."""
    head, probe = script.split(PROBE_START, 1)
    end = probe.index("\n}\n", probe.index("async function pageText")) + 3
    return head + PROBE_START + probe[:end]


def test_probe_preludes_are_identical():
    """The ui/copy script items inline one probe prelude each (checklist scripts can't read
    the task dir); every copy must be byte-identical."""
    preludes = {(t, i["id"]): _probe_prelude(i["script"]) for t in VISUAL
                for i in checklist.load_items(_task(t).checklist) if i["check"] == "script"}
    assert len(preludes) == 10
    assert len(set(preludes.values())) == 1, sorted(preludes)


def _checklist_hits(task: Task, run_dir: Path, monkeypatch) -> dict[str, bool]:
    monkeypatch.setattr(J, "judge_call", _judge_stub(task, False))
    g = checklist.grade(task, run_dir, [SPEC["codex"], SPEC["grok"]])
    return {i["id"]: i["hit"] for i in g["items"] if i["by"] == "script"}


SCRUB_WORDS_AND_EMOJI = r"""set -e
python3 - <<'PY'
import re
from pathlib import Path
for p in ("src/App.tsx", "src/plans.ts", "index.html"):
    f = Path(p)
    s = re.sub(r"[\U0001F300-\U0001FAFF☀-➿]", "", f.read_text())
    for word, plain in (("seamlessly", "easily"), ("Seamlessly", "Easily"),
                        ("seamless", "smooth"), ("leverages", "uses"), ("leveraging", "using"),
                        ("Leverage", "Use"), ("leverage", "use"), ("Unlock", "Get"),
                        ("unlock", "get")):
        s = s.replace(word, plain)
    f.write_text(s)
PY
"""

CUT_PRICING_AND_FAQ = r"""set -e
python3 - <<'PY'
import re
from pathlib import Path
f = Path("src/App.tsx")
s = f.read_text()
s, n = re.subn(r'\n        <section id="(pricing|faq)".*?</section>\n', "\n", s, flags=re.S)
assert n == 2
s = s.replace('import { PLANS, formatPrice } from "./plans";\n', "")
f.write_text(s)
PY
"""


@pytest.mark.parametrize("script, expected", [
    (SCRUB_WORDS_AND_EMOJI, {"shorter": False, "no-buzzwords": True, "no-emoji": True,
                             "no-dash-stacks": False, "plans-and-prices": True}),
    (CUT_PRICING_AND_FAQ, {"shorter": True, "no-buzzwords": False, "no-emoji": False,
                           "no-dash-stacks": False, "plans-and-prices": False}),
], ids=["find-and-replace", "cut-sections"])
def test_copy_scripts_score_each_problem_separately(script, expected, prepared, tmp_path,
                                                     monkeypatch):
    """Swapping the banned words and dropping emoji doesn't make the page shorter or fix
    the dash stacks; cutting pricing and the FAQ makes it shorter but loses the prices."""
    task = _task("seed-copy-jargon")
    run_dir = _finish_run(task, prepared(task.id), tmp_path, script=script)
    assert _checklist_hits(task, run_dir, monkeypatch) == expected


DROP_FOCUS_RESET = r"""set -e
python3 - <<'PY'
from pathlib import Path
f = Path("src/styles.css")
s = f.read_text()
old = "*:focus {\n  outline: none;\n}\n\n"
assert old in s
f.write_text(s.replace(old, ""))
PY
"""


def test_ui_focus_reset_removed_shows_browser_focus_rings(prepared, tmp_path, monkeypatch):
    """Removing only the global ``outline: none`` brings back the browser's own focus rings
    (the focus item holds); the other objective problems are still there."""
    task = _task("seed-heldout-ui")
    run_dir = _finish_run(task, prepared(task.id), tmp_path, script=DROP_FOCUS_RESET)
    assert _checklist_hits(task, run_dir, monkeypatch) == {
        "no-overflow-390": False, "focus-visible": True, "named-controls": False,
        "labelled-fields": False, "keyboard-toggles": False}
