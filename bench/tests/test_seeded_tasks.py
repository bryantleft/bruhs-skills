"""Validate each seeded task end to end with the real graders (Task 10, Step 2).

For every task in ``SEEDED``: build its workspace exactly as a run would
(``prepare_workspace``: fixture copy, setup.sh, bench-base commit, after_base.sh), then grade

* the untouched workspace -> low score, and
* the workspace with the reference solution applied (``tests/reference/<task>/apply.sh``,
  never visible to agents) -> full marks,

with deterministic stand-ins for the model-backed parts: audit findings are parsed from
``### [severity] file:lines`` headings and matched by file/line only; checklist judge items
are answered "hit" for the reference run and "miss" otherwise.

Workspaces are prepared once per task per session (setup installs pinned deps: npm ci,
cargo build), so these tests are marked ``seeded`` and skip when the toolchain is missing.
Later Task 10 batches add their tasks to ``SEEDED`` and, for new categories, a grading
branch in ``_grade``.
"""

from __future__ import annotations

import json
import os
import re
import shutil
import subprocess
from pathlib import Path

import pytest

from bruhsbench import judge as J
from bruhsbench.graders import audit, checklist, commands
from bruhsbench.tasks import BENCH_DIR, load_task
from bruhsbench.types import MODELS, Task
from bruhsbench.workspace import BASE_TAG, GIT, prepare_workspace

pytestmark = pytest.mark.seeded

REFERENCE = Path(__file__).parent / "reference"
TASKS_DIR = BENCH_DIR / "tasks"
SEEDED = ["seed-audit-ts", "seed-audit-rust", "seed-ship-messy-diff"]
TOOLS = {"seed-audit-ts": ["npm", "node"], "seed-audit-rust": ["cargo"],
         "seed-ship-messy-diff": ["npm", "node"]}
SPEC = {m.cli: m for m in MODELS}
RUN_CLI = "claude"  # the graded runs' family; checklist judges are the other two
FINDING_RE = re.compile(r"^#{2,4} \[(\w+)\] (\S+?):(\d+)(?:-(\d+))?\s*$", re.MULTILINE)


def _task(task_id: str) -> Task:
    return load_task(TASKS_DIR / task_id)


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


def _finish_run(task: Task, base_ws: Path, tmp_path: Path, *, reference: bool) -> Path:
    """A finished run of ``task`` (laid out like runner.run_one's) starting from a clone of
    the prepared workspace, with the reference solution applied if ``reference``."""
    run_id = f"{task.id}__{RUN_CLI}__bare__r1"
    workspace = tmp_path / "work" / run_id / "workspace"
    workspace.parent.mkdir(parents=True)
    commands.clone_tree(base_ws, workspace)
    final = ""
    if reference:
        ref = REFERENCE / task.id
        subprocess.run(["bash", str(ref / "apply.sh")], cwd=workspace, check=True,
                       env={**os.environ, "REFERENCE_DIR": str(ref)})
        final = "Done."
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


def _judge_stub(task: Task, hit: bool):
    """judge_call stand-in: every judge answers ``hit`` for every judge item."""
    ids = [i["id"] for i in checklist.load_items(task.checklist) if i["check"] == "judge"]

    def fake(judge, prompt, images, schema):
        return {"items": [{"id": i, "hit": hit, "evidence": "stub"} for i in ids]}
    return fake


def _grade(task: Task, run_dir: Path, monkeypatch, *, reference: bool) -> float:
    """The task's primary metric (score.py: audit = F1, ship = checklist score)."""
    if task.category == "audit":
        g = audit.grade(task, run_dir, extract_findings=extract_findings,
                        match_finding=no_semantic_match)
        if reference:
            assert g["missed"] == [] and g["decoys_flagged"] == 0 and g["fp"] == 0, g
            assert g["severity_accuracy"] == 1.0, g
        return g["f1"]
    if task.category == "ship":
        monkeypatch.setattr(J, "judge_call", _judge_stub(task, reference))
        g = checklist.grade(task, run_dir, [SPEC["codex"], SPEC["grok"]])
        assert "invalid" not in g, g
        if reference:
            assert all(i["hit"] for i in g["items"]), g["items"]
        return g["score"]
    raise AssertionError(f"no grading branch for category {task.category}")


# --------------------------------------------------------------------------- task files


@pytest.mark.parametrize("task_id", SEEDED)
def test_task_files(task_id):
    task = _task(task_id)
    fixture = task.dir / "fixture"
    assert (fixture / ".gitignore").is_file()
    lock = [p for p in ("package-lock.json", "pnpm-lock.yaml", "Cargo.lock")
            if (fixture / p).is_file()]
    assert lock, "fixture has no lockfile"
    for build_dir in ("node_modules", "target", "dist"):
        assert not (fixture / build_dir).exists(), f"{build_dir}/ left in the fixture"
    assert task.setup is not None and task.checks.get("test")
    prompt = task.prompt.lower()
    for word in ("bruhs", "grade", "benchmark", "checklist", "decoy"):
        assert word not in prompt
    assert (REFERENCE / task_id / "apply.sh").is_file()
    assert not (task.dir / "reference").exists()


@pytest.mark.parametrize("task_id", [t for t in SEEDED if _task(t).category == "audit"])
def test_known_issues_locate_planted_code(task_id):
    task = _task(task_id)
    known = json.loads(task.known_issues.read_text())
    anchors = json.loads((REFERENCE / task_id / "anchors.json").read_text())
    ids = [e["id"] for e in known]
    assert len(ids) == len(set(ids)) == len(anchors)
    real = [e for e in known if not e["decoy"]]
    assert 14 <= len(real) <= 17 and len(known) - len(real) == 4
    assert {e["severity"] for e in real} >= {"critical", "high", "medium", "low"}
    for e in known:
        lines = (task.dir / "fixture" / e["file"]).read_text().splitlines()
        a, b = e["lines"]
        assert 1 <= a <= b <= len(lines), e["id"]
        assert any(anchors[e["id"]] in line for line in lines[a - 1:b]), e["id"]
        assert e["summary"]
    for x in known:  # ranges in one file never overlap: a cited line picks one entry
        for y in known:
            if x is not y and x["file"] == y["file"]:
                assert x["lines"][1] < y["lines"][0] or y["lines"][1] < x["lines"][0]


# --------------------------------------------------------------------------- grading


@pytest.mark.parametrize("task_id", SEEDED)
def test_untouched_fixture_scores_low(task_id, prepared, tmp_path, monkeypatch):
    task = _task(task_id)
    run_dir = _finish_run(task, prepared(task_id), tmp_path, reference=False)
    cmd = commands.grade(task, run_dir)
    assert all(cmd["checks"].values()), cmd  # builds and tests pass offline after setup
    assert cmd["regressions"] == [], cmd
    assert _grade(task, run_dir, monkeypatch, reference=False) <= 0.2


@pytest.mark.parametrize("task_id", SEEDED)
def test_reference_solution_scores_full(task_id, prepared, tmp_path, monkeypatch):
    task = _task(task_id)
    run_dir = _finish_run(task, prepared(task_id), tmp_path, reference=True)
    cmd = commands.grade(task, run_dir)
    assert all(cmd["checks"].values()), cmd
    assert cmd["regressions"] == [], cmd
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
