"""Builders for a finished run: a tiny git workspace tagged with the base tag plus a results dir
laid out like runner.run_one's (result.json, diff.patch, final.txt, transcript.jsonl)."""

from __future__ import annotations

import atexit
import importlib.util
import json
import os
import shutil
import subprocess
import sys
import tempfile
from dataclasses import replace
from pathlib import Path

import pytest

from bruhsbench.types import Task
from bruhsbench.workspace import BASE_MESSAGE, BASE_TAG, GIT


def _sandbox_readable_pytest() -> str:
    """A pytest command the sandboxed checks can run: this venv lives in the user's
    home and the per-user temp dir is blocked too, so pytest and its deps are copied to
    /private/var/tmp (readable, not writable, in the sandbox) and run with the venv's
    base interpreter."""
    lib = Path(tempfile.mkdtemp(prefix="bruhsbench-pytest-", dir="/private/var/tmp"))
    atexit.register(shutil.rmtree, lib, ignore_errors=True)
    for mod in ("pytest", "_pytest", "pluggy", "iniconfig", "packaging", "py", "pygments"):
        spec = importlib.util.find_spec(mod)
        if spec is None or spec.origin is None:
            continue
        origin = Path(spec.origin)
        if origin.name == "__init__.py":
            shutil.copytree(origin.parent, lib / mod,
                            ignore=shutil.ignore_patterns("__pycache__"))
        else:
            shutil.copy2(origin, lib / origin.name)
    python = os.path.realpath(sys._base_executable)
    return f"PYTHONPATH={lib} {python} -m pytest -q -p no:cacheprovider"


PYTEST = _sandbox_readable_pytest()


def git(cwd: Path, *args: str) -> str:
    return subprocess.run([*GIT, *args], cwd=cwd, check=True, capture_output=True,
                          text=True).stdout


def make_task(tmp_path: Path, **kw) -> Task:
    d = tmp_path / "task"
    d.mkdir(exist_ok=True)
    base = Task(id="t", category="feature", dir=d, repo=None, base=None, prompt="p",
                setup=None, allowed_paths=(), pages=(), dev_cmd=None, dev_port=None,
                checks={}, hidden_tests=None, known_issues=None, checklist=None,
                heldout=False)
    return replace(base, **kw)


class Run:
    """A workspace (base files committed + tagged) and its results dir."""

    def __init__(self, tmp_path: Path, files: dict[str, str], run_id: str = "t__claude__bare__r1"):
        self.workspace = tmp_path / "work" / run_id / "workspace"
        self.workspace.mkdir(parents=True)
        self.run_dir = tmp_path / "results" / run_id
        self.run_dir.mkdir(parents=True)
        self.write(files)
        git(self.workspace, "init", "--quiet", "-b", "main")
        git(self.workspace, "add", "-A")
        git(self.workspace, "commit", "--quiet", "-m", BASE_MESSAGE)
        git(self.workspace, "tag", BASE_TAG)

    def write(self, files: dict[str, str]) -> None:
        for rel, text in files.items():
            p = self.workspace / rel
            p.parent.mkdir(parents=True, exist_ok=True)
            p.write_text(text)

    def finish(self, final: str = "", transcript: str = "", status: str = "ok") -> Path:
        """Record the run like the runner does once the agent exits."""
        git(self.workspace, "add", "-A")
        diff = subprocess.run([*GIT, "diff", "--cached", "--binary", BASE_TAG],
                              cwd=self.workspace, check=True, capture_output=True).stdout
        (self.run_dir / "diff.patch").write_bytes(diff)
        (self.run_dir / "final.txt").write_text(final)
        (self.run_dir / "transcript.jsonl").write_text(transcript)
        (self.run_dir / "result.json").write_text(json.dumps({
            "run_id": self.run_dir.name, "status": status, "final_message": final,
            "workspace": str(self.workspace),
            "diff_path": str(self.run_dir / "diff.patch"),
            "transcript_path": str(self.run_dir / "transcript.jsonl"),
        }))
        return self.run_dir


@pytest.fixture
def make_run(tmp_path):
    def _make(files: dict[str, str], run_id: str = "t__claude__bare__r1") -> Run:
        return Run(tmp_path, files, run_id)
    return _make
