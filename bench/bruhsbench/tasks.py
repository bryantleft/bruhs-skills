from __future__ import annotations

import tomllib
from pathlib import Path

from .types import CATEGORIES, Task

HELDOUT_DIR = "tasks-heldout"
PRIVATE_DIR = "tasks-private"
BENCH_DIR = Path(__file__).resolve().parents[1]
# public seeded tasks, gitignored real tasks from private repos, sealed held-out tasks
TASK_ROOTS = (BENCH_DIR / "tasks", BENCH_DIR / PRIVATE_DIR, BENCH_DIR / HELDOUT_DIR)


class TaskError(Exception):
    pass


def _opt_path(d: Path, override: object, default: str) -> Path | None:
    if override is not None:
        return d / str(override)
    p = d / default
    return p if p.exists() else None


def load_task(dir: Path) -> Task:
    dir = Path(dir)
    toml_path = dir / "task.toml"
    if not toml_path.is_file():
        raise TaskError(f"{dir}: missing task.toml")
    try:
        cfg = tomllib.loads(toml_path.read_text())
    except tomllib.TOMLDecodeError as e:
        raise TaskError(f"{toml_path}: invalid TOML: {e}") from e
    for key in ("id", "category"):
        if key not in cfg:
            raise TaskError(f"{toml_path}: missing required key '{key}'")
    if cfg["category"] not in CATEGORIES:
        raise TaskError(f"{toml_path}: unknown category {cfg['category']!r}")
    prompt_path = dir / "prompt.md"
    if not prompt_path.is_file():
        raise TaskError(f"{dir}: missing prompt.md")

    repo = Path(cfg["repo"]).expanduser() if "repo" in cfg else None
    base = cfg.get("base") if repo is not None else None
    heldout = bool(cfg.get("heldout", False)) or HELDOUT_DIR in dir.resolve().parts

    return Task(
        id=cfg["id"],
        category=cfg["category"],
        dir=dir,
        repo=repo,
        base=base,
        prompt=prompt_path.read_text(),
        setup=_opt_path(dir, cfg.get("setup"), "setup.sh"),
        allowed_paths=tuple(cfg.get("allowed_paths", ())),
        pages=tuple(cfg.get("pages", ())),
        dev_cmd=cfg.get("dev_cmd"),
        dev_port=cfg.get("dev_port"),
        checks=dict(cfg.get("checks", {})),
        hidden_tests=_opt_path(dir, cfg.get("hidden_tests"), "hidden"),
        known_issues=_opt_path(dir, cfg.get("known_issues"), "known_issues.json"),
        checklist=_opt_path(dir, cfg.get("checklist"), "checklist.json"),
        heldout=heldout,
        after_base=_opt_path(dir, cfg.get("after_base"), "after_base.sh"),
    )


def load_tasks(root: Path, *, include_heldout: bool = False) -> list[Task]:
    tasks = [load_task(p.parent) for p in sorted(Path(root).rglob("task.toml"))]
    return [t for t in tasks if include_heldout or not t.heldout]


def load_all_tasks(roots=TASK_ROOTS) -> list[Task]:
    """Every task (held-out included) under the existing ``roots``."""
    return [t for r in roots if Path(r).is_dir() for t in load_tasks(r, include_heldout=True)]


def is_private(task: Task) -> bool:
    """Real tasks (a source repo, or under tasks-private/): never published beyond
    category and scores."""
    return task.repo is not None or PRIVATE_DIR in Path(task.dir).resolve().parts
