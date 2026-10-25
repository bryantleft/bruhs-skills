"""``bruhsbench``: run -> grade -> capture -> judge -> spotcheck -> report.

Every stage reads and writes plain files under one results dir (``--results``, default
``bench/results/full``; ``--pilot`` -> ``bench/results/pilot``) and skips work whose
outputs already exist, so any stage can be rerun or resumed; ``--force`` redoes it.
Held-out tasks (``tasks-heldout/`` or ``heldout = true``) are refused unless
``--heldout`` is given (rulings R1/R2).
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


def cmd_run(args) -> int:
    from .homes import ClaudeAuthMissing
    from .runner import AuthAbort, run_matrix

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
                             parallel=args.parallel, timeout_s=args.timeout * 60)
    except ClaudeAuthMissing:
        print(_claude_guidance(), file=sys.stderr)
        return 2
    except AuthAbort as exc:
        print(f"stopped: {exc}", file=sys.stderr)
        return 3
    by_status: dict[str, int] = {}
    for r in results:
        by_status[r.status] = by_status.get(r.status, 0) + 1
    print(f"run: {len(results)} runs {by_status}")
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


def cmd_grade(args) -> int:
    from .graders import grade_all, run_meta
    from .judge import judges_for, make_judge, parse_run_id

    root = results_root(args)
    todo = []
    for d, task in _runs_with_tasks(root, args):
        status = run_meta(d).get("status")
        if status in ("error", "setup_failed"):
            continue  # excluded from scoring (R23 a); nothing to grade
        if args.force or not _graded(d):
            todo.append((d, task))
    print(f"grade: {len(todo)} runs to grade in {root}")

    def one(d: Path, task: Task) -> None:
        cli = parse_run_id(d.name)[1]
        grades = grade_all(task, d, make_judge(cli), checklist_judges=judges_for(cli))
        errs = [n for n, g in grades.items() if g.get("error") and "checks" not in g]
        print(f"graded {d.name}" + (f" (errors: {errs})" if errs else ""), flush=True)

    _parallel(one, todo, args.parallel)
    return 0


def cmd_capture(args) -> int:
    import json

    from .capture import capture, capture_before
    from .graders import workspace_of
    from .runner import default_work_root
    from .score import load_runs

    root = results_root(args)
    work_root = default_work_root(root)
    excluded = {r.run_id for r in load_runs(root) if r.exclusion}
    todo, tasks = [], {}
    for d, task in _runs_with_tasks(root, args):
        if task.category not in PAIRWISE or d.name in excluded:
            continue
        tasks[task.id] = task
        rec = d / "grades" / "capture.json"
        if not args.force and rec.is_file():
            data = json.loads(rec.read_text())
            if not data.get("error") and not data.get("page_errors"):
                continue
        ws = workspace_of(d)
        if ws is None:
            log.warning("%s: workspace gone, can't capture", d.name)
            continue
        todo.append((d, task, ws))
    print(f"capture: {len(tasks)} ui/copy tasks, {len(todo)} runs to capture")
    for task in tasks.values():  # baseline once per task (skipped when complete)
        if args.force:
            shutil.rmtree(root / "_before" / task.id, ignore_errors=True)
        capture_before(task, root, work_root)

    def one(d: Path, task: Task, ws: Path) -> None:
        shutil.rmtree(d / "screens", ignore_errors=True)
        files = capture(task, ws, d / "screens", run_dir=d)
        print(f"captured {d.name}: {len(files)} screenshots", flush=True)

    _parallel(one, todo, args.parallel)
    return 0


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

    serve(results_root(args), n=args.n, seed=args.seed, port=args.port)
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

    for name, fn, par, help_ in (("grade", cmd_grade, 4, "grade every finished run"),
                                 ("capture", cmd_capture, 3, "screenshot ui/copy runs"),
                                 ("judge", cmd_judge, 4, "blind pairwise judging, ui/copy")):
        sp = sub.add_parser(name, help=help_)
        common(sp, parallel=par)
        sp.set_defaults(fn=fn)

    sp = sub.add_parser("spotcheck", help="blind-pick ui/copy pairs in a local page")
    common(sp)
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
