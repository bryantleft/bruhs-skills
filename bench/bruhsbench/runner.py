"""Execute benchmark runs: one (task, model, arm, repeat) at a time, or the whole matrix.

Layout (Ruling R10). Everything an agent touches lives in a *work root* outside the
user's home (``$BRUHSBENCH_WORK`` or ``/private/tmp/bruhsbench``, plus a per-results
id): the pinned bruhs export at ``<work>/_bruhs/<commit>/`` and, per run,
``<work>/<run_id>/{home,workspace,final.txt}``, with its ``TMPDIR`` at the short
``sandbox.tmp_dir(<work>/<run_id>)`` (R37: under 78 characters for unix sockets); graders' scratch
copies go to ``<work>/_scratch/``, outside every run root. The results dir
``<out_root>/<run_id>/`` only receives copies: ``result.json``, ``transcript.jsonl`` (raw
CLI stdout, streaming JSON for all three CLIs), ``stderr.txt``, ``diff.patch``,
``final.txt``.

Sandbox (R19-R22): the agent runs under ``sandbox.wrap`` with only its run dir
writable (and readable) inside the work base, its own short private ``TMPDIR``, no
access to the rest of the work base or the real home, no unix sockets but its own, no
``lsof``/``ps`` on other processes, and no clipboard or app-launching. Its stdout/stderr
are drained over pipes into the results dir, so it can't forge its transcript. Other
files it may have written (session logs, codex ``final.txt``) are read only through
``untrusted`` (no symlinks, regular files; anything else lands in ``unsafe_files``), and
git on the workspace runs hardened and sandboxed. ``result.json`` records
the workspace's absolute path for the graders and is written last (atomically), so a
run dir without it is partial and is redone on resume.

``out_root/matrix.json`` pins the bruhs commit, CLI versions, models, repeats and seed;
``out_root/excluded.json`` lists tasks whose setup failed (excluded from both arms).

Contamination (R9/R14): after each run the transcript, stderr and the CLI's own
session logs inside the run's home are scanned for absolute paths under the real home
or the source repos. ``contaminated`` is None when none of that material shows any
tool-level event (nothing to check), else True/False.

A failing run never takes the matrix down: harness exceptions are recorded as
``status="error"`` with the traceback. Only an auth failure (:class:`AuthAbort`) or an
interrupt (Ctrl-C) stops it; both kill every live agent process group first.
"""

from __future__ import annotations

import fcntl
import hashlib
import json
import logging
import os
import random
import re
import select
import shutil
import signal
import subprocess
import threading
import time
import traceback
from collections.abc import Callable, Sequence
from concurrent.futures import ThreadPoolExecutor, as_completed
from contextlib import contextmanager, nullcontext
from dataclasses import asdict, replace
from datetime import datetime, timezone
from pathlib import Path, PurePath

from . import untrusted
from .agents import build_command, is_auth_failure, parse_output, tool_event_count
from .homes import ClaudeAuthMissing, build_home, claude_auth, export_bruhs
from .sandbox import (check_tmp_base, private_tmp, real_home, remove_private_tmp, work_base,
                      wrap)
from .types import Arm, Cli, ModelSpec, RunResult, RunSpec, Task
from .workspace import BASE_TAG, SetupFailed, check_task_setup, prepare_workspace

log = logging.getLogger(__name__)

BRUHS_REPO = Path(__file__).resolve().parents[2]
DEFAULT_TIMEOUT_S = 45 * 60
DEFAULT_PARALLEL = 6
CLAUDE_MAX_PARALLEL = 3  # parallel claude runs share one account token (rate limits)
DEFAULT_SEED = 0
KILL_GRACE_S = 10
# CLI session logs inside the run's home (scanned for contamination)
SESSION_LOG_DIRS = (".claude/projects", ".codex/sessions", ".grok/sessions")
_SESSION_TOOL_RE = re.compile(
    r'"type"\s*:\s*"(?:tool_use|tool_result|tool_call|tool_call_update|function_call|'
    r'function_call_output|custom_tool_call|local_shell_call|command_execution)"')

# (spec, argv the real CLI would get) -> argv to run instead; tests install a fake agent
CommandOverride = Callable[[RunSpec, list[str]], list[str]]


class AuthAbort(Exception):
    """A CLI reported it isn't authenticated; the matrix stops instead of scoring zeros."""


class RunInterrupted(Exception):
    """The matrix was stopped while this run was live; nothing is recorded for it."""


class DiskLow(Exception):
    """Too little free disk to start (or capture/grade) a run; the matrix stops cleanly
    and is resumable."""


