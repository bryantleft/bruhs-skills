"""R40-R43: nothing the harness or a task's setup puts in a workspace names the benchmark
or an arm (the bruhs marker blocks in the bruhs arm are the treatment)."""

import json
from dataclasses import replace
from pathlib import Path

import pytest

from bruhsbench.tasks import BENCH_DIR, load_task, load_tasks
from bruhsbench.visibility import workspace_leaks
from bruhsbench.workspace import prepare_workspace

PRIVATE = BENCH_DIR / "tasks-private"


def _seeded(tmp_path: Path, setup: str) -> object:
    d = tmp_path / "task-v"
    (d / "fixture" / "src").mkdir(parents=True)
    (d / "task.toml").write_text('id = "task-v"\ncategory = "feature"\n')
    (d / "prompt.md").write_text("do it\n")
    (d / "fixture" / "src" / "bench_utils.ts").write_text("// microbench helpers\n")
    (d / "fixture" / "package.json").write_text(json.dumps({"scripts": {"test": "vitest"}}))
    (d / "setup.sh").write_text(setup)
    return load_task(d)


LEAKY = """mkdir -p node_modules/.bench node_modules/tinybench node_modules/.bench/hidden/node_modules/tinybench
echo 'instance="mints-bench"' > node_modules/.bench/dev.sh
echo 'tinybench' > node_modules/.bench/hidden/node_modules/tinybench/README.md
echo 'export const x = 1' > node_modules/tinybench/index.js
node -e 'const f="package.json",p=JSON.parse(require("fs").readFileSync(f));p.scripts.dev="bash node_modules/.bench/dev.sh";require("fs").writeFileSync(f,JSON.stringify(p))'
"""
CLEAN = """mkdir -p node_modules/.local-stack node_modules/tinybench
echo 'instance="local"' > node_modules/.local-stack/dev.sh
echo 'export const x = 1' > node_modules/tinybench/index.js
"""


def test_scan_finds_setup_added_names_and_text(tmp_path):
    task = _seeded(tmp_path, LEAKY)
    ws = prepare_workspace(task, "bare", tmp_path / "ws")
    leaks = workspace_leaks(task, ws, "bare")
    assert "dir name: node_modules/.bench" in leaks
    assert any(l.startswith("node_modules/.bench/dev.sh: instance=") for l in leaks)
    assert any("script dev: bash node_modules/.bench/dev.sh" in l for l in leaks)
    # third-party packages and the task's own unchanged files are not the harness's
    assert not any("tinybench" in l or "bench_utils" in l for l in leaks)


@pytest.mark.parametrize("arm", ("bare", "bruhs"))
def test_scan_is_clean_for_neutral_setup_in_both_arms(tmp_path, arm):
    task = _seeded(tmp_path, CLEAN)
    ws = prepare_workspace(task, arm, tmp_path / "ws")
    assert workspace_leaks(task, ws, arm) == []
    if arm == "bruhs":  # the marker blocks are there, and are the treatment
        assert "bruhs:state:begin" in (ws / "CLAUDE.md").read_text()


def _private_tasks():
    if not PRIVATE.is_dir():
        return []
    return [t for t in load_tasks(PRIVATE, include_heldout=True)]


@pytest.mark.private
@pytest.mark.parametrize("task", _private_tasks(), ids=lambda t: t.id)
def test_private_task_workspaces_name_neither_benchmark_nor_arm(task, tmp_path):
    for arm in ("bare", "bruhs"):
        ws = prepare_workspace(task, arm, tmp_path / arm)
        leaks = workspace_leaks(task, ws, arm)
        assert leaks == [], (task.id, arm, leaks)
