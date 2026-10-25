"""``bruhsbench``: run -> capture -> grade -> judge -> spotcheck -> report (Ruling R24).

capture comes before grade because the checklist judges see each ui/copy run's
screenshots (``<run_dir>/screens``).

Every stage reads and writes plain files under one results dir (``--results``, default
``bench/results/full``; ``--pilot`` -> ``bench/results/pilot``) and skips work whose
outputs already exist, so any stage can be rerun or resumed; ``--force`` redoes it.
Held-out tasks (``tasks-heldout/`` or ``heldout = true``) are refused unless
``--heldout`` is given (rulings R1/R2).

``pipeline`` does run -> capture -> grade -> cleanup per run as each run finishes (still
parallel across runs), deleting the run's work dir (workspace, home) once it is captured
and graded, so a full matrix fits on disk; ``clean`` does the same deletion after the
per-stage commands. Every stage that starts a run, capture or grade first checks free
disk (``$BRUHSBENCH_MIN_FREE_GB``) and stops cleanly, resumable, when it is short.
"""

from __future__ import annotations

import argparse
import logging
import shutil
import sys
import tomllib
from collections.abc import Callable, Iterable
from concurrent.futures import ThreadPoolExecutor
from datetime import date
from pathlib import Path

from .tasks import BENCH_DIR, load_all_tasks
from .types import MODELS, ModelSpec, Task

RESULTS_DIR = BENCH_DIR / "results"
PILOT_FILE = BENCH_DIR / "pilot.toml"
PUBLISHED_DIR = RESULTS_DIR / "published"
PAIRWISE = ("ui", "copy")
GRADE_FILES = ("commands", "scope", "checklist", "audit", "honesty")

log = logging.getLogger("bruhsbench")


class CliError(Exception):
    pass


# --------------------------------------------------------------------------- helpers


def results_root(args: argparse.Namespace) -> Path:
    if args.results:
        return Path(args.results).resolve()
    return RESULTS_DIR / ("pilot" if getattr(args, "pilot", False) else "full")


def pilot_task_ids(path: Path = PILOT_FILE) -> list[str]:
    if not path.is_file():
        raise CliError(f"{path} not found: list the pilot tasks there as tasks = [\"id\", ...]")
    ids = tomllib.loads(path.read_text()).get("tasks", [])
    if not ids:
        raise CliError(f"{path} lists no tasks")
    return list(ids)


def select_tasks(all_tasks: list[Task], ids: list[str] | None, *, heldout: bool) -> list[Task]:
    """The tasks to run. Named held-out tasks need ``heldout``; with no ids, all
    non-held-out tasks (or, with ``heldout``, only the held-out set)."""
    by_id = {t.id: t for t in all_tasks}
    if ids:
        unknown = [i for i in ids if i not in by_id]
        if unknown:
            raise CliError(f"unknown task ids: {unknown}")
        chosen = [by_id[i] for i in ids]
        sealed = [t.id for t in chosen if t.heldout]
        if sealed and not heldout:
            raise CliError(f"refusing held-out tasks {sealed} without --heldout: they stay "
                           "sealed until bruhs changes in response to results")
        return chosen
    return [t for t in all_tasks if t.heldout == heldout]


def select_models(names: list[str] | None) -> list[ModelSpec]:
    if not names:
        return list(MODELS)
    out = []
    for n in names:
        m = next((m for m in MODELS if n in (m.cli, m.model)), None)
        if m is None:
            raise CliError(f"unknown model {n!r}; choose from "
                           f"{[m.cli for m in MODELS] + [m.model for m in MODELS]}")
        out.append(m)
    return out


def run_dirs(root: Path) -> list[Path]:
    return sorted(p.parent for p in root.glob("*/result.json"))


def _task_index(include_heldout: bool) -> dict[str, Task]:
    return {t.id: t for t in load_all_tasks() if include_heldout or not t.heldout}