class RunControl:
    """Live agent process groups of a matrix, so an interrupt can kill all of them."""

    def __init__(self) -> None:
        self._lock = threading.Lock()
        self._pgids: set[int] = set()
        self.stopped = threading.Event()

    def spawn(self, run_id: str, start: Callable[[], subprocess.Popen]) -> subprocess.Popen:
        with self._lock:
            if self.stopped.is_set():
                raise RunInterrupted(run_id)
            proc = start()
            self._pgids.add(proc.pid)  # start_new_session: pgid == pid
            return proc

    def release(self, proc: subprocess.Popen) -> None:
        with self._lock:
            self._pgids.discard(proc.pid)

    def kill_all(self) -> None:
        with self._lock:
            self.stopped.set()
            for pgid in self._pgids:
                _kill_group(pgid, signal.SIGKILL)


# --------------------------------------------------------------------------- paths


def results_id(out_root: Path) -> str:
    resolved = str(Path(out_root).resolve())
    return f"{Path(out_root).name}-{hashlib.sha1(resolved.encode()).hexdigest()[:8]}"


def _check_outside_home(path: Path) -> Path:
    if Path(path).resolve().is_relative_to(real_home()):
        raise ValueError(f"work root {path} is inside the user's home; the CLIs would "
                         "discover ~/ config from its ancestors (set BRUHSBENCH_WORK)")
    return Path(path)


def default_work_root(out_root: Path) -> Path:
    base = work_base()
    return _check_outside_home(base / results_id(out_root))


def git_head(repo: Path, rev: str = "HEAD") -> str:
    return subprocess.run(["git", "rev-parse", "--verify", f"{rev}^{{commit}}"], cwd=repo,
                          check=True, capture_output=True, text=True).stdout.strip()


_export_lock = threading.Lock()


def ensure_bruhs_export(work_root: Path, commit: str) -> Path:
    """The filtered bruhs tree for ``commit`` under the work root, exported once."""
    with _export_lock:
        dest = Path(work_root) / "_bruhs" / commit
        done = dest.parent / f"{commit}.ok"  # sibling, so it never reaches an agent's home
        if done.exists() and dest.is_dir():
            return dest
        if dest.exists():
            shutil.rmtree(dest)
        dest.parent.mkdir(parents=True, exist_ok=True)
        export_bruhs(BRUHS_REPO, commit, dest)
        done.touch()
        return dest


# --------------------------------------------------------------------------- disk

MIN_FREE_ENV = "BRUHSBENCH_MIN_FREE_GB"
DEFAULT_MIN_FREE_GB = 10.0  # ruling R36
DISK_WAIT_S = 20 * 60  # how long a starved run waits for other runs' cleanup
DISK_POLL_S = 30.0
FreeSpace = Callable[[Path], float]


def free_gb(path: Path) -> float:
    """Free GiB (as ``df -g`` counts) on the filesystem holding ``path`` (or its nearest
    existing ancestor)."""
    p = Path(path)
    while not p.exists() and p != p.parent:
        p = p.parent
    return shutil.disk_usage(p).free / 2**30


def min_free_gb() -> float:
    raw = os.environ.get(MIN_FREE_ENV)
    if not raw:
        return DEFAULT_MIN_FREE_GB
    try:
        return float(raw)
    except ValueError:
        raise ValueError(f"{MIN_FREE_ENV}={raw!r} is not a number") from None


class DiskGuard:
    """Refuses to start work while the filesystems holding ``paths`` have less than
    ``min_gb`` free (``$BRUHSBENCH_MIN_FREE_GB``, default 10). While other jobs are live
    (:meth:`job`), :meth:`wait` polls for up to ``wait_s`` for their cleanup to free
    space; then (or at once, with nothing else running) it raises :class:`DiskLow`."""

    def __init__(self, paths: Sequence[Path], *, min_gb: float | None = None,
                 free_fn: FreeSpace | None = None, wait_s: float = DISK_WAIT_S,
                 poll_s: float = DISK_POLL_S, sleep: Callable[[float], None] = time.sleep):
        self.paths = [Path(p) for p in paths]
        self.min_gb = min_free_gb() if min_gb is None else min_gb
        self._free_fn = free_fn
        self.wait_s, self.poll_s, self._sleep = wait_s, poll_s, sleep
        self._lock = threading.Lock()
        self._active = 0
        self._local = threading.local()

    def free(self) -> float:
        fn = self._free_fn or free_gb  # looked up late, so tests can patch free_gb
        return min(fn(p) for p in self.paths)

    @contextmanager
    def job(self):
        """Mark the calling thread as a live job (its cleanup may free space)."""
        with self._lock:
            self._active += 1
        self._local.depth = getattr(self._local, "depth", 0) + 1
        try:
            yield
        finally:
            self._local.depth -= 1
            with self._lock:
                self._active -= 1

    def _others(self) -> int:
        with self._lock:
            return self._active - (1 if getattr(self._local, "depth", 0) else 0)

    def wait(self, what: str) -> float:
        """Free GiB once there is at least ``min_gb``; :class:`DiskLow` if it doesn't
        come."""
        free, waited = self.free(), 0.0
        while free < self.min_gb:
            if self._others() <= 0 or waited >= self.wait_s:
                raise DiskLow(
                    f"only {free:.1f} GB free under {self.paths[0]} (need {self.min_gb:g}, "
                    f"${MIN_FREE_ENV}) before {what}; stopped cleanly. Free space (e.g. "
                    "`bruhsbench clean`) and rerun the same command to resume.")
            log.warning("%s: %.1f GB free (< %g); waiting for other runs' cleanup", what,
                        free, self.min_gb)
            self._sleep(self.poll_s)
            waited += self.poll_s
            free = self.free()
        return free


