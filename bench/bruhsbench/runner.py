"""Execute benchmark runs: one (task, model, arm, repeat) at a time, or the whole matrix.

Layout (Ruling R10). Everything an agent touches lives in a *work root* outside the
user's home (``$BRUHSBENCH_WORK`` or ``/private/tmp/bruhsbench``, plus a per-results
id): the pinned bruhs export at ``<work>/_bruhs/<commit>/`` and, per run,
``<work>/<run_id>/{home,workspace,stdout,stderr,final.txt}``. The results dir
``<out_root>/<run_id>/`` only receives copies: ``result.json``, ``transcript.json[l]``
(raw CLI stdout), ``stderr.txt``, ``diff.patch``, ``final.txt``. ``result.json`` records
the workspace's absolute path for the graders and is written last (atomically), so a
run dir without it is partial and is redone on resume.

``out_root/matrix.json`` pins the bruhs commit, CLI versions, models, repeats and seed;
``out_root/excluded.json`` lists tasks whose setup failed (excluded from both arms).
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
from collections.abc import Callable, Sequence
from concurrent.futures import ThreadPoolExecutor, as_completed
from contextlib import nullcontext
from dataclasses import asdict, replace
from datetime import datetime, timezone
from pathlib import Path, PurePath

from .agents import build_command, is_auth_failure, parse_output
from .homes import build_home, export_bruhs
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
TRANSCRIPT_EXT: dict[str, str] = {"claude": "json", "codex": "jsonl", "grok": "json"}

# (spec, argv the real CLI would get) -> argv to run instead; tests install a fake agent
CommandOverride = Callable[[RunSpec, list[str]], list[str]]


class AuthAbort(Exception):
    """A CLI reported it isn't authenticated; the matrix stops instead of scoring zeros."""


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


def _contamination(spec: RunSpec, texts: Sequence[str], work_root: Path,
                   env: dict[str, str]) -> list[str]:
    home = Path.home()
    forbidden = [home, BRUHS_REPO] + ([spec.task.repo] if spec.task.repo else [])
    # Running a toolchain binary from a PATH dir under ~ (e.g. ~/.bun/bin/bun) is not
    # reading the user's config; everything else under ~ is.
    path_dirs = [Path(p) for p in env.get("PATH", "").split(os.pathsep)
                 if p and Path(p) != home and Path(p).is_absolute()]
    allowed = [work_root, *path_dirs]
    return scan_contamination("\n".join(texts), forbidden=forbidden, allowed=allowed)


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


def _execute(argv: list[str], cwd: Path, env: dict[str, str], stdout: Path, stderr: Path,
             timeout_s: float) -> tuple[int, bool]:
    """Run ``argv`` in its own process group; returns (exit code, timed out)."""
    with open(stdout, "wb") as out, open(stderr, "wb") as err:
        proc = subprocess.Popen(argv, cwd=cwd, env=env, stdin=subprocess.DEVNULL,
                                stdout=out, stderr=err, start_new_session=True)
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
    return proc.returncode, timed_out


def _write_diff(workspace: Path, dest: Path) -> bool:
    try:
        subprocess.run([*GIT, "add", "-A"], cwd=workspace, check=True, capture_output=True)
        diff = subprocess.run([*GIT, "diff", "--cached", BASE_TAG], cwd=workspace,
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
) -> RunResult:
    """Run ``spec`` from scratch and write its artifacts to ``out_root/<run_id>/``.

    Raises :class:`AuthAbort` (and writes no result.json) if the CLI isn't logged in.
    """
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
    transcript = out_dir / f"transcript.{TRANSCRIPT_EXT[cli]}"
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

    with claude_slots if (cli == "claude" and claude_slots is not None) else nullcontext():
        start = time.monotonic()
        code, timed_out = _execute(argv, workspace, env, run_dir / "stdout",
                                   run_dir / "stderr", timeout_s)
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
    contamination = _contamination(spec, [stdout, stderr], work_root, env)
    result = replace(
        base, status=status, wall_s=round(wall_s, 3), turns=parsed.turns,
        input_tokens=parsed.input_tokens, output_tokens=parsed.output_tokens,
        cost_usd=parsed.cost_usd, final_message=final,
        contaminated=bool(contamination), contamination=contamination,
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
    if path.exists():
        meta = json.loads(path.read_text())
        if (meta["bruhs_commit"], meta["seed"]) != (commit, seed):
            raise ValueError(f"{path} was started with bruhs {meta['bruhs_commit']} seed "
                             f"{meta['seed']}; refusing to resume with {commit} seed {seed}")
        meta["starts"].append(start)
    else:
        meta = {
            "bruhs_commit": commit, "seed": seed, "repeats": repeats, "arms": list(arms),
            "models": [asdict(m) for m in models], "tasks": [t.id for t in tasks],
            "timeout_s": timeout_s, "cli_versions": versions, "starts": [start],
        }
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

    Returns results in matrix order. On an auth failure no further runs start and
    :class:`AuthAbort` is raised once in-flight runs finish.
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

    stop = threading.Event()
    claude_slots = threading.BoundedSemaphore(claude_parallel)

    def work(spec: RunSpec) -> RunResult | None:
        if stop.is_set():
            return None
        try:
            return run_one(spec, out_root, timeout_s=timeout_s, bruhs_src=bruhs_src,
                           work_root=work_root, command_override=command_override,
                           claude_slots=claude_slots)
        except BaseException:
            stop.set()  # before this worker can pick up the next run
            raise

    first_error: BaseException | None = None
    with ThreadPoolExecutor(max_workers=max(1, parallel)) as pool:
        futures = [pool.submit(work, spec) for spec in todo]
        for fut in as_completed(futures):
            try:
                res = fut.result()
            except BaseException as exc:  # noqa: BLE001 -- re-raised below
                first_error = first_error or exc
                continue
            if res is not None:
                results[res.run_id] = res
                log.info("%s: %s (%.0fs)", res.run_id, res.status, res.wall_s)
    if first_error is not None:
        raise first_error
    return [results[s.run_id] for s in specs]
