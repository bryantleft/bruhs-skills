"""Task freeze (plan Task 11, Steps 4-5): pin every task's definition and grading before the
matrix runs, so a checklist can't drift between the user's review and the results.

``bruhsbench freeze`` writes one SHA-256 per task: private tasks (``tasks-private/``,
gitignored) into ``tasks-private/_frozen.sha256``, public seeded tasks (``tasks/``,
``tasks-heldout/``) into ``bench/frozen.sha256`` (committed). Each has a companion
``*.manifest.json`` with the per-file hashes, so a mismatch names the files that changed.
``run``/``pipeline`` (not ``--pilot``) refuse to start when a selected task's hash differs
from its frozen one or it isn't frozen; ``--allow-unfrozen`` (development only) overrides
that and is recorded in ``matrix.json``, as are the hashes every start ran with.

Beyond the start: matrix.json pins the first start's ``task_hashes`` (pilot included), a
resume with a changed task is refused, and ``grade``, ``capture``, ``judge`` and the
pipeline's per-run step refuse a task whose current hash isn't the pinned one, so runs are
always graded against the definition they ran with. ``freeze`` refuses (without
``--force``) to freeze a task at a definition other than one that an existing results dir
under ``bench/results/`` pinned.

What is hashed (the exact rule). A task's hash is the SHA-256 of its manifest: one line
``<sha256 of the file>  <label>`` per file, sorted by label, over

* every file under the task dir (label ``task/<relative path>``): task.toml, prompt.md,
  setup.sh, after_base.sh, checklist.json, known_issues.json, hidden/**, fixture/** (a
  seeded task's repo), seed/** (seed data: large blobs enter by their content hash only,
  like every file), bench-deps/** and anything else there;
* every file of each shared dir the task's setup.sh, after_base.sh or task.toml names as
  ``_shared/<name>`` (a sibling ``_shared/<name>/`` of the task dir; label
  ``shared/<name>/<relative path>``): install scripts, dev.sh, the Convex backend binary,
  probe preludes;

except files that don't affect what an agent sees or how it is graded: ``NOTES.md``,
``*_src.py`` (checklist_src.py, known_issues_src.py: sources of the JSON that is hashed),
``__pycache__/``, ``*.pyc`` and ``.DS_Store``. A symlink is hashed as its target string,
never followed.
"""

from __future__ import annotations

import hashlib
import json
import os
import re
from collections.abc import Iterable, Sequence
from dataclasses import dataclass, field
from pathlib import Path

from .tasks import BENCH_DIR, PRIVATE_DIR, is_private
from .types import Task

FROZEN_PUBLIC = BENCH_DIR / "frozen.sha256"
FROZEN_PRIVATE = BENCH_DIR / PRIVATE_DIR / "_frozen.sha256"
EXCLUDED_NAMES = frozenset({"NOTES.md", ".DS_Store"})
EXCLUDED_DIRS = frozenset({"__pycache__"})
SHARED_DIR = "_shared"
_SHARED_REF = re.compile(r"_shared/([A-Za-z0-9][A-Za-z0-9_.-]*)")
_SHARED_REF_FILES = ("task.toml", "setup.sh", "after_base.sh")
HEADER = ("# bruhsbench task freeze: SHA-256 of each task's manifest (bruhsbench/freeze.py). "
          "Regenerate with `bruhsbench freeze` after reviewing the tasks.\n")


class FreezeError(ValueError):
    """A frozen file or its manifest can't be parsed."""


_LINE = re.compile(r"([0-9a-f]{64})\s+(\S+)")


def _excluded(name: str) -> bool:
    return name in EXCLUDED_NAMES or name.endswith(("_src.py", ".pyc"))


_file_hashes: dict[tuple, str] = {}  # (path, ino, size, mtime_ns) -> sha256, per process


def _file_hash(path: Path) -> str:
    st = os.lstat(path)
    if os.path.islink(path):
        return hashlib.sha256(b"symlink:" + os.readlink(path).encode()).hexdigest()
    key = (str(path), st.st_ino, st.st_size, st.st_mtime_ns)
    if key not in _file_hashes:  # the Convex binary and seeds are shared by many tasks
        h = hashlib.sha256()
        with open(path, "rb") as f:
            while chunk := f.read(1 << 20):
                h.update(chunk)
        _file_hashes[key] = h.hexdigest()
    return _file_hashes[key]