# --------------------------------------------------------------------------- cleanup


def _check_cleanable(work_root: Path, protect: Sequence[Path]) -> Path:
    """The resolved work root, if deleting inside it can't touch the user's home, the
    bruhs repo (bench/results, bench/tasks*) or any ``protect`` path."""
    root = Path(work_root).resolve()
    guarded = [real_home(), BRUHS_REPO, *protect]
    if root == Path(root.anchor):
        raise ValueError(f"refusing to clean {root}: not a bruhsbench work root")
    for g in guarded:
        g = Path(g).resolve()
        if root.is_relative_to(g) or g.is_relative_to(root):
            raise ValueError(f"refusing to clean {root}: it overlaps {g}")
    if not root.is_dir():
        raise FileNotFoundError(f"no work root at {root}")
    return root


def remove_work_dir(work_root: Path, name: str, *, protect: Sequence[Path] = ()) -> bool:
    """Delete ``<work_root>/<name>`` and its private TMPDIR without following symlinks;
    False if it wasn't there. ``name`` is one path component (a run id, ``_scratch``,
    ...)."""
    if name in ("", ".", "..") or Path(name).name != name:
        raise ValueError(f"not a work-root entry name: {name!r}")
    root = _check_cleanable(work_root, protect)
    remove_private_tmp(root / name)
    if not os.path.lexists(root / name):
        return False
    untrusted.remove(root, name)
    return True


def _remove_private_tmps(root: Path) -> None:
    """The private TMPDIRs of the work root's run dirs and of any grading scratch dir
    left in ``_scratch`` (their owners normally delete those)."""
    for parent in (root, root / "_scratch"):
        if parent.is_symlink() or not parent.is_dir():
            continue
        for entry in os.scandir(parent):
            remove_private_tmp(parent / entry.name)


def remove_work_root(work_root: Path, *, protect: Sequence[Path] = ()) -> bool:
    """Delete the whole work root (every run dir, export, scratch, and their private
    TMPDIRs); False if absent."""
    try:
        root = _check_cleanable(work_root, protect)
    except FileNotFoundError:
        return False
    _remove_private_tmps(root)
    untrusted.remove(root.parent, root.name)
    return True


def mark_workspace_deleted(out_dir: Path) -> None:
    path = Path(out_dir) / "result.json"
    if path.is_file():
        _write_result(Path(out_dir), replace(load_result(path), workspace_deleted=True))


def cleanup_run(out_root: Path, work_root: Path, run_id: str) -> list[str]:
    """Delete run ``run_id``'s work dir (workspace, home, tmp) and record
    ``workspace_deleted`` in its result.json. Returns the paths it couldn't delete ([] on
    success). Never raises for a failed delete (logged): a cleanup problem must not stop
    the matrix."""
    try:
        remove_work_dir(work_root, run_id, protect=[out_root])
    except untrusted.RemoveIncomplete as exc:
        log.warning("%s: cleanup left %d path(s): %s", run_id, len(exc.leftovers), exc)
        return exc.leftovers
    except (OSError, ValueError) as exc:
        log.warning("%s: cleanup failed: %s", run_id, exc)
        return [str(Path(work_root) / run_id)]
    mark_workspace_deleted(Path(out_root) / run_id)
    return []


def active_lock_path(work_root: Path) -> Path:
    """``<work_base>/<results_id>.lock``: next to the work root, never inside it, so
    ``clean --all`` deleting the work root can't delete the lock it holds."""
    return Path(work_root).parent / f"{Path(work_root).name}.lock"


def _open_lock(work_root: Path):
    lock = active_lock_path(work_root)
    lock.parent.mkdir(parents=True, exist_ok=True)
    return open(lock, "a")