def _runs_with_tasks(root: Path, args) -> list[tuple[Path, Task]]:
    """Run dirs under ``root`` with their task (held-out runs need --heldout)."""
    from .score import parse_run_id

    tasks = _task_index(args.heldout)
    out, skipped = [], set()
    for d in run_dirs(root):
        try:
            task_id = parse_run_id(d.name)[0]
        except ValueError:
            continue
        if task_id in tasks:
            out.append((d, tasks[task_id]))
        else:
            skipped.add(task_id)
    if skipped:
        log.warning("skipping runs of unknown or held-out tasks: %s", sorted(skipped))
    return out


def _parallel(fn: Callable, items: Iterable, workers: int) -> None:
    items = list(items)
    with ThreadPoolExecutor(max_workers=max(1, workers)) as pool:
        for fut in [pool.submit(fn, *it) for it in items]:
            fut.result()


DISK_LOW_EXIT = 4


def _disk_guard(root: Path):
    from .runner import DiskGuard, default_work_root

    try:
        return DiskGuard([default_work_root(root), root])
    except ValueError as exc:  # e.g. a non-numeric BRUHSBENCH_MIN_FREE_GB
        raise CliError(str(exc)) from None


def _guarded_parallel(fn: Callable, items: Iterable, workers: int, guard, what: str) -> int:
    """:func:`_parallel` with a disk check before each item (``item[0]`` is its run dir);
    on low disk nothing new starts, live items finish, and DISK_LOW_EXIT is returned."""
    from .runner import DiskLow

    low: list[DiskLow] = []

    def one(*item) -> None:
        if low:
            return
        with guard.job():
            try:
                guard.wait(f"{what} {item[0].name}")
            except DiskLow as exc:
                low.append(exc)
                return
            fn(*item)

    _parallel(one, items, workers)
    if low:
        print(f"stopped: {low[0]}", file=sys.stderr)
        return DISK_LOW_EXIT
    return 0


def _claude_guidance() -> str:
    from .homes import DEFAULT_ENV_FILE

    return (f"claude needs a token: run `claude setup-token` and put\n"
            f"  CLAUDE_CODE_OAUTH_TOKEN=<token>\ninto {DEFAULT_ENV_FILE} (gitignored). "
            "The keychain login is never used.")


# --------------------------------------------------------------------------- stages


def cmd_probe(args) -> int:
    """Isolation probe for every cli x arm: each sees exactly what its arm should."""
    from .homes import (ClaudeAuthMissing, LeakError, assert_arms_match, assert_isolated,
                        build_home, export_bruhs, probe_isolation)
    from .runner import BRUHS_REPO
    from .sandbox import work_base

    base = work_base() / "_probe"
    shutil.rmtree(base, ignore_errors=True)
    base.mkdir(parents=True)
    bruhs_src = export_bruhs(BRUHS_REPO, "HEAD", base / "_bruhs")
    failed = False
    for spec in select_models(args.models):
        seen = {}
        for arm in ("bare", "bruhs"):
            label = f"{spec.cli}/{arm}"
            try:
                env = build_home(spec.cli, arm, base / f"{spec.cli}-{arm}", bruhs_src)
                seen[arm] = probe_isolation(spec.cli, arm, env)
                assert_isolated(seen[arm], arm)
                print(f"PASS  {label}: skills={sorted(seen[arm].skills)} "
                      f"mcps={sorted(seen[arm].mcps)}")
            except ClaudeAuthMissing:
                print(f"SKIP  {label}: no claude token.\n{_claude_guidance()}")
                failed = True
                break
            except (LeakError, OSError, ValueError) as exc:
                print(f"FAIL  {label}: {exc}")
                failed = True
        if len(seen) == 2:
            try:
                assert_arms_match(seen["bare"], seen["bruhs"])
                print(f"PASS  {spec.cli}: arms differ only by bruhs")
            except LeakError as exc:
                print(f"FAIL  {spec.cli}: {exc}")
                failed = True
    shutil.rmtree(base, ignore_errors=True)
    print("probe: " + ("FAILED" if failed else "all isolated"))
    return 1 if failed else 0


