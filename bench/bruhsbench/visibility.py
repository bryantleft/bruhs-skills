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
  ``.git/info/exclude``, ``.git/description``, ``.git/hooks/*`` and the reflogs
  (``.git/logs/**``; :func:`workspace.prepare_workspace` expires them after setup).

Dependency and build trees (``node_modules/<pkg>``, site-packages, a real virtualenv, a
Cargo ``target/``; see :func:`_excluded`) get a reduced check: symlink targets and a
case-sensitive byte search for :func:`_reduced_tokens`. Build output records the
workspace's own absolute path, so the workspace must live under a neutral path, as a run's
does (``<work base>/<12 hex>/workspace``, R40); a ``$BRUHSBENCH_WORK`` naming the benchmark
would trip the guard.

Limits: a file over 512 KB (:data:`MAX_TEXT_BYTES`) or with a NUL byte in its first 8 KB
gets only the case-sensitive byte search for :data:`BYTE_TOKENS`, not the line, decoding or
arm-name checks.

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

from .homes import BRUHS_REPO
from .types import Arm, Task
from .workspace import GIT, strip_bruhs_blocks

HINT_RE = re.compile(r"bench|bruhs|(?<![A-Za-z0-9])bare(?![A-Za-z0-9])", re.IGNORECASE)
HEX_RUN_RE = re.compile(r"[0-9a-fA-F]{16,}")
B64_RUN_RE = re.compile(r"[A-Za-z0-9+/_-]{16,}={0,2}")
# the harness's own tokens, searched case-sensitively in large or binary files
BYTE_TOKENS = (b"bruhs", b"mints-bench", b"__bench", b".bench/", b"BENCH_")
MAX_TEXT_BYTES = 512_000
TREATMENT_FILES = ("CLAUDE.md", "AGENTS.md")
LOCKFILES = ("pnpm-lock.yaml", "package-lock.json", "yarn.lock", "bun.lock", "bun.lockb",
             "Cargo.lock", "uv.lock", "poetry.lock")


def _decodings(text: str):
    """Hex runs decoded at offsets 0 and 1, base64 runs (standard and URL-safe) at offsets
    0-3: an encoding needn't start where the run of its alphabet does (``k=a<hex>``)."""
    for m in HEX_RUN_RE.finditer(text):
        run = m.group(0)
        for o in (0, 1):
            part = run[o:]
            yield bytes.fromhex(part[:len(part) - len(part) % 2])
    for m in B64_RUN_RE.finditer(text):
        run = m.group(0).rstrip("=")
        for o in range(4):
            part = run[o:]
            part = part[:len(part) - len(part) % 4]
            if len(part) < 12:
                continue
            for alt in (b"+/", b"-_"):
                try:
                    yield base64.b64decode(part, altchars=alt, validate=True)
                except (binascii.Error, ValueError):
                    pass


def _hint(text: str) -> bool:
    """A benchmark or arm name in ``text`` or in a hex or base64 run decoded from it."""
    if HINT_RE.search(text):
        return True
    return any(HINT_RE.search(raw.decode("latin-1")) for raw in _decodings(text))


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


# Dependency and build trees: their contents are the dependencies' (or the compiler's) own
# text, e.g. a FastAPI README that mentions benchmarks, libtest strings in a Rust test
# binary, a package named tinybench. They are not dropped: every file in them still gets a
# reduced check (:data:`REDUCED_TOKENS`, case-sensitive bytes, and symlink targets), which
# catches a path into the bench repo or the old harness names (a .pyc co_filename, an
# editable .pth or direct_url.json, a Cargo dep-info file). Which trees:
#   node_modules/<pkg> and package managers' own dot entries (TOOL_DOT_ENTRIES);
#   site-packages/, __pycache__/, a .venv/ or venv/ that holds pyvenv.cfg, and a target/
#   next to a Cargo.toml -- but never under a harness dot dir in node_modules (e.g.
#   node_modules/.local-stack/venv is the harness's own and fully checked).
NAME_EXCLUDED = ("site-packages", "__pycache__")


def _harness_dot_dir(part: str) -> bool:
    return (part.startswith(".") and part not in TOOL_DOT_ENTRIES
            and not part.startswith(".pnpm-"))


def _excluded(ws: Path, rel: str) -> bool:
    """``rel`` is (inside) a dependency or build tree (see above)."""
    parts = rel.split("/")
    for i, part in enumerate(parts[:-1]):
        if part == "node_modules" and not _harness_dot_dir(parts[i + 1]):
            return True  # node_modules/<pkg>, node_modules/.pnpm, ...
    if any(part == "node_modules" and _harness_dot_dir(parts[i + 1])
           for i, part in enumerate(parts[:-1])):
        return False  # the harness's own dir: no name exclusions inside it
    for i, part in enumerate(parts):
        here = ws.joinpath(*parts[:i + 1])
        if part in NAME_EXCLUDED:
            return True
        if part in (".venv", "venv") and (here / "pyvenv.cfg").is_file():
            return True
        if part == "target" and (here.parent / "Cargo.toml").is_file():
            return True
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
    """(rel, is_dir, excluded) for every entry; a symlink (to a file or a directory) is
    reported as a non-directory so its target is checked; excluded trees are walked too."""
    excluded_dirs: dict[str, bool] = {"": False}
    for dirpath, dirnames, filenames in os.walk(ws):
        rel_dir = Path(dirpath).relative_to(ws).as_posix()
        rel_dir = "" if rel_dir == "." else rel_dir
        parent_ex = excluded_dirs.get(rel_dir, False)
        prefix = rel_dir + "/" if rel_dir else ""
        links = [d for d in dirnames if os.path.islink(os.path.join(dirpath, d))]
        dirnames[:] = [d for d in dirnames if d != ".git" and d not in links]
        for d in links:
            yield prefix + d, False, parent_ex or _excluded(ws, prefix + d)
        for d in dirnames:
            ex = parent_ex or _excluded(ws, prefix + d)
            excluded_dirs[prefix + d] = ex
            yield prefix + d, True, ex
        for f in filenames:  # e.g. node_modules/.modules.yaml is the package manager's
            yield prefix + f, False, parent_ex or _excluded(ws, prefix + f)


def _reduced_tokens() -> tuple[bytes, ...]:
    """What a dependency/build file must not hold: the bench repo's path and the harness's
    own names. (The work root is left out on purpose: a run's workspace lives under it,
    behind an opaque name, so build output naming its own paths is expected and reveals
    nothing; neither is `BENCH_`/`__bench`, which libraries use.)"""
    repo = str(BRUHS_REPO)
    forms = {repo, str(Path(repo).resolve())}
    return (*sorted(f.encode() for f in forms), b"bruhs", b"mints-bench", b".bench/")


def workspace_leaks(task: Task, ws: Path, arm: Arm) -> list[str]:
    ws = Path(ws)
    source = _source_files(task) or {}
    reduced = _reduced_tokens()
    found: list[str] = []
    for rel, is_dir, excluded in _walk(ws):
        if excluded:  # a dependency or build tree: the reduced check only
            p = ws / rel
            if p.is_symlink():
                target = os.readlink(p).encode()
                if any(t in target for t in reduced):
                    found.append(f"symlink: {rel} -> {target.decode(errors='replace')}")
            elif not is_dir and p.is_file():
                data = p.read_bytes()
                hits = [t.decode() for t in reduced if t in data]
                if hits:
                    found.append(f"{rel}: dependency/build file holds {hits}")
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
        if pkg.is_file() and not _excluded(ws, pkg.relative_to(ws).as_posix()):
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
                  *sorted((git_dir / "hooks").glob("*")),
                  *sorted((git_dir / "logs").rglob("*"))):  # reflogs
        if extra.is_file() and not extra.is_symlink():
            meta.append(extra.read_text(errors="replace"))
    for line in "\n".join(meta).splitlines():
        if _hint(line):
            found.append(f"git: {line.strip()[:160]}")
    return sorted(set(found))