@contextmanager
def hold_active(work_root: Path):
    """Shared lock on :func:`active_lock_path` while ``run``/``pipeline``/``capture``/
    ``grade`` use the work root; ``clean --all`` (:func:`exclusive_work_root`) can't
    delete it meanwhile, and they wait while it deletes."""
    with _open_lock(work_root) as f:
        fcntl.flock(f, fcntl.LOCK_SH)
        yield


class WorkRootBusy(Exception):
    """A run/pipeline/capture/grade holds the work root."""


@contextmanager
def exclusive_work_root(work_root: Path):
    """Exclusive lock on :func:`active_lock_path` for the whole of a ``clean --all``;
    :class:`WorkRootBusy` at once if anything holds it."""
    with _open_lock(work_root) as f:
        try:
            fcntl.flock(f, fcntl.LOCK_EX | fcntl.LOCK_NB)
        except BlockingIOError:
            raise WorkRootBusy(str(work_root)) from None
        yield  # closing the file releases the lock


def work_root_active(work_root: Path) -> bool:
    """A ``run``/``pipeline``/``capture``/``grade`` currently holds the work root."""
    try:
        with exclusive_work_root(work_root):
            return False
    except WorkRootBusy:
        return True


# --------------------------------------------------------------------------- contamination

_PATH_END = r"""(?=$|[/\s"'`:;,()\[\]{}<>|])"""
_PATH_TAIL = r"""(?:/[^\s"'`:;,()\[\]{}<>|\\]*)?"""


def _forms(p: Path) -> set[str]:
    return {str(p), str(Path(p).resolve())}


def _within(path: str, roots: Sequence[Path]) -> bool:
    return any(PurePath(path).is_relative_to(form) for r in roots for form in _forms(r))


def scan_contamination(text: str, *, forbidden: Sequence[Path],
                       allowed: Sequence[Path] = ()) -> list[str]:
    """Absolute paths under any ``forbidden`` root (and not under ``allowed``) in ``text``.

    JSON-escaped slashes are undone first; matches stop at quotes, whitespace and
    other delimiters, and a trailing ``.`` is dropped.
    """
    text = text.replace("\\/", "/")
    found: set[str] = set()
    for root in forbidden:
        for form in _forms(root):
            for m in re.finditer(re.escape(form) + _PATH_END + _PATH_TAIL, text):
                path = m.group(0).rstrip(".")
                if not _within(path, allowed):
                    found.add(path)
    return sorted(found)


def session_logs(run_dir: Path) -> list[str]:
    """The CLI's own JSONL session logs in the run's home, relative to ``run_dir``
    (found without following symlinks)."""
    return [p for rel in SESSION_LOG_DIRS
            for p in untrusted.files(run_dir, Path("home") / rel, ".jsonl")]


def _read_untrusted(run_dir: Path, rel: str | Path, skipped: list[str]) -> str:
    """``run_dir/rel`` read safely (R22); "" and noted in ``skipped`` if it isn't a plain
    file there (missing, symlink, FIFO, hard link, ...)."""
    try:
        return untrusted.read_text(run_dir, rel)
    except untrusted.UnsafePath as exc:
        skipped.append(str(exc))
        return ""


def _contamination(spec: RunSpec, stdout: str, stderr: str, run_dir: Path, work_root: Path,
                   env: dict[str, str], skipped: list[str]) -> tuple[bool | None, list[str]]:
    home_dir = real_home()
    forbidden = [home_dir, BRUHS_REPO] + ([spec.task.repo] if spec.task.repo else [])
    # Running a toolchain binary from a PATH dir under ~ (e.g. ~/.bun/bin/bun) is not
    # reading the user's config; everything else under ~ is.
    path_dirs = [Path(p) for p in env.get("PATH", "").split(os.pathsep)
                 if p and Path(p) != home_dir and Path(p).is_absolute()]
    logs = [_read_untrusted(run_dir, rel, skipped) for rel in session_logs(run_dir)]
    found = scan_contamination("\n".join([stdout, stderr, *logs]), forbidden=forbidden,
                               allowed=[work_root, *path_dirs])
    if found:
        return True, found
    tool_level = (tool_event_count(spec.model.cli, stdout) > 0
                  or any(_SESSION_TOOL_RE.search(t) for t in logs))
    return (False if tool_level else None), []


# --------------------------------------------------------------------------- result.json


def _write_result(out_dir: Path, result: RunResult) -> None:
    data = asdict(result)
    for key in ("diff_path", "transcript_path", "workspace"):
        data[key] = str(data[key]) if data[key] is not None else None
    tmp = out_dir / "result.json.tmp"
    tmp.write_text(json.dumps(data, indent=2) + "\n")
    os.replace(tmp, out_dir / "result.json")