def cmd_run(args, post_run: Callable | None = None, disk_guard=None) -> int:
    from .homes import ClaudeAuthMissing
    from .runner import AuthAbort, DiskLow, run_matrix

    if args.pilot and args.tasks:
        raise CliError("--pilot runs the tasks in bench/pilot.toml; don't combine it with --tasks")
    all_tasks = load_all_tasks()
    ids = pilot_task_ids() if args.pilot else args.tasks
    tasks = select_tasks(all_tasks, ids, heldout=args.heldout)
    if not tasks:
        raise CliError("no tasks to run")
    repeats = 1 if args.pilot else args.repeats
    models = select_models(args.models)
    root = results_root(args)
    print(f"run: {len(tasks)} tasks x {len(models)} models x 2 arms x {repeats} repeats "
          f"-> {root}")
    try:
        results = run_matrix(tasks, models, ("bare", "bruhs"), repeats, root,
                             parallel=args.parallel, timeout_s=args.timeout * 60,
                             post_run=post_run, disk_guard=disk_guard or _disk_guard(root))
    except ClaudeAuthMissing:
        print(_claude_guidance(), file=sys.stderr)
        return 2
    except AuthAbort as exc:
        print(f"stopped: {exc}", file=sys.stderr)
        return 3
    except DiskLow as exc:
        print(f"stopped: {exc}", file=sys.stderr)
        return DISK_LOW_EXIT
    by_status: dict[str, int] = {}
    for r in results:
        by_status[r.status] = by_status.get(r.status, 0) + 1
    print(f"run: {len(results)} runs {by_status}")
    return 0


def _post_processor(root: Path, guard, *, cleanup: bool, post_parallel: int = 2) -> Callable:
    """The pipeline's per-run step after the agent finishes: capture (ui/copy) ->
    grade -> delete the run's work dir once nothing needs it.

    Disk is checked with the matrix's own ``guard`` before capture and before grade, and
    *before* taking one of the ``post_parallel`` capture/grade slots, so a run waiting
    for space never holds a slot. Runs with only cleanup left take no slot and never
    wait: they are what frees space. :class:`~bruhsbench.runner.DiskLow` stops the
    matrix."""
    import threading

    from .capture import capture_before
    from .graders import run_meta, workspace_of
    from .runner import cleanup_run, default_work_root

    work_root = default_work_root(root)
    slots = threading.BoundedSemaphore(max(1, post_parallel))

    def post_run(spec, result) -> None:
        d, task = root / spec.run_id, spec.task
        meta = run_meta(d)
        if meta.get("workspace_deleted"):
            return
        gradeable = meta.get("status") not in ("error", "setup_failed")
        ws = workspace_of(d)
        if (gradeable and ws is not None and task.category in PAIRWISE
                and _own_exclusion(d) is None and not _capture_finished(d)):
            guard.wait(f"capturing {d.name}")
            with slots:
                capture_before(task, root, work_root)  # once per task, file-locked
                for _attempt in range(2):  # one retry for a flaky dev server
                    _capture_and_refresh(d, task, ws)
                    if _captured(d):
                        break
        if gradeable and not _graded(d):
            guard.wait(f"grading {d.name}")
            with slots:
                _grade_run(d, task)
        if cleanup:
            if _done_with_workspace(d, task):
                cleanup_run(root, work_root, d.name)
            elif _capture_error(d):
                log.warning("%s: capture failed (harness error), workspace kept; rerun "
                            "`pipeline` or `capture` to retry", d.name)
            else:
                log.warning("%s: grading incomplete, workspace kept (rerun to retry)", d.name)

    return post_run


def _checklist_stale(d: Path, task: Task) -> bool:
    """A ui/copy run's checklist was graded without the screenshots a later successful
    capture now provides."""
    from .graders import read_grade

    if task.category not in PAIRWISE or not _captured(d):
        return False
    g = read_grade(d, "checklist")
    if not g or not g.get("applicable") or not any((d / "screens").glob("*.png")):
        return False
    if "screens" in g:
        return g["screens"] == 0
    # graded before the count was recorded: stale if graded before this capture
    grades = d / "grades"
    return (grades / "checklist.json").stat().st_mtime < (grades / "capture.json").stat().st_mtime


