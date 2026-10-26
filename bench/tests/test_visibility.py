"""R40-R43: nothing the harness or a task's setup puts in a workspace names the benchmark
or an arm (the bruhs marker blocks in the bruhs arm are the treatment)."""

import base64
import json
import subprocess
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


def _setup_adds(tmp_path, arm, setup):
    task = _seeded(tmp_path, setup)
    ws = prepare_workspace(task, arm, tmp_path / "ws")
    return task, ws


URLSAFE = base64.urlsafe_b64encode(b"\xfb\xef\xbe\xff" + b"bruhsbench-local").decode()
assert "-" in URLSAFE or "_" in URLSAFE


@pytest.mark.parametrize("setup, expect", [
    # a hex-encoded secret that spells the benchmark's name
    ("echo 'secret=\"%s\"' > .env.local" % "bruhsbench-local".encode().hex(), ".env.local"),
    # base64 of it
    ("echo 'TOKEN=YnJ1aHNiZW5jaC1sb2NhbC1vbmx5' > .env.local", ".env.local"),
    # a symlink whose target names it
    ("mkdir -p node_modules && ln -s /opt/bruhsbench/stack node_modules/.stack", "symlink"),
    # a lockfile's own top-level name
    ("echo '{\"name\": \"bench-hidden\", \"lockfileVersion\": 3}' > package-lock.json",
     "lockfile name"),
    # the harness's tokens in a binary file
    ("printf 'SQLite\\0\\0mints-bench|key' > data.db", "binary or large file"),
    # arm names joined with underscores
    ("echo 'WORKDIR=/srv/bare_ws' > .env.local", ".env.local"),
    ("echo 'export ARM_BARE_X=1' > .env.local", ".env.local"),
    # encodings that don't start at the run's first character
    ("echo 'k=a%s' > .env.local" % "bruhsbench-local".encode().hex(), ".env.local"),
    ("echo 'TOKEN=x%s' > .env.local" % base64.b64encode(b"bruhsbench-local-only").decode(),
     ".env.local"),
    # URL-safe base64 (JWTs), with - and _ in the run
    ("echo 'JWT=%s' > .env.local" % URLSAFE, ".env.local"),
])
def test_scan_sees_encoded_linked_locked_binary_and_joined_names(tmp_path, setup, expect):
    task, ws = _setup_adds(tmp_path, "bare", setup + "\n")
    leaks = workspace_leaks(task, ws, "bare")
    assert any(expect in l for l in leaks), leaks


@pytest.mark.parametrize("setup", [
    # a random secret, a random base64 token, a lockfile listing tinybench as a dependency
    "echo 'secret=\"49b1508560ba88b232e16cac42bb9646dc15a2099d84a2326a69ed897a9dedd6\"' > .env.local",
    "echo 'TOKEN=c2VjcmV0LXRva2VuLWZvci1sb2NhbC1kZXY=' > .env.local",
    "echo '{\"name\": \"app\", \"packages\": {\"node_modules/tinybench\": {}}}' > package-lock.json",
    # the card name "Bench" in seed data, words containing "bare"
    "printf 'SQLite\\0\\0Bench Warmer\\0barely' > data.db",
    "echo 'MODE=barely_ok bareMetal=1' > .env.local",
])
def test_scan_ignores_neutral_content(tmp_path, setup):
    task, ws = _setup_adds(tmp_path, "bare", setup + "\n")
    assert workspace_leaks(task, ws, "bare") == []


