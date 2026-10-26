"""What a prepared workspace shows an agent that names the benchmark or an arm (R40-R45).

:func:`workspace_leaks` scans what the harness and a task's setup put into a workspace, not
the task's own code (a real repo's files at ``base``, a seeded fixture's files):

* every path the setup added or changed relative to the task's source (tracked or not,
  ignored included, e.g. ``node_modules/.local-stack/``), except third-party packages
  under any ``node_modules/<pkg>`` (their names are the dependencies' own), and the target
  of every symlink among them;
* the lines such a file added (``dev.sh``, ``.env.local``, a rewritten ``package.json``),
  plus hex and base64 runs in them decoded (a secret can spell a name), and every changed
  ``package.json`` script; a lockfile only by its top-level ``name`` (the rest lists the
  dependencies' own names); a large or binary file (seed databases, the Convex binary) by
  a case-sensitive byte search for the harness's own tokens (:data:`BYTE_TOKENS`), since
  seed data legitimately holds words like the card name "Bench";
* the workspace's git metadata: authors, committers and full commit messages of the
  harness's commits, refs, ``.git/config`` (minus git's own ``core.bare`` key),
  ``.git/info/exclude``, ``.git/description`` and ``.git/hooks/*``.

Matches (:data:`HINT_RE`) are case-insensitive ``bench``/``bruhs`` anywhere and ``bare`` as
a word with ``_`` counted as a separator (``bare_ws``, ``ARM_BARE_X``), not inside a word
(``barely``, ``bareMetal``). The arm check covers only what the harness or setup wrote: a
task's own code may say "bare" (or "bench") legitimately, and that is task content, the same
in both arms. In the bruhs arm the bruhs marker blocks in CLAUDE.md/AGENTS.md are the
treatment and are skipped.
"""

from __future__ import annotations

import base64
import binascii
import json
import os
import re
import subprocess
from pathlib import Path

from .types import Arm, Task
from .workspace import GIT, strip_bruhs_blocks

HINT_RE = re.compile(r"bench|bruhs|(?<![A-Za-z0-9])bare(?![A-Za-z0-9])", re.IGNORECASE)
HEX_RUN_RE = re.compile(r"(?:[0-9a-fA-F]{2}){8,}")
B64_RUN_RE = re.compile(r"[A-Za-z0-9+/]{16,}={0,2}")
# the harness's own tokens, searched case-sensitively in large or binary files
BYTE_TOKENS = (b"bruhs", b"mints-bench", b"__bench", b".bench/", b"BENCH_")
MAX_TEXT_BYTES = 512_000
TREATMENT_FILES = ("CLAUDE.md", "AGENTS.md")
LOCKFILES = ("pnpm-lock.yaml", "package-lock.json", "yarn.lock", "bun.lock", "bun.lockb",
             "Cargo.lock", "uv.lock", "poetry.lock")


def _hint(text: str) -> bool:
    """A benchmark or arm name in ``text`` or in a hex or base64 run decoded from it."""
    if HINT_RE.search(text):
        return True
    for m in HEX_RUN_RE.finditer(text):
        if HINT_RE.search(bytes.fromhex(m.group(0)).decode("latin-1")):
            return True
    for m in B64_RUN_RE.finditer(text):
        run = m.group(0)
        try:
            raw = base64.b64decode(run + "=" * (-len(run) % 4), validate=True)
        except (binascii.Error, ValueError):
            continue
        if HINT_RE.search(raw.decode("latin-1")):
            return True
    return False


def _lockfile_name(p: Path, data: bytes) -> str | None:
    """The top-level package name a lockfile records, if any."""
    text = data.decode("utf-8", errors="replace")
    if p.suffix == ".json" or p.name == "bun.lock":
        try:
            name = json.loads(text).get("name")
        except (ValueError, AttributeError):
            return None
        return name if isinstance(name, str) else None
    m = re.search(r"^name\s*:\s*(\S+)", text, re.MULTILINE)  # top level only (no indent)
    return m.group(1) if m else None


def _git(ws: Path, *args: str) -> str:
    return subprocess.run([*GIT, *args], cwd=ws, check=True, capture_output=True,
                          text=True).stdout


def _source_files(task: Task) -> dict[str, bytes] | None:
    """The task's own files: path -> blob id at ``base`` (real repo) or the fixture's
    bytes hashed the same way (seeded)."""
    if task.repo is not None:
        out = subprocess.run([*GIT, "ls-tree", "-r", task.base], cwd=task.repo, check=True,
                             capture_output=True, text=True).stdout
        return {line.split("\t", 1)[1]: line.split()[2].encode()
                for line in out.splitlines() if "\t" in line}
    fixture = task.dir / "fixture"
    if not fixture.is_dir():
        return None
    files = {}
    for p in fixture.rglob("*"):
        if p.is_file() and ".git" not in p.relative_to(fixture).parts:
            files[p.relative_to(fixture).as_posix()] = _blob_id(p)
    return files


def _blob_id(path: Path) -> bytes:
    return subprocess.run([*GIT, "hash-object", str(path)], check=True, capture_output=True,
                          text=True).stdout.strip().encode()