def load_result(path: Path) -> RunResult:
    data = json.loads(Path(path).read_text())
    data["diff_path"] = Path(data["diff_path"])
    data["transcript_path"] = Path(data["transcript_path"])
    data["workspace"] = Path(data["workspace"]) if data.get("workspace") else None
    return RunResult(**data)


# --------------------------------------------------------------------------- one run


def _kill_group(pgid: int, sig: int) -> None:
    try:
        os.killpg(pgid, sig)
    except (ProcessLookupError, PermissionError):
        pass


DRAIN_POLL_S = 0.2


def _drain(fd: int, dst, stop: threading.Event) -> None:
    """Copy pipe ``fd`` into ``dst`` until EOF or ``stop`` (polled, so a descendant
    that escaped the process group and still holds the pipe can't block us forever)."""
    while not stop.is_set():
        ready, _, _ = select.select([fd], [], [], DRAIN_POLL_S)
        if not ready:
            continue
        chunk = os.read(fd, 65536)
        if not chunk:
            return
        dst.write(chunk)


def _execute(run_id: str, argv: list[str], cwd: Path, env: dict[str, str], stdout: Path,
             stderr: Path, timeout_s: float, control: RunControl) -> tuple[int, bool, bool]:
    """Run ``argv`` in its own process group; returns (exit code, timed out, orphaned).

    R22: the agent's stdout/stderr are read over pipes and written to ``stdout`` /
    ``stderr`` by the harness, so the agent has no file to reopen and rewrite -- it
    cannot forge its own transcript. After the process group is gone the drains get
    ``KILL_GRACE_S`` to reach EOF; a ``setsid()`` descendant still holding the pipes
    then only loses its remaining output (``orphaned`` = True), it can't hang the run.
    """
    with open(stdout, "wb") as out, open(stderr, "wb") as err:
        proc = control.spawn(run_id, lambda: subprocess.Popen(
            argv, cwd=cwd, env=env, stdin=subprocess.DEVNULL, stdout=subprocess.PIPE,
            stderr=subprocess.PIPE, start_new_session=True))
        stop = threading.Event()
        pipes = [(proc.stdout, out), (proc.stderr, err)]
        readers = [threading.Thread(target=_drain, args=(src.fileno(), dst, stop), daemon=True)
                   for src, dst in pipes]
        for t in readers:
            t.start()
        timed_out = orphaned = False
        try:
            proc.wait(timeout=timeout_s)
        except subprocess.TimeoutExpired:
            timed_out = True
            _kill_group(proc.pid, signal.SIGTERM)
            try:
                proc.wait(timeout=KILL_GRACE_S)
            except subprocess.TimeoutExpired:
                _kill_group(proc.pid, signal.SIGKILL)
                proc.wait()
        finally:
            # whatever the agent left running (dev servers, watchers) goes too
            _kill_group(proc.pid, signal.SIGKILL)
            deadline = time.monotonic() + KILL_GRACE_S
            for t in readers:
                t.join(timeout=max(0.0, deadline - time.monotonic()))
            if any(t.is_alive() for t in readers):
                orphaned = True
                stop.set()
                for t in readers:
                    t.join(timeout=DRAIN_POLL_S * 5)
            for src, _ in pipes:
                src.close()
            control.release(proc)
    if control.stopped.is_set():
        raise RunInterrupted(run_id)
    return proc.returncode, timed_out, orphaned


def _write_diff(workspace: Path, dest: Path) -> bool:
    try:  # R22: agent-controlled repo config; hardened and sandboxed
        untrusted.git(workspace, "add", "-A")
        diff = untrusted.git(workspace, "diff", "--cached", "--binary", BASE_TAG).stdout
    except (subprocess.CalledProcessError, OSError, untrusted.UnsafePath) as exc:
        log.warning("diff failed in %s: %s", workspace, exc)
        dest.write_bytes(b"")
        return False
    dest.write_bytes(diff)
    return True