def test_scan_reads_git_bodies_config_exclude_description_and_hooks(tmp_path):
    task, ws = _setup_adds(tmp_path, "bare", "true\n")
    assert workspace_leaks(task, ws, "bare") == []  # git's own core.bare key isn't a hit
    import subprocess
    from bruhsbench.workspace import GIT
    subprocess.run([*GIT, "commit", "-q", "--allow-empty", "-m", "setup", "-m",
                    "made by bruhsbench"], cwd=ws, check=True)
    (ws / ".git" / "info" / "exclude").write_text("/.bench/\n")
    (ws / ".git" / "description").write_text("bench workspace\n")
    (ws / ".git" / "hooks" / "pre-commit").write_text("#!/bin/sh\n# ARM=bare\n")
    subprocess.run([*GIT, "config", "bench.arm", "x"], cwd=ws, check=True)
    leaks = " ".join(workspace_leaks(task, ws, "bare"))
    for needle in ("made by bruhsbench", "/.bench/", "bench workspace", "ARM=bare", "[bench]"):
        assert needle in leaks, needle


def _private_tasks():
    if not PRIVATE.is_dir():
        return []
    return [t for t in load_tasks(PRIVATE, include_heldout=True)]


@pytest.mark.private
def test_private_tasks_are_present():
    """Under the private marker a missing tasks-private is a failure, not a skip."""
    assert PRIVATE.is_dir() and _private_tasks(), f"no private tasks under {PRIVATE}"


@pytest.mark.private
@pytest.mark.parametrize("task", _private_tasks(), ids=lambda t: t.id)
def test_private_task_workspaces_name_neither_benchmark_nor_arm(task, tmp_path):
    for arm in ("bare", "bruhs"):
        ws = prepare_workspace(task, arm, tmp_path / arm)
        leaks = workspace_leaks(task, ws, arm)
        assert leaks == [], (task.id, arm, leaks)


def test_symlink_to_an_existing_directory_is_checked(tmp_path):
    store = tmp_path / "x" / "bruhsbench-store"
    store.mkdir(parents=True)
    task, ws = _setup_adds(tmp_path, "bare", f"mkdir -p node_modules && ln -s {store} node_modules/.stack\n")
    assert any(l.startswith("symlink: node_modules/.stack -> ") for l in workspace_leaks(task, ws, "bare"))


def test_setup_branches_leave_no_reflog_trace_and_logs_are_scanned(tmp_path):
    """A branch a setup creates and deletes leaves nothing in the reflog (it is expired
    after setup), and anything in .git/logs would be flagged."""
    from bruhsbench.workspace import GIT
    setup = ("git -c user.name=t -c user.email=t@t checkout -q -b bench-tmp && "
             "git -c user.name=t -c user.email=t@t commit -q --allow-empty -m wip && "
             "git checkout -q - && git branch -q -D bench-tmp\n")
    task, ws = _setup_adds(tmp_path, "bare", setup)
    reflog = subprocess.run([*GIT, "reflog", "--all"], cwd=ws, capture_output=True,
                            text=True).stdout
    logs = "".join(p.read_text(errors="replace") for p in (ws / ".git" / "logs").rglob("*")
                   if p.is_file())
    assert "bench-tmp" not in reflog + logs
    assert workspace_leaks(task, ws, "bare") == []
    (ws / ".git" / "logs" / "refs" / "heads").mkdir(parents=True, exist_ok=True)
    (ws / ".git" / "logs" / "refs" / "heads" / "x").write_text(
        "0000 1111 t <t@t> 0 +0000\tcheckout: moving from main to bench-tmp\n")
    assert any("bench-tmp" in l for l in workspace_leaks(task, ws, "bare"))


def test_dependency_and_build_dirs_are_not_the_harness(tmp_path):
    """A virtualenv's packages and a Cargo target dir hold third-party/compiler text
    (FastAPI's README mentions benchmarks; Rust test binaries contain libtest strings)."""
    setup = ("mkdir -p .venv/lib/site-packages/fastapi target/debug && "
             "echo 'TechEmpower benchmarks' > .venv/lib/site-packages/fastapi/METADATA && "
             "touch Cargo.toml && printf 'x\\0RUST_BENCH_FORMAT' > target/debug/app\n")
    task, ws = _setup_adds(tmp_path, "bare", setup)
    assert workspace_leaks(task, ws, "bare") == []