def _regrade_after_capture(d: Path, task: Task) -> None:
    """Regrade the checklist with the new screenshots, then honesty (it reads the
    checklist). The earlier checklist is kept as ``grades/checklist.superseded.json``."""
    import traceback

    from .graders import checklist, honesty, read_grade, write_grade
    from .judge import judges_for, make_judge, parse_run_id

    old = read_grade(d, "checklist") or {}
    write_grade(d, "checklist.superseded", {
        **old, "superseded": True,
        "reason": "graded without screenshots; regraded after a successful capture"})
    cli = parse_run_id(d.name)[1]
    judge = make_judge(cli)
    for name, fn in (
            ("checklist", lambda: checklist.grade(task, d, judges_for(cli))),
            ("honesty", lambda: honesty.grade(task, d, extract_claims=judge.extract_claims,
                                              claimed_items=judge.claimed_items))):
        try:
            fn()
        except Exception:  # recorded like grade_all does; `grade` retries it
            write_grade(d, name, {"applicable": True, "error": traceback.format_exc()})
    print(f"regraded {d.name}: checklist + honesty with the new screenshots", flush=True)


def _capture_and_refresh(d: Path, task: Task, ws: Path) -> None:
    """Capture, then regrade a checklist that was graded without screenshots."""
    _capture_run(d, task, ws)
    if _checklist_stale(d, task):
        _regrade_after_capture(d, task)


def _capture_finished(d: Path) -> bool:
    """A capture was recorded and needs no retry (page errors are final here)."""
    return (d / "grades" / "capture.json").is_file() and not _capture_error(d)


def cmd_pipeline(args) -> int:
    """run, with capture -> grade -> cleanup per run as each finishes."""
    root = results_root(args)
    guard = _disk_guard(root)
    post = _post_processor(root, guard, cleanup=args.cleanup,
                           post_parallel=args.post_parallel)
    return cmd_run(args, post_run=post, disk_guard=guard)


def _clean_done(root: Path, args) -> tuple[int, list[str], dict[str, list[str]]]:
    """(run dirs removed, runs kept for a capture error, leftovers per run)."""
    from .runner import cleanup_run, default_work_root

    work_root = default_work_root(root)
    n, capture_kept, leftovers = 0, [], {}
    for d, task in _runs_with_tasks(root, args):
        if not ((work_root / d.name).exists() or (work_root / d.name).is_symlink()):
            continue
        if not _done_with_workspace(d, task):
            if _capture_error(d):
                capture_kept.append(d.name)
            continue
        left = cleanup_run(root, work_root, d.name)
        if left:
            leftovers[d.name] = left
        else:
            n += 1
    return n, capture_kept, leftovers


def cmd_clean(args) -> int:
    """Delete work-root dirs of runs that are captured + graded (``--all``: the whole
    work root of this results dir, refused while a run/pipeline/capture/grade holds it unless
    ``--force``). Never touches the results dir itself."""
    from contextlib import nullcontext

    from .runner import (WorkRootBusy, default_work_root, exclusive_work_root,
                         mark_workspace_deleted, remove_work_root)
    from .untrusted import RemoveIncomplete

    root = results_root(args)
    work_root = default_work_root(root)
    if args.all:
        try:  # the exclusive lock is held for the whole removal
            with nullcontext() if args.force else exclusive_work_root(work_root):
                removed = remove_work_root(work_root, protect=[root])
        except WorkRootBusy:
            raise CliError(f"a `run`, `pipeline`, `capture` or `grade` is using {work_root}; "
                           "wait for it to finish (or pass --force to delete it anyway)"
                           ) from None
        except RemoveIncomplete as exc:
            print(f"clean: could not delete {len(exc.leftovers)} path(s) under {work_root}:",
                  file=sys.stderr)
            for p in exc.leftovers:
                print(f"  {p}", file=sys.stderr)
            return 1
        for d in run_dirs(root):
            mark_workspace_deleted(d)
        print(f"clean: {'removed' if removed else 'nothing at'} {work_root}")
        return 0
    n, capture_kept, leftovers = _clean_done(root, args)
    print(f"clean: removed {n} run dirs under {work_root}")
    if capture_kept:
        print(f"clean: kept {len(capture_kept)} workspaces whose capture failed (rerun "
              f"`bruhsbench capture`): {capture_kept}", file=sys.stderr)
    if leftovers:
        print(f"clean: could not fully delete {len(leftovers)} run dirs:", file=sys.stderr)
        for rid, paths in leftovers.items():
            print(f"  {rid}: {paths}", file=sys.stderr)
        return 1
    return 0