def run_one(
    spec: RunSpec,
    out_root: Path,
    *,
    timeout_s: int = DEFAULT_TIMEOUT_S,
    bruhs_src: Path | None = None,
    work_root: Path | None = None,
    command_override: CommandOverride | None = None,
    claude_slots: threading.Semaphore | None = None,
    control: RunControl | None = None,
    free_gb_at_start: float | None = None,
) -> RunResult:
    """Run ``spec`` from scratch and write its artifacts to ``out_root/<run_id>/``.

    Raises :class:`AuthAbort` (and writes no result.json) if the CLI isn't logged in,
    and :class:`RunInterrupted` if ``control`` was stopped while the run was live.
    """
    control = control or RunControl()
    out_root = Path(out_root)
    work_root = _check_outside_home(work_root) if work_root else default_work_root(out_root)
    if bruhs_src is None:
        bruhs_src = ensure_bruhs_export(work_root, git_head(BRUHS_REPO))
    if free_gb_at_start is None:
        free_gb_at_start = min(free_gb(work_root), free_gb(out_root))
    cli = spec.model.cli
    out_dir = out_root / spec.run_id
    run_dir = work_root / spec.run_id
    if os.path.lexists(run_dir):  # a partial earlier attempt; symlink-safe removal
        remove_work_dir(work_root, spec.run_id, protect=[out_root])
    remove_private_tmp(run_dir)  # an earlier attempt's TMPDIR, even without its run dir
    if out_dir.exists():
        shutil.rmtree(out_dir)
    for d in (out_dir, run_dir):
        d.mkdir(parents=True)
    workspace = run_dir / "workspace"
    transcript = out_dir / "transcript.jsonl"
    diff_path = out_dir / "diff.patch"
    base = RunResult(spec.run_id, "ok", 0.0, None, None, None, None, "", diff_path,
                     transcript, workspace=workspace,
                     free_gb_at_start=round(free_gb_at_start, 1))

    try:
        prepare_workspace(spec.task, spec.arm, workspace, scripts_dir=bruhs_src / "scripts")
    except SetupFailed as exc:
        (out_dir / "stderr.txt").write_text(f"{exc}\n")
        for p in (transcript, diff_path, out_dir / "final.txt"):
            p.write_text("")
        result = replace(base, status="setup_failed")
        _write_result(out_dir, result)
        return result

    env = build_home(cli, spec.arm, run_dir, bruhs_src)
    argv = build_command(spec.model, spec.arm, spec.task.prompt, workspace,
                         Path(env["HOME"]), run_dir)
    if command_override is not None:
        argv = command_override(spec, argv)
    # R19/R21: no real home, no other run or root under the work base, private TMPDIR
    argv = wrap(argv, writable=[run_dir], denied=[work_root])
    env = private_tmp(env, run_dir)

    # R22: the agent's stdout/stderr are drained over pipes straight into the results
    # dir (outside the sandbox); there is no stdout file in the run dir for the agent to
    # reopen and forge.
    with claude_slots if (cli == "claude" and claude_slots is not None) else nullcontext():
        start = time.monotonic()
        code, timed_out, orphaned = _execute(spec.run_id, argv, workspace, env, transcript,
                                             out_dir / "stderr.txt", timeout_s, control)
        wall_s = time.monotonic() - start

    unsafe: list[str] = []
    stdout = transcript.read_text(errors="replace")
    stderr = (out_dir / "stderr.txt").read_text(errors="replace")
    if not timed_out and is_auth_failure(cli, stdout, stderr, code):
        raise AuthAbort(f"{spec.run_id}: {cli} is not authenticated (exit {code}); "
                        f"log in and rerun to resume. stderr: {stderr[-500:]}")

    diff_ok = _write_diff(workspace, diff_path)
    parsed = parse_output(cli, stdout)
    final = parsed.final_message
    if os.path.lexists(run_dir / "final.txt"):  # codex -o; agent-writable, read safely
        final = _read_untrusted(run_dir, "final.txt", unsafe) or final
    (out_dir / "final.txt").write_text(final)

    status = "timeout" if timed_out else ("ok" if code == 0 and diff_ok else "error")
    contaminated, contamination = _contamination(spec, stdout, stderr, run_dir, work_root,
                                                 env, unsafe)
    result = replace(
        base, status=status, wall_s=round(wall_s, 3), turns=parsed.turns,
        input_tokens=parsed.input_tokens, output_tokens=parsed.output_tokens,
        cost_usd=parsed.cost_usd, final_message=final,
        contaminated=contaminated, contamination=contamination, unsafe_files=unsafe,
        orphaned_output=orphaned,
    )
    _write_result(out_dir, result)
    return result


# --------------------------------------------------------------------------- matrix


def matrix_order(tasks: Sequence[Task], models: Sequence[ModelSpec], arms: Sequence[Arm],
                 repeats: int, *, seed: int = DEFAULT_SEED) -> list[RunSpec]:
    """Every run, shuffled by (task, model, repeat) unit with each unit's arms adjacent
    (in random order), so both arms of a unit run at about the same time."""
    rng = random.Random(seed)
    units = [(t, m, r) for t in tasks for m in models for r in range(1, repeats + 1)]
    rng.shuffle(units)
    order: list[RunSpec] = []
    for task, model, repeat in units:
        unit_arms = list(arms)
        rng.shuffle(unit_arms)
        order += [RunSpec(task, model, arm, repeat) for arm in unit_arms]
    return order


