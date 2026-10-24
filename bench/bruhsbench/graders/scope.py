"""Scope creep: files and lines the agent changed outside ``task.allowed_paths``.

Reads the run's ``diff.patch`` (``git diff --binary`` vs bench-base). A file is inside
scope when any of its paths (both sides of a rename) matches an ``fnmatch`` glob (``*``
spans ``/``, so ``app/**`` and ``app/*`` both cover the whole tree). No globs = everything
is in scope. Lines = added + removed lines; binary files count as 0 lines.
"""

from __future__ import annotations

import re
from dataclasses import dataclass
from fnmatch import fnmatchcase
from pathlib import Path

from ..types import Task
from . import write_grade

_HEADER_RE = re.compile(r'^diff --git ("(?:[^"\\]|\\.)*"|\S+) ("(?:[^"\\]|\\.)*"|\S+)$')


@dataclass
class FileChange:
    paths: tuple[str, ...]  # one path, or (old, new) for a rename
    lines: int = 0


def _unquote(p: str) -> str:
    if p.startswith('"') and p.endswith('"'):
        p = p[1:-1].encode("latin-1", "backslashreplace").decode("unicode_escape")
        p = p.encode("latin-1").decode("utf-8", "replace")
    return p


def _strip_prefix(p: str) -> str | None:
    p = _unquote(p.strip())
    if p == "/dev/null":
        return None
    return p[2:] if p[:2] in ("a/", "b/") else p


def parse_diff(text: str) -> list[FileChange]:
    files: list[FileChange] = []
    cur: FileChange | None = None
    old = new = None
    in_hunk = False

    def close() -> None:
        if cur is not None:
            cur.paths = tuple(dict.fromkeys(p for p in (old, new) if p))

    for line in text.splitlines():
        if line.startswith("diff --git "):
            close()
            m = _HEADER_RE.match(line)
            old, new = (_strip_prefix(m[1]), _strip_prefix(m[2])) if m else (None, None)
            cur = FileChange(())
            files.append(cur)
            in_hunk = False
        elif cur is None:
            continue
        elif line.startswith("@@"):
            in_hunk = True
        elif in_hunk:
            if line[:1] in ("+", "-"):
                cur.lines += 1
        elif line.startswith("rename from "):
            old = _unquote(line[len("rename from "):])
        elif line.startswith("rename to "):
            new = _unquote(line[len("rename to "):])
        elif line.startswith("--- "):
            old = _strip_prefix(line[4:])
        elif line.startswith("+++ "):
            new = _strip_prefix(line[4:])
    close()
    return files


def in_scope(path: str, allowed: tuple[str, ...]) -> bool:
    return not allowed or any(fnmatchcase(path, g) for g in allowed)


def grade(task: Task, run_dir: Path) -> dict:
    diff_path = Path(run_dir) / "diff.patch"
    diff = diff_path.read_text(errors="replace") if diff_path.is_file() else ""
    files = parse_diff(diff)
    outside = [f for f in files if not all(in_scope(p, task.allowed_paths) for p in f.paths)]
    return write_grade(run_dir, "scope", {
        "applicable": True,
        "files_outside": sorted(p for f in outside for p in f.paths
                                if not in_scope(p, task.allowed_paths)),
        "lines_outside": sum(f.lines for f in outside),
        "files_changed": len(files),
        "lines_changed": sum(f.lines for f in files),
    })