def _walk(root: Path, label: str) -> Iterable[tuple[str, Path]]:
    for dirpath, dirnames, filenames in os.walk(root):  # never descends into symlinks
        dirnames[:] = sorted(d for d in dirnames if d not in EXCLUDED_DIRS)
        rel = Path(dirpath).relative_to(root)
        links = [d for d in dirnames if os.path.islink(Path(dirpath) / d)]
        for name in sorted([*filenames, *links]):
            if not _excluded(name):
                yield (Path(label) / rel / name).as_posix(), Path(dirpath) / name


def shared_dirs(task: Task) -> list[str]:
    """The ``_shared/<name>`` dirs the task's setup.sh, after_base.sh or task.toml name."""
    names: set[str] = set()
    for f in _SHARED_REF_FILES:
        p = Path(task.dir) / f
        if p.is_file():
            names.update(_SHARED_REF.findall(p.read_text(errors="replace")))
    shared = Path(task.dir).parent / SHARED_DIR
    return sorted(n for n in names if (shared / n).is_dir())


def manifest(task: Task) -> dict[str, str]:
    """``{label: sha256}`` for every file that defines the task (module docstring)."""
    files = list(_walk(Path(task.dir), "task"))
    for name in shared_dirs(task):
        files += _walk(Path(task.dir).parent / SHARED_DIR / name, f"shared/{name}")
    return {label: _file_hash(path) for label, path in sorted(files)}


def manifest_hash(entries: dict[str, str]) -> str:
    text = "".join(f"{h}  {label}\n" for label, h in sorted(entries.items()))
    return hashlib.sha256(text.encode()).hexdigest()


def task_hash(task: Task) -> str:
    return manifest_hash(manifest(task))


# --------------------------------------------------------------------------- files


def frozen_file(task: Task) -> Path:
    return FROZEN_PRIVATE if is_private(task) else FROZEN_PUBLIC


def _manifest_file(frozen: Path) -> Path:
    return frozen.with_suffix(".manifest.json")


def read_frozen(path: Path) -> dict[str, str]:
    """``{task_id: sha256}`` from a frozen file ({} if absent); :class:`FreezeError`
    naming the file and line for a malformed line."""
    if not Path(path).is_file():
        return {}
    out = {}
    for n, line in enumerate(Path(path).read_text().splitlines(), 1):
        if not line.strip() or line.startswith("#"):
            continue
        m = _LINE.fullmatch(line.strip())
        if m is None:
            raise FreezeError(f"{path}:{n}: malformed line {line[:80]!r} (expected "
                              "'<64 hex sha256>  <task id>'); rerun `bruhsbench freeze`")
        out[m[2]] = m[1]
    return out


def _read_manifests(path: Path) -> dict[str, dict[str, str]]:
    m = _manifest_file(path)
    if not m.is_file():
        return {}
    try:
        data = json.loads(m.read_text())
    except json.JSONDecodeError as exc:
        raise FreezeError(f"{m}:{exc.lineno}: malformed manifest: {exc.msg}") from None
    if not isinstance(data, dict):
        raise FreezeError(f"{m}: malformed manifest (not an object)")
    return data