# package managers' and tools' own dot entries in node_modules (their contents are the
# dependencies'); any other dot dir there (e.g. .local-stack) is the harness's
TOOL_DOT_ENTRIES = (".pnpm", ".bin", ".cache", ".vite", ".vite-temp", ".modules.yaml",
                    ".package-lock.json", ".ignored", ".tmp", ".prisma")


def _third_party(rel: str) -> bool:
    """Under ``node_modules/<pkg>`` (a package, or a package manager's own dot dir)."""
    parts = rel.split("/")
    for i, part in enumerate(parts[:-1]):
        if part == "node_modules":
            nxt = parts[i + 1]
            if (not nxt.startswith(".") or nxt in TOOL_DOT_ENTRIES
                    or nxt.startswith(".pnpm-")):
                return True  # e.g. node_modules/.local-stack/hidden/node_modules/vitest
    return False


def _source_text(task: Task, rel: str) -> str:
    """``rel`` as the task's source has it ("" if it doesn't)."""
    if task.repo is not None:
        proc = subprocess.run([*GIT, "show", f"{task.base}:{rel}"], cwd=task.repo,
                              capture_output=True)
        return proc.stdout.decode("utf-8", errors="replace") if proc.returncode == 0 else ""
    p = task.dir / "fixture" / rel
    return p.read_text(errors="replace") if p.is_file() else ""


def _walk(ws: Path):
    for dirpath, dirnames, filenames in os.walk(ws):
        rel_dir = Path(dirpath).relative_to(ws).as_posix()
        rel_dir = "" if rel_dir == "." else rel_dir + "/"
        dirnames[:] = [d for d in dirnames if d != ".git"
                       and not _third_party(rel_dir + d)]
        for d in dirnames:
            yield rel_dir + d, True
        for f in filenames:
            yield rel_dir + f, False


def workspace_leaks(task: Task, ws: Path, arm: Arm) -> list[str]:
    ws = Path(ws)
    source = _source_files(task) or {}
    found: list[str] = []
    for rel, is_dir in _walk(ws):
        if _third_party(rel):
            continue
        if is_dir:
            if _hint(rel.rsplit("/", 1)[-1]) and not any(
                    k.startswith(rel + "/") for k in source):
                found.append(f"dir name: {rel}")
            continue
        p = ws / rel
        if p.is_symlink():
            target = os.readlink(p)
            if _hint(target) and rel not in source:
                found.append(f"symlink: {rel} -> {target}")
            continue
        if rel in source and source[rel] == _blob_id(p):
            continue  # the task's own file, unchanged by setup
        if HINT_RE.search(rel) and rel not in source:
            found.append(f"file name: {rel}")
        data = p.read_bytes()
        if p.name in LOCKFILES:
            name = _lockfile_name(p, data)
            if name and _hint(name):
                found.append(f"{rel}: lockfile name {name}")
            continue
        if len(data) > MAX_TEXT_BYTES or b"\0" in data[:8192]:
            hits = [t.decode() for t in BYTE_TOKENS if t in data]
            if hits:
                found.append(f"{rel}: binary or large file holds {hits}")
            continue
        text = data.decode("utf-8", errors="replace")
        if arm == "bruhs" and rel in TREATMENT_FILES:
            text = strip_bruhs_blocks(text)
        # only lines the setup or harness added (the source's own lines are task content)
        own = set(_source_text(task, rel).splitlines()) if rel in source else set()
        for line in text.splitlines():
            if _hint(line) and line not in own:
                found.append(f"{rel}: {line.strip()[:160]}")
    for pkg in [ws / "package.json", *ws.glob("*/package.json"), *ws.glob("*/*/package.json")]:
        if pkg.is_file() and not _third_party(pkg.relative_to(ws).as_posix()):
            rel = pkg.relative_to(ws).as_posix()
            try:
                scripts = json.loads(pkg.read_text()).get("scripts") or {}
                orig = json.loads(_source_text(task, rel) or "{}").get("scripts") or {}
            except ValueError:
                continue
            for name, cmd in scripts.items():
                if _hint(f"{name} {cmd}") and orig.get(name) != cmd:
                    found.append(f"{pkg.relative_to(ws)} script {name}: {cmd}")
    # commits the harness and setup made (a real repo's own history up to base is task
    # content), with their full messages
    since = ["--not", task.base] if task.repo is not None else []
    meta = [_git(ws, "log", "--format=%an %ae %cn %ce%n%B", "--all", *since),
            _git(ws, "for-each-ref", "--format=%(refname)")]
    git_dir = ws / ".git"
    config = git_dir / "config"
    if config.is_file():  # git's own `bare = false` key is not an arm name
        meta.append(re.sub(r"(?m)^\s*bare\s*=\s*(true|false)\s*$", "", config.read_text()))
    for extra in (git_dir / "info" / "exclude", git_dir / "description",
                  *sorted((git_dir / "hooks").glob("*"))):
        if extra.is_file() and not extra.is_symlink():
            meta.append(extra.read_text(errors="replace"))
    for line in "\n".join(meta).splitlines():
        if _hint(line):
            found.append(f"git: {line.strip()[:160]}")
    return sorted(set(found))