def _graded(run_dir: Path) -> bool:
    """Every grade file exists and none recorded a grader exception or a judge failure
    (those are retried)."""
    from .graders import read_grade

    for name in GRADE_FILES:
        g = read_grade(run_dir, name)
        if g is None or g.get("invalid") or (g.get("applicable") and set(g) == {"applicable",
                                                                                "error"}):
            return False
    return True


def _captured(d: Path) -> bool:
    """capture.json exists without a harness error or page errors (else capture retries)."""
    import json

    rec = d / "grades" / "capture.json"
    if not rec.is_file():
        return False
    data = json.loads(rec.read_text())
    return not data.get("error") and not data.get("page_errors")


def _own_exclusion(d: Path) -> str | None:
    from .graders import run_meta
    from .score import Run, parse_run_id

    task_id, cli_, arm, rep = parse_run_id(d.name)
    return Run(d.name, task_id, cli_, arm, rep, d, run_meta(d), {}).exclusion


def _capture_error(d: Path) -> bool:
    """capture.json records a harness error (dev server didn't start, browser crashed):
    the capture must be retried, so the workspace is kept. Page errors alone (often the
    agent's own broken page) are a finished capture."""
    import json

    rec = d / "grades" / "capture.json"
    return rec.is_file() and bool(json.loads(rec.read_text()).get("error"))


def _done_with_workspace(d: Path, task: Task) -> bool:
    """Nothing left needs the run's workspace: it is graded (or ungradeable) and, for a
    ui/copy run that isn't excluded, captured without a harness error (page errors are
    fine)."""
    from .graders import run_meta

    if run_meta(d).get("status") in ("error", "setup_failed"):
        return True
    if not _graded(d):
        return False
    return (task.category not in PAIRWISE or _own_exclusion(d) is not None
            or ((d / "grades" / "capture.json").is_file() and not _capture_error(d)))


def _grade_run(d: Path, task: Task) -> None:
    from .graders import grade_all
    from .judge import judges_for, make_judge, parse_run_id

    cli = parse_run_id(d.name)[1]
    grades = grade_all(task, d, make_judge(cli), checklist_judges=judges_for(cli))
    errs = [n for n, g in grades.items() if g.get("error") and "checks" not in g]
    print(f"graded {d.name}" + (f" (errors: {errs})" if errs else ""), flush=True)


def _capture_run(d: Path, task: Task, ws: Path) -> None:
    from .capture import capture

    shutil.rmtree(d / "screens", ignore_errors=True)
    files = capture(task, ws, d / "screens", run_dir=d)
    print(f"captured {d.name}: {len(files)} screenshots", flush=True)


def cmd_grade(args) -> int:
    from .graders import run_meta
    from .runner import default_work_root, hold_active
    from .score import load_runs

    root = results_root(args)
    excluded = {r.run_id for r in load_runs(root) if r.exclusion}
    todo, unshot, gone = [], [], []
    for d, task in _runs_with_tasks(root, args):
        meta = run_meta(d)
        if meta.get("status") in ("error", "setup_failed"):
            continue  # excluded from scoring (R23 a); nothing to grade
        if meta.get("workspace_deleted"):
            if args.force or not _graded(d):
                gone.append(d.name)  # regrading without a workspace would wipe grades
            continue
        if args.force or not _graded(d):
            todo.append((d, task))
            if (task.category in PAIRWISE and d.name not in excluded
                    and not any((d / "screens").glob("*.png"))):
                unshot.append(d.name)
    if unshot:
        print(f"warning: {len(unshot)} ui/copy runs have no screenshots, so their checklist "
              f"judges see none (run `bruhsbench capture` first): {unshot}", file=sys.stderr)
    if gone:
        print(f"warning: not regrading {len(gone)} runs whose workspace was deleted: {gone}",
              file=sys.stderr)
    print(f"grade: {len(todo)} runs to grade in {root}")
    with hold_active(default_work_root(root)):  # `clean --all` waits for us
        return _guarded_parallel(_grade_run, todo, args.parallel, _disk_guard(root),
                                 "grading")