def _write(path: Path, hashes: dict[str, str], manifests: dict[str, dict[str, str]]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    body = HEADER + "".join(f"{hashes[t]}  {t}\n" for t in sorted(hashes))
    for target, text in ((path, body), (_manifest_file(path),
                                        json.dumps(manifests, indent=1, sort_keys=True) + "\n")):
        tmp = target.with_name(target.name + ".tmp")
        tmp.write_text(text)
        os.replace(tmp, target)


@dataclass
class FreezeResult:
    added: list[str] = field(default_factory=list)
    changed: list[str] = field(default_factory=list)
    unchanged: list[str] = field(default_factory=list)
    dropped: list[str] = field(default_factory=list)


def freeze(tasks: Sequence[Task], *, only: Sequence[str] | None = None) -> FreezeResult:
    """Write the frozen files for ``tasks``. With ``only``, just those ids are
    (re)frozen and every other entry is kept; otherwise the files list exactly
    ``tasks`` (entries of tasks that no longer exist are dropped)."""
    result = FreezeResult()
    for path in (FROZEN_PUBLIC, FROZEN_PRIVATE):
        group = [t for t in tasks if frozen_file(t) == path]
        if only is not None:
            group = [t for t in group if t.id in only]
            if not group:
                continue
        old, old_manifests = read_frozen(path), _read_manifests(path)
        hashes = dict(old) if only is not None else {}
        manifests = {k: v for k, v in old_manifests.items() if k in hashes}
        if only is None:
            result.dropped += sorted(set(old) - {t.id for t in group})
        for t in group:
            manifests[t.id] = manifest(t)
            hashes[t.id] = manifest_hash(manifests[t.id])
            if t.id not in old:
                result.added.append(t.id)
            elif old[t.id] != hashes[t.id]:
                result.changed.append(t.id)
            else:
                result.unchanged.append(t.id)
        _write(path, hashes, manifests)
    return result


@dataclass
class FreezeCheck:
    hashes: dict[str, str]  # task id -> current hash
    unfrozen: dict[str, str]  # task id -> why it doesn't match the frozen files

    def message(self) -> str:
        lines = [f"  {tid}: {why}" for tid, why in sorted(self.unfrozen.items())]
        return "\n".join(lines)


def _diff(old: dict[str, str], new: dict[str, str], limit: int = 8) -> str:
    if not old:
        return "no manifest to compare files with"
    changed = sorted(k for k in old.keys() & new.keys() if old[k] != new[k])
    added, removed = sorted(new.keys() - old.keys()), sorted(old.keys() - new.keys())
    parts = [f"{what} {', '.join(names[:limit])}{' ...' if len(names) > limit else ''}"
             for what, names in (("changed", changed), ("added", added),
                                 ("removed", removed)) if names]
    return "; ".join(parts) or "manifest out of date"


def check(tasks: Sequence[Task]) -> FreezeCheck:
    """Current hashes of ``tasks`` and those that are missing from, or differ from,
    the frozen files."""
    frozen = {p: read_frozen(p) for p in (FROZEN_PUBLIC, FROZEN_PRIVATE)}
    manifests = {p: _read_manifests(p) for p in frozen}
    hashes, unfrozen = {}, {}
    for t in tasks:
        path = frozen_file(t)
        current = manifest(t)
        hashes[t.id] = manifest_hash(current)
        want = frozen[path].get(t.id)
        if want is None:
            unfrozen[t.id] = f"not frozen (missing from {path})"
        elif want != hashes[t.id]:
            unfrozen[t.id] = "changed since the freeze: " + _diff(
                manifests[path].get(t.id, {}), current)
    return FreezeCheck(hashes, unfrozen)


def pinned_mismatches(tasks: Iterable[Task], pinned: dict[str, str]) -> dict[str, str]:
    """``{task_id: why}`` for ``tasks`` whose current hash isn't the one a results dir's
    matrix.json pinned (the hash its runs ran with)."""
    out = {}
    for t in tasks:
        want = pinned.get(t.id)
        if want is None:
            out[t.id] = "not in matrix.json's task_hashes"
        elif task_hash(t) != want:
            out[t.id] = "changed since its runs ran (hash differs from matrix.json)"
    return out


def matrices_using(task_hashes: dict[str, str], results_dir: Path) -> dict[str, list[str]]:
    """``{task_id: [results dirs]}``: results dirs under ``results_dir`` whose matrix.json
    lists the task but didn't pin ``task_hashes[task_id]`` (refreezing it would make their
    runs ungradeable)."""
    out: dict[str, list[str]] = {}
    for m in sorted(Path(results_dir).glob("*/matrix.json")):
        try:
            meta = json.loads(m.read_text())
        except (OSError, json.JSONDecodeError):
            continue
        pinned = meta.get("task_hashes") or {}
        for tid in meta.get("tasks", []):
            if tid in task_hashes and pinned.get(tid) != task_hashes[tid]:
                out.setdefault(tid, []).append(str(m.parent))
    return out
