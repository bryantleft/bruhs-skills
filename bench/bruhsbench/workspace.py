"""Per-run repo checkout preparation for each arm."""

from __future__ import annotations

import json
import re
import shutil
import subprocess
import sys
from pathlib import Path

from .sandbox import check_tmp_base
from .types import Arm, Task

DEFAULT_SCRIPTS_DIR = Path(__file__).resolve().parents[2] / "scripts"
SETUP_TIMEOUT_S = 15 * 60
# R42: everything an agent can see in the workspace's git is neutral (no benchmark, no
# arm): the identity, the commit messages and the tag the graders diff against.
BASE_TAG = "base"
BASE_MESSAGE = "setup"
FIXTURE_MESSAGE = "initial"
# Frozen checklist scripts written before R42 name the base `bench-base`; graders add it
# as an alias in their own disposable clones only (never in the agent's workspace).
FROZEN_BASE_ALIAS = "bench-base"

GIT = ["git", "-c", "user.name=dev", "-c", "user.email=dev@localhost",
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
        # Fetch only the base commit's history into a fresh repo: the future solution is
        # never copied (no refs, no remote, no objects past base), and none of the source
        # repo's other objects are written to disk, unlike a full clone + gc.
        commit = _git(Path(task.repo), "rev-parse", "--verify", f"{task.base}^{{commit}}").strip()
        dest.mkdir(parents=True, exist_ok=True)
        _git(dest, "init", "--quiet")
        _git(dest, "fetch", "--quiet", "--no-tags", str(Path(task.repo).resolve()), commit)
        _git(dest, "checkout", "--detach", "--quiet", commit)
        (dest / ".git" / "FETCH_HEAD").unlink(missing_ok=True)  # names the source repo
        _git(dest, "reflog", "expire", "--expire=now", "--all")
    else:
        fixture = task.dir / "fixture"
        if not fixture.is_dir():
            raise FileNotFoundError(f"task {task.id}: seeded task has no fixture/ at {fixture}")
        shutil.copytree(fixture, dest, ignore=shutil.ignore_patterns(".git"))
        _git(dest, "init", "--quiet", "-b", "main")
        _git(dest, "add", "-A")
        _git(dest, "commit", "--quiet", "--allow-empty", "-m", FIXTURE_MESSAGE)


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
    """Create a fresh checkout at `dest` for `arm`, run setup, commit it as the base
    (:data:`BASE_MESSAGE`, tagged :data:`BASE_TAG`).

    Raises ``sandbox.TmpDirTooLong`` first if the sandboxed processes that will use the
    workspace couldn't get a short enough ``TMPDIR`` (R37)."""
    check_tmp_base()
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
    _git(dest, "commit", "--quiet", "--allow-empty", "-m", BASE_MESSAGE)
    _git(dest, "tag", "-f", BASE_TAG)
    # after_base.sh leaves work the agent starts from uncommitted (staged, unstaged,
    # untracked); it shows in the run's diff against the base like the agent's own edits.
    _run_task_script(task, task.after_base, dest)
    # what setup did in git (branches it made and dropped, checkouts) stays out of the
    # reflog an agent can read, as for the checkout itself
    _git(dest, "reflog", "expire", "--expire=now", "--all")
    # and its dropped commits out of the object store (`git fsck --unreachable`)
    _git(dest, "gc", "--prune=now", "--quiet")
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