def cli_version(cli: Cli) -> str:
    try:
        proc = subprocess.run([cli, "--version"], capture_output=True, text=True, timeout=60,
                              stdin=subprocess.DEVNULL)
    except (OSError, subprocess.TimeoutExpired) as exc:
        return f"unavailable: {exc}"
    return (proc.stdout or proc.stderr).strip()


def _now() -> str:
    return datetime.now(timezone.utc).isoformat(timespec="seconds")


def _record_matrix(out_root: Path, commit: str, tasks: Sequence[Task],
                   models: Sequence[ModelSpec], arms: Sequence[Arm], repeats: int,
                   seed: int, timeout_s: int, record: dict | None = None) -> None:
    """Write (or, on resume, check and extend) matrix.json. ``record`` (the task hashes
    and freeze status) is stored with this start; an ``allow_unfrozen`` start also
    marks the whole matrix ``allow_unfrozen``."""
    path = out_root / "matrix.json"
    versions = {cli: cli_version(cli) for cli in dict.fromkeys(m.cli for m in models)}
    start = {"at": _now(), "cli_versions": versions, **(record or {})}
    pinned = {"bruhs_commit": commit, "seed": seed, "repeats": repeats,
              "models": [asdict(m) for m in models], "tasks": sorted(t.id for t in tasks)}
    if path.exists():
        meta = json.loads(path.read_text())
        changed = [k for k, v in pinned.items()
                   if (sorted(meta.get(k, [])) if k == "tasks" else meta.get(k)) != v]
        if changed:
            detail = "; ".join(f"{k}: matrix.json has {meta.get(k)!r}, now {pinned[k]!r}"
                               for k in changed)
            raise ValueError(f"refusing to resume {out_root}: the matrix changed ({detail}). "
                             "Use a new results dir for a different matrix.")
        meta["starts"].append(start)
    else:
        meta = {**pinned, "arms": list(arms), "timeout_s": timeout_s,
                "cli_versions": versions, "starts": [start]}
    if start.get("allow_unfrozen"):
        meta["allow_unfrozen"] = True
    path.write_text(json.dumps(meta, indent=2) + "\n")


def _exclude_failed_setup(tasks: Sequence[Task], out_root: Path, work_root: Path,
                          scripts_dir: Path) -> list[Task]:
    scratch = work_root / "_setup-check"
    kept, excluded = [], []
    for task in tasks:
        if check_task_setup(task, scratch, scripts_dir):
            kept.append(task)
        else:
            log.warning("excluding %s from both arms: setup failed", task.id)
            excluded.append({"task_id": task.id, "reason": "setup_failed"})
    shutil.rmtree(scratch, ignore_errors=True)
    (out_root / "excluded.json").write_text(json.dumps(excluded, indent=2) + "\n")
    return kept


def run_matrix(
    tasks: Sequence[Task],
    models: Sequence[ModelSpec],
    arms: Sequence[Arm],
    repeats: int,
    out_root: Path,
    *,
    parallel: int = DEFAULT_PARALLEL,
    claude_parallel: int = CLAUDE_MAX_PARALLEL,
    bruhs_commit: str = "HEAD",
    seed: int = DEFAULT_SEED,
    timeout_s: int = DEFAULT_TIMEOUT_S,
    work_root: Path | None = None,
    command_override: CommandOverride | None = None,
    disk_guard: DiskGuard | None = None,
    post_run: Callable[[RunSpec, RunResult], None] | None = None,
    record: dict | None = None,
) -> list[RunResult]:
    """Run every (task, model, arm, repeat), skipping runs that already have result.json.

    Returns results in matrix order. A harness exception inside a run is recorded as
    ``status="error"`` and the matrix goes on. On an auth failure or an interrupt, queued
    runs are cancelled, every live agent process group is killed (those runs write no
    result.json and are redone on resume), and the exception is re-raised. With claude in
    ``models`` and no claude token, :class:`ClaudeAuthMissing` is raised up front.

    Disk: before each run starts, ``disk_guard`` (default: a :class:`DiskGuard` on the
    work and results roots) must see enough free space. If it doesn't come, no further
    run starts, live runs finish normally, and :class:`DiskLow` is raised at the end
    (resumable).

    ``post_run(spec, result)`` (the pipeline's capture -> grade -> cleanup) runs in the
    same worker right after each run, and for already-finished runs on resume; it may
    raise :class:`DiskLow` to stop the matrix the same way. Its other exceptions are
    logged and the matrix goes on.

    ``record`` is stored with this start in matrix.json (the CLI passes the task hashes
    and freeze status).
    """
    check_tmp_base()  # R37: raises TmpDirTooLong before anything starts
    if any(m.cli == "claude" for m in models):
        claude_auth()  # R20: raises ClaudeAuthMissing before any process starts
    out_root = Path(out_root)
    out_root.mkdir(parents=True, exist_ok=True)
    work_root = _check_outside_home(work_root) if work_root else default_work_root(out_root)
    with hold_active(work_root):  # `clean --all` refuses while this is held
        return _run_matrix(tasks, models, arms, repeats, out_root, work_root,
                           parallel=parallel, claude_parallel=claude_parallel,
                           bruhs_commit=bruhs_commit, seed=seed, timeout_s=timeout_s,
                           command_override=command_override, disk_guard=disk_guard,
                           post_run=post_run, record=record)