def cmd_capture(args) -> int:
    from .capture import capture_before
    from .graders import workspace_of
    from .runner import DiskLow, default_work_root, hold_active
    from .score import load_runs

    root = results_root(args)
    work_root = default_work_root(root)
    excluded = {r.run_id for r in load_runs(root) if r.exclusion}
    todo, tasks = [], {}
    for d, task in _runs_with_tasks(root, args):
        if task.category not in PAIRWISE or d.name in excluded:
            continue
        tasks[task.id] = task
        if not args.force and _captured(d):
            continue
        ws = workspace_of(d)
        if ws is None:
            log.warning("%s: workspace gone, can't capture", d.name)
            continue
        todo.append((d, task, ws))
    print(f"capture: {len(tasks)} ui/copy tasks, {len(todo)} runs to capture")
    guard = _disk_guard(root)
    with hold_active(work_root):  # `clean --all` waits for us
        for task in tasks.values():  # baseline once per task (skipped when complete)
            if args.force:
                shutil.rmtree(root / "_before" / task.id, ignore_errors=True)
            try:
                guard.wait(f"capturing the {task.id} baseline")
            except DiskLow as exc:
                print(f"stopped: {exc}", file=sys.stderr)
                return DISK_LOW_EXIT
            capture_before(task, root, work_root)
        # a run graded before its first good capture gets checklist + honesty regraded
        return _guarded_parallel(_capture_and_refresh, todo, args.parallel, guard,
                                 "capturing")


def cmd_judge(args) -> int:
    import json

    from .judge import judges_for, pairwise
    from .score import load_runs

    root = results_root(args)
    tasks = _task_index(args.heldout)
    units: dict[tuple[str, str, int], dict] = {}
    for r in load_runs(root):
        if r.task_id in tasks and tasks[r.task_id].category in PAIRWISE:
            units.setdefault((r.task_id, r.cli, r.repeat), {})[r.arm] = r
    todo = []
    for (task_id, cli, rep), arms in sorted(units.items()):
        if set(arms) != {"bare", "bruhs"} or any(r.exclusion for r in arms.values()):
            continue  # R23 a: never judged, excluded from both arms
        for judge in judges_for(cli):
            verdict = root / "_pairs" / f"{task_id}__{cli}__r{rep}__{judge.cli}.json"
            if not args.force and verdict.is_file() and \
                    json.loads(verdict.read_text()).get("winner") is not None:
                continue
            todo.append((tasks[task_id], arms["bare"].dir, arms["bruhs"].dir, judge))
    print(f"judge: {len(todo)} pairwise verdicts to get")

    def one(task, bare_dir, bruhs_dir, judge) -> None:
        v = pairwise(task, bare_dir, bruhs_dir, judge)
        print(f"judged {task.id} {bare_dir.name.split('__')[1]} {bare_dir.name.rsplit('__', 1)[1]}"
              f" by {judge.cli}: " + ("error" if v["winner"] is None else "ok"), flush=True)

    _parallel(one, todo, args.parallel)
    return 0


def cmd_spotcheck(args) -> int:
    from .spotcheck import serve

    serve(results_root(args), n=args.n, seed=args.seed, port=args.port, force=args.force)
    return 0


def cmd_report(args) -> int:
    from .report import render
    from .score import summarize

    root = results_root(args)
    tasks = list(_task_index(args.heldout).values())
    summary = summarize(root, tasks=tasks)
    if args.public:
        out = Path(args.out) if args.out else PUBLISHED_DIR / date.today().isoformat()
    else:
        out = Path(args.out) if args.out else root / "report"
    html, md = render(summary, out, private=not args.public)
    print(f"report: {html}\n        {md}")
    return 0


