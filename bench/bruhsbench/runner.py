"""Execute benchmark runs: one (task, model, arm, repeat) at a time, or the whole matrix.

Layout (Ruling R10). Everything an agent touches lives in a *work root* outside the
user's home (``$BRUHSBENCH_WORK`` or ``/private/tmp/bruhsbench``, plus a per-results
id): the pinned bruhs export at ``<work>/_bruhs/<commit>/`` and, per run,
``<work>/<run_id>/{home,workspace,stdout,stderr,final.txt}``. The results dir
``<out_root>/<run_id>/`` only receives copies: ``result.json``, ``transcript.jsonl``
(raw CLI stdout, streaming JSON for all three CLIs), ``stderr.txt``, ``diff.patch``, ``final.txt``. ``result.json`` records
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

import hashlib
import json
import logging
import os
import random
import re
import shutil
import signal
import subprocess
import threading
import time
import traceback
from collections.abc import Callable, Sequence
from concurrent.futures import ThreadPoolExecutor, as_completed
from contextlib import nullcontext
from dataclasses import asdict, replace
from datetime import datetime, timezone
from pathlib import Path, PurePath

from .agents import build_command, is_auth_failure, parse_output, tool_event_count
from .homes import build_home, export_bruhs
from .sandbox import wrap
from .types import Arm, Cli, ModelSpec, RunResult, RunSpec, Task
from .workspace import BASE_TAG, GIT, SetupFailed, check_task_setup, prepare_workspace

log = logging.getLogger(__name__)

BRUHS_REPO = Path(__file__).resolve().parents[2]
DEFAULT_WORK_BASE = Path("/private/tmp/bruhsbench")
DEFAULT_TIMEOUT_S = 45 * 60
DEFAULT_PARALLEL = 6
CLAUDE_MAX_PARALLEL = 3  # R11: parallel claude runs share one keychain login
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
    if Path(path).resolve().is_relative_to(Path.home().resolve()):
        raise ValueError(f"work root {path} is inside the user's home; the CLIs would "
                         "discover ~/ config from its ancestors (set BRUHSBENCH_WORK)")
    return Path(path)


def default_work_root(out_root: Path) -> Path:
    base = Path(os.environ.get("BRUHSBENCH_WORK") or DEFAULT_WORK_BASE)
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


def session_logs(home: Path) -> list[Path]:
    """The CLI's own JSONL session logs written inside the run's home."""
    return sorted(p for rel in SESSION_LOG_DIRS if (home / rel).is_dir()
                  for p in (home / rel).rglob("*.jsonl"))


def _contamination(spec: RunSpec, stdout: str, stderr: str, home: Path, work_root: Path,
                   env: dict[str, str]) -> tuple[bool | None, list[str]]:
    real_home = Path.home()
    forbidden = [real_home, BRUHS_REPO] + ([spec.task.repo] if spec.task.repo else [])
    # Running a toolchain binary from a PATH dir under ~ (e.g. ~/.bun/bin/bun) is not
    # reading the user's config; everything else under ~ is.
    path_dirs = [Path(p) for p in env.get("PATH", "").split(os.pathsep)
                 if p and Path(p) != real_home and Path(p).is_absolute()]
    logs = [p.read_text(errors="replace") for p in session_logs(home)]
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


def _execute(run_id: str, argv: list[str], cwd: Path, env: dict[str, str], stdout: Path,
             stderr: Path, timeout_s: float, control: RunControl) -> tuple[int, bool]:
    """Run ``argv`` in its own process group; returns (exit code, timed out)."""
    with open(stdout, "wb") as out, open(stderr, "wb") as err:
        proc = control.spawn(run_id, lambda: subprocess.Popen(
            argv, cwd=cwd, env=env, stdin=subprocess.DEVNULL, stdout=out, stderr=err,
            start_new_session=True))
        timed_out = False
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
            control.release(proc)
    if control.stopped.is_set():
        raise RunInterrupted(run_id)
    return proc.returncode, timed_out


def _write_diff(workspace: Path, dest: Path) -> bool:
    try:
        subprocess.run([*GIT, "add", "-A"], cwd=workspace, check=True, capture_output=True)
        diff = subprocess.run([*GIT, "diff", "--cached", "--binary", BASE_TAG], cwd=workspace,
                              check=True, capture_output=True).stdout
    except (subprocess.CalledProcessError, OSError) as exc:
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
    cli = spec.model.cli
    out_dir = out_root / spec.run_id
    run_dir = work_root / spec.run_id
    for d in (out_dir, run_dir):
        if d.exists():
            shutil.rmtree(d)
        d.mkdir(parents=True)
    workspace = run_dir / "workspace"
    transcript = out_dir / "transcript.jsonl"
    diff_path = out_dir / "diff.patch"
    base = RunResult(spec.run_id, "ok", 0.0, None, None, None, None, "", diff_path,
                     transcript, workspace=workspace)

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
    argv = wrap(argv, writable=[run_dir])  # R19: no access to the real home

    with claude_slots if (cli == "claude" and claude_slots is not None) else nullcontext():
        start = time.monotonic()
        code, timed_out = _execute(spec.run_id, argv, workspace, env, run_dir / "stdout",
                                   run_dir / "stderr", timeout_s, control)
        wall_s = time.monotonic() - start

    shutil.copyfile(run_dir / "stdout", transcript)
    shutil.copyfile(run_dir / "stderr", out_dir / "stderr.txt")
    stdout = transcript.read_text(errors="replace")
    stderr = (out_dir / "stderr.txt").read_text(errors="replace")
    if not timed_out and is_auth_failure(cli, stdout, stderr, code):
        raise AuthAbort(f"{spec.run_id}: {cli} is not authenticated (exit {code}); "
                        f"log in and rerun to resume. stderr: {stderr[-500:]}")

    diff_ok = _write_diff(workspace, diff_path)
    parsed = parse_output(cli, stdout)
    final = parsed.final_message
    cli_final = run_dir / "final.txt"  # codex -o
    if cli_final.is_file():
        final = cli_final.read_text(errors="replace") or final
    (out_dir / "final.txt").write_text(final)

    status = "timeout" if timed_out else ("ok" if code == 0 and diff_ok else "error")
    contaminated, contamination = _contamination(spec, stdout, stderr, Path(env["HOME"]),
                                                 work_root, env)
    result = replace(
        base, status=status, wall_s=round(wall_s, 3), turns=parsed.turns,
        input_tokens=parsed.input_tokens, output_tokens=parsed.output_tokens,
        cost_usd=parsed.cost_usd, final_message=final,
        contaminated=contaminated, contamination=contamination,
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
                   seed: int, timeout_s: int) -> None:
    path = out_root / "matrix.json"
    versions = {cli: cli_version(cli) for cli in dict.fromkeys(m.cli for m in models)}
    start = {"at": _now(), "cli_versions": versions}
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
) -> list[RunResult]:
    """Run every (task, model, arm, repeat), skipping runs that already have result.json.

    Returns results in matrix order. A harness exception inside a run is recorded as
    ``status="error"`` and the matrix goes on. On an auth failure or an interrupt, queued
    runs are cancelled, every live agent process group is killed (those runs write no
    result.json and are redone on resume), and the exception is re-raised.
    """
    out_root = Path(out_root)
    out_root.mkdir(parents=True, exist_ok=True)
    work_root = _check_outside_home(work_root) if work_root else default_work_root(out_root)
    commit = git_head(BRUHS_REPO, bruhs_commit)
    _record_matrix(out_root, commit, tasks, models, arms, repeats, seed, timeout_s)
    bruhs_src = ensure_bruhs_export(work_root, commit)
    kept = _exclude_failed_setup(tasks, out_root, work_root, bruhs_src / "scripts")

    specs = matrix_order(kept, models, arms, repeats, seed=seed)
    results: dict[str, RunResult] = {}
    todo = []
    for spec in specs:
        done = out_root / spec.run_id / "result.json"
        if done.is_file():
            results[spec.run_id] = load_result(done)
        else:
            todo.append(spec)
    log.info("%d runs: %d done, %d to run", len(specs), len(results), len(todo))

    claude_slots = threading.BoundedSemaphore(claude_parallel)
    control = RunControl()

    def work(spec: RunSpec) -> RunResult | None:
        if control.stopped.is_set():
            return None
        try:
            return run_one(spec, out_root, timeout_s=timeout_s, bruhs_src=bruhs_src,
                           work_root=work_root, command_override=command_override,
                           claude_slots=claude_slots, control=control)
        except RunInterrupted:
            return None
        except AuthAbort:
            control.stopped.set()  # before this worker can pick up the next run
            raise
        except Exception:
            log.exception("%s: harness error, recorded as status=error", spec.run_id)
            return _record_error(spec, out_root, work_root, traceback.format_exc())

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