def _run_matrix(tasks, models, arms, repeats, out_root: Path, work_root: Path, *,
                parallel, claude_parallel, bruhs_commit, seed, timeout_s,
                command_override, disk_guard, post_run, record) -> list[RunResult]:
    guard = disk_guard or DiskGuard([work_root, out_root])
    guard.wait("starting the matrix")  # nothing runs yet: raises DiskLow at once if low
    commit = git_head(BRUHS_REPO, bruhs_commit)
    _record_matrix(out_root, commit, tasks, models, arms, repeats, seed, timeout_s, record)
    bruhs_src = ensure_bruhs_export(work_root, commit)
    kept = _exclude_failed_setup(tasks, out_root, work_root, bruhs_src / "scripts")

    specs = matrix_order(kept, models, arms, repeats, seed=seed)
    results: dict[str, RunResult] = {}
    todo = []
    for spec in specs:
        done = out_root / spec.run_id / "result.json"
        if done.is_file():
            results[spec.run_id] = load_result(done)
            if post_run is not None:
                todo.append(spec)  # finished; only its post-processing may be left
        else:
            todo.append(spec)
    log.info("%d runs: %d done, %d to run", len(specs), len(results),
             sum(s.run_id not in results for s in specs))

    claude_slots = threading.BoundedSemaphore(claude_parallel)
    control = RunControl()
    draining = threading.Event()  # low disk: start nothing new, let live runs finish
    low: list[DiskLow] = []

    def stop_for_disk(exc: DiskLow) -> None:
        if not draining.is_set():
            log.error("%s", exc)
        low.append(exc)
        draining.set()

    def run(spec: RunSpec) -> RunResult | None:
        try:
            free = guard.wait(spec.run_id)
        except DiskLow as exc:
            stop_for_disk(exc)
            return None
        try:
            return run_one(spec, out_root, timeout_s=timeout_s, bruhs_src=bruhs_src,
                           work_root=work_root, command_override=command_override,
                           claude_slots=claude_slots, control=control,
                           free_gb_at_start=free)
        except RunInterrupted:
            return None
        except (AuthAbort, ClaudeAuthMissing):
            control.stopped.set()  # before this worker can pick up the next run
            raise
        except Exception:
            log.exception("%s: harness error, recorded as status=error", spec.run_id)
            return _record_error(spec, out_root, work_root, traceback.format_exc())

    def work(spec: RunSpec) -> RunResult | None:
        if control.stopped.is_set() or draining.is_set():
            return None
        with guard.job():
            res = results.get(spec.run_id) or run(spec)
            if res is None or post_run is None or control.stopped.is_set():
                return res
            try:
                post_run(spec, res)
            except DiskLow as exc:
                stop_for_disk(exc)
            except Exception:
                log.exception("%s: post-processing failed (run kept; rerun to retry)",
                              spec.run_id)
            return res

    pool = ThreadPoolExecutor(max_workers=max(1, parallel))
    try:
        futures = [pool.submit(work, spec) for spec in todo]
        for fut in as_completed(futures):
            res = fut.result()
            if res is not None:
                results[res.run_id] = res
                log.info("%s: %s (%.0fs)", res.run_id, res.status, res.wall_s)
    except BaseException:  # AuthAbort, KeyboardInterrupt, ...
        control.kill_all()
        pool.shutdown(wait=False, cancel_futures=True)
        raise
    pool.shutdown(wait=True)
    if low:
        raise low[0]
    return [results[s.run_id] for s in specs]


def _record_error(spec: RunSpec, out_root: Path, work_root: Path, tb: str) -> RunResult:
    out_dir = out_root / spec.run_id
    out_dir.mkdir(parents=True, exist_ok=True)
    paths = {name: out_dir / name for name in ("diff.patch", "transcript.jsonl", "final.txt")}
    for p in paths.values():
        if not p.exists():
            p.write_text("")
    workspace = work_root / spec.run_id / "workspace"
    result = RunResult(spec.run_id, "error", 0.0, None, None, None, None, "",
                       paths["diff.patch"], paths["transcript.jsonl"], contaminated=None,
                       workspace=workspace if workspace.is_dir() else None, error=tb)
    _write_result(out_dir, result)
    return result