# --------------------------------------------------------------------------- parser


def build_parser() -> argparse.ArgumentParser:
    p = argparse.ArgumentParser(prog="bruhsbench", description=__doc__.split("\n")[0])
    sub = p.add_subparsers(dest="command", required=True)

    def common(sp, *, parallel: int | None = None):
        sp.add_argument("--results", help="results dir (default bench/results/full, "
                                          "or bench/results/pilot with --pilot)")
        sp.add_argument("--pilot", action="store_true", help="use the pilot results dir")
        sp.add_argument("--heldout", action="store_true", help="allow held-out tasks")
        if parallel is not None:
            sp.add_argument("--parallel", type=int, default=parallel)
        sp.add_argument("--force", action="store_true", help="redo work that already exists")

    sp = sub.add_parser("probe", help="isolation probe for all cli x arm combos")
    sp.add_argument("--models", nargs="+")
    sp.set_defaults(fn=cmd_probe)

    from .runner import DEFAULT_PARALLEL

    sp = sub.add_parser("run", help="run the agent matrix (resumable)")
    common(sp, parallel=DEFAULT_PARALLEL)
    sp.add_argument("--tasks", nargs="+")
    sp.add_argument("--models", nargs="+")
    sp.add_argument("--repeats", type=int, default=3)
    sp.add_argument("--timeout", type=int, default=45, help="per-run timeout, minutes")
    sp.set_defaults(fn=cmd_run)

    sp = sub.add_parser("pipeline", help="run -> capture -> grade -> cleanup per run "
                                         "(resumable)")
    common(sp, parallel=DEFAULT_PARALLEL)
    sp.add_argument("--tasks", nargs="+")
    sp.add_argument("--models", nargs="+")
    sp.add_argument("--repeats", type=int, default=3)
    sp.add_argument("--timeout", type=int, default=45, help="per-run timeout, minutes")
    sp.add_argument("--cleanup", action=argparse.BooleanOptionalAction, default=True,
                    help="delete each run's workspace + home once captured and graded")
    sp.add_argument("--post-parallel", type=int, default=2,
                    help="max runs capturing/grading at once next to the agent runs")
    sp.set_defaults(fn=cmd_pipeline)

    for name, fn, par, help_ in (("capture", cmd_capture, 3, "screenshot ui/copy runs"),
                                 ("grade", cmd_grade, 4, "grade every finished run"),
                                 ("judge", cmd_judge, 4, "blind pairwise judging, ui/copy")):
        sp = sub.add_parser(name, help=help_)
        common(sp, parallel=par)
        sp.set_defaults(fn=fn)

    sp = sub.add_parser("clean", help="delete work dirs of captured + graded runs")
    common(sp)
    sp.add_argument("--all", action="store_true",
                    help="delete everything under this results dir's work root (refused "
                         "while a run/pipeline is active unless --force)")
    sp.set_defaults(fn=cmd_clean)

    sp = sub.add_parser("spotcheck", help="blind-pick ui/copy pairs in a local page")
    common(sp)  # --force: draw a new sample (clears picks; old file kept as .bak)
    sp.add_argument("-n", type=int, default=20)
    sp.add_argument("--seed", type=int, default=0)
    sp.add_argument("--port", type=int, default=8765)
    sp.set_defaults(fn=cmd_spotcheck)

    sp = sub.add_parser("report", help="HTML + markdown report")
    common(sp)
    sp.add_argument("--public", action="store_true",
                    help="publishable: private tasks by category and score only")
    sp.add_argument("--out", help="output dir (default <results>/report, or "
                                  "bench/results/published/<date> with --public)")
    sp.set_defaults(fn=cmd_report)
    return p


def main(argv: list[str] | None = None) -> int:
    logging.basicConfig(level=logging.INFO, format="%(levelname)s %(message)s")
    args = build_parser().parse_args(argv)
    try:
        return args.fn(args)
    except CliError as exc:
        print(f"bruhsbench: {exc}", file=sys.stderr)
        return 2


if __name__ == "__main__":
    sys.exit(main())
