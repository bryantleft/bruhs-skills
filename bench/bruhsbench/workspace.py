"""Per-run repo checkout preparation for each arm."""

from __future__ import annotations

import json
import re
import shutil
import subprocess
import sys
from pathlib import Path

from .types import Arm, Task

DEFAULT_SCRIPTS_DIR = Path(__file__).resolve().parents[2] / "scripts"
SETUP_TIMEOUT_S = 15 * 60
BASE_TAG = "bench-base"

GIT = ["git", "-c", "user.name=bruhsbench", "-c", "user.email=bench@localhost",
       "-c", "commit.gpgsign=false", "-c", "tag.gpgsign=false"]

_BLOCK_RE = re.compile(
    r"<!--\s*bruhs:(?P<kind>[\w-]+):begin[^>]*-->.*?<!--\s*bruhs:(?P=kind):end\s*-->[ \t]*\n?",
    re.DOTALL,
)
_EMPTY_HEADING_RE = re.compile(r"^## bruhs-managed[ \t]*(?:\n\s*)?(?=^#|\Z)", re.MULTILINE)


class SetupFailed(Exception):
    pass


def strip_bruhs_blocks(text: str) -> str:
    """Remove every bruhs marker block, and the `## bruhs-managed` heading if left empty."""
    stripped, n = _BLOCK_RE.subn("", text)
    if n == 0:
        return text
    stripped = _EMPTY_HEADING_RE.sub("", stripped)
    stripped = stripped.rstrip()
    return stripped + "\n" if stripped else ""


def _git(cwd: Path, *args: str) -> str:
    return subprocess.run(
        [*GIT, *args], cwd=cwd, check=True, capture_output=True, text=True
    ).stdout


def _run_script(scripts_dir: Path, name: str, args: list[str], stdin: str) -> str:
    proc = subprocess.run(
        [sys.executable, str(scripts_dir / name), *args],
        input=stdin, capture_output=True, text=True,
    )
    if proc.returncode != 0:
        raise RuntimeError(f"{name} failed ({proc.returncode}): {proc.stderr.strip()}")
    return proc.stdout


def insert_bruhs_blocks(root: Path, scripts_dir: Path | None = None) -> None:
    """Write bruhs state + rules blocks into CLAUDE.md/AGENTS.md (no Linear integration)."""
    scripts = scripts_dir or DEFAULT_SCRIPTS_DIR
    detected = json.loads(_run_script(scripts, "detect_stack.py", [str(root)], ""))
    detected.pop("root", None)  # absolute path; not part of the state
    detected.pop("confidence", None)
    state = json.dumps({"stack": detected, "tooling": {"mcps": [], "skills": []}})
    rules = _run_script(scripts, "derive_stack_rules.py", [], state)
    _run_script(scripts, "sync_bruhs_block.py", ["--kind", "state", "--root", str(root)], state)
    # No detected stack -> no rules: bruhs itself writes no rules block then
    # (sync_bruhs_block.py rejects empty input), so neither do we.
    if rules.strip():
        _run_script(scripts, "sync_bruhs_block.py", ["--kind", "rules", "--root", str(root)],
                    rules)


def _checkout(task: Task, dest: Path) -> None:
    if task.repo is not None:
        if task.base is None:
            raise ValueError(f"task {task.id}: repo set without base")
        subprocess.run(
            ["git", "clone", "--no-hardlinks", "--quiet", str(task.repo), str(dest)],
            check=True, capture_output=True, text=True,
        )
        _git(dest, "checkout", "--detach", "--quiet", task.base)
        for remote in _git(dest, "remote").split():
            _git(dest, "remote", "remove", remote)
        # Make the future solution unreachable: drop every ref, reflogs, and prune objects.
        for ref in _git(dest, "for-each-ref", "--format=%(refname)").split():
            _git(dest, "update-ref", "-d", ref)
        _git(dest, "reflog", "expire", "--expire=now", "--all")
        _git(dest, "gc", "--prune=now", "--quiet")
    else:
        fixture = task.dir / "fixture"
        if not fixture.is_dir():
            raise FileNotFoundError(f"task {task.id}: seeded task has no fixture/ at {fixture}")
        shutil.copytree(fixture, dest, ignore=shutil.ignore_patterns(".git"))
        _git(dest, "init", "--quiet", "-b", "main")
        _git(dest, "add", "-A")
        _git(dest, "commit", "--quiet", "--allow-empty", "-m", "fixture")


def _run_task_script(task: Task, script: Path | None, dest: Path) -> None:
    """Run a trusted task script (setup.sh, after_base.sh) unsandboxed in ``dest``."""
    if script is None:
        return
    try:
        proc = subprocess.run(
            ["bash", str(script.resolve())], cwd=dest,
            capture_output=True, text=True, timeout=SETUP_TIMEOUT_S,
        )
    except subprocess.TimeoutExpired as exc:
        raise SetupFailed(f"{task.id}: {script.name} timed out after {SETUP_TIMEOUT_S}s") from exc
    if proc.returncode != 0:
        tail = (proc.stderr or proc.stdout)[-2000:]
        raise SetupFailed(f"{task.id}: {script.name} exited {proc.returncode}: {tail}")


def prepare_workspace(
    task: Task, arm: Arm, dest: Path, scripts_dir: Path | None = None
) -> Path:
    """Create a fresh checkout at `dest` for `arm`, run setup, commit it as `bench: base`."""
    dest = Path(dest)
    if dest.exists() and any(dest.iterdir()):
        raise FileExistsError(f"workspace destination not empty: {dest}")
    dest.parent.mkdir(parents=True, exist_ok=True)
    _checkout(task, dest)

    for name in ("CLAUDE.md", "AGENTS.md"):
        p = dest / name
        if p.is_file():
            p.write_text(strip_bruhs_blocks(p.read_text(encoding="utf-8")), encoding="utf-8")
    (dest / ".claude" / "bruhs.json").unlink(missing_ok=True)

    if arm == "bruhs":
        insert_bruhs_blocks(dest, scripts_dir)

    # Setup runs before the base commit so its output is part of base, not the agent diff.
    _run_task_script(task, task.setup, dest)

    _git(dest, "add", "-A")
    _git(dest, "commit", "--quiet", "--allow-empty", "-m", "bench: base")
    _git(dest, "tag", "-f", BASE_TAG)
    # after_base.sh leaves work the agent starts from uncommitted (staged, unstaged,
    # untracked); it shows in the run's diff against bench-base like the agent's own edits.
    _run_task_script(task, task.after_base, dest)
    return dest


def check_task_setup(task: Task, scratch: Path, scripts_dir: Path | None = None) -> bool:
    """Prepare both arms once in scratch; False (setup failed in either arm) means
    exclude the task from both arms."""
    for arm in ("bare", "bruhs"):
        dest = Path(scratch) / f"setup-check-{task.id}-{arm}"
        if dest.exists():
            shutil.rmtree(dest)
        try:
            prepare_workspace(task, arm, dest, scripts_dir)
        except SetupFailed:
            return False
        finally:
            shutil.rmtree(dest, ignore_errors=True)
    return True
