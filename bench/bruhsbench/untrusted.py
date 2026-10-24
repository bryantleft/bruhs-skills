"""Harness-side operations on trees an agent or agent-written code controlled (R22).

The harness itself is not sandboxed, so anything it does with an agent's files must
not let the agent steer it:

* :func:`read_file` / :func:`files` never follow a symlink (every path component is
  opened ``O_NOFOLLOW`` from the trusted root down) and accept only regular files with
  a single link; anything else raises :class:`UnsafePath` (callers skip and record it).
* :func:`overlay` copies trusted files into an untrusted tree, removing symlinks along
  every destination path first, so a planted ``tests -> ~/`` link can't redirect it.
* :func:`git` runs git on an agent-touched repo under the OS sandbox (writes only in
  the repo), with system/global config off and every config-driven command hook
  neutralized: fsmonitor, hooks, external diff, textconv, auto-gc and the
  ``filter.<name>.*`` drivers the repo config (with its includes) defines.
"""

from __future__ import annotations

import os
import shutil
import stat
import subprocess
from pathlib import Path

from .sandbox import real_home, wrap
from .workspace import GIT

_DIR_FLAGS = os.O_RDONLY | os.O_DIRECTORY | os.O_NOFOLLOW
_FILE_FLAGS = os.O_RDONLY | os.O_NOFOLLOW | os.O_NONBLOCK  # NONBLOCK: a FIFO can't hang us


class UnsafePath(ValueError):
    pass


def check_outside_home(path: Path) -> Path:
    """``path`` unless it resolves into the real home (an agent-planted symlink chain)."""
    if Path(os.path.realpath(path)).is_relative_to(real_home()):
        raise UnsafePath(f"{path} resolves into the real home")
    return Path(path)


def _parts(rel: str | Path) -> tuple[str, ...]:
    parts = Path(rel).parts
    if not parts or Path(rel).is_absolute() or any(p in ("..", ".") for p in parts):
        raise UnsafePath(f"not a plain relative path: {rel}")
    return parts


def _open_dir(root: Path, parts: tuple[str, ...]) -> int:
    """fd of ``root/parts...`` reached without following any symlink."""
    fd = os.open(root, _DIR_FLAGS)
    try:
        for part in parts:
            nxt = os.open(part, _DIR_FLAGS, dir_fd=fd)
            os.close(fd)
            fd = nxt
    except BaseException:
        os.close(fd)
        raise
    return fd


def read_file(root: Path, rel: str | Path) -> bytes:
    """Bytes of ``root/rel``; :class:`UnsafePath` unless every component is a real
    directory and the file is a regular, singly-linked file."""
    parts = _parts(rel)
    try:
        dfd = _open_dir(Path(root), parts[:-1])
        try:
            fd = os.open(parts[-1], _FILE_FLAGS, dir_fd=dfd)
        finally:
            os.close(dfd)
    except OSError as exc:
        raise UnsafePath(f"{Path(root) / rel}: {exc.strerror or exc}") from exc
    with os.fdopen(fd, "rb") as f:
        st = os.fstat(f.fileno())
        if not stat.S_ISREG(st.st_mode) or st.st_nlink != 1:
            raise UnsafePath(f"{Path(root) / rel}: not a regular single-link file")
        return f.read()


def read_text(root: Path, rel: str | Path) -> str:
    return read_file(root, rel).decode(errors="replace")


def files(root: Path, rel_dir: str | Path, suffix: str = "") -> list[str]:
    """Paths (relative to ``root``) of regular files under ``root/rel_dir`` ending in
    ``suffix``, found without following symlinks; [] if ``rel_dir`` isn't a real dir."""
    parts = _parts(rel_dir)
    try:
        top = _open_dir(Path(root), parts)
    except OSError:
        return []
    found = []
    try:
        for dirpath, _dirs, names, dfd in os.fwalk(".", dir_fd=top, follow_symlinks=False):
            for name in names:
                st = os.stat(name, dir_fd=dfd, follow_symlinks=False)
                if stat.S_ISREG(st.st_mode) and name.endswith(suffix):
                    found.append(str(Path(*parts, dirpath, name)))
    finally:
        os.close(top)
    return sorted(found)


def _clear(path: Path) -> None:
    if path.is_symlink() or path.is_file():
        path.unlink()
    elif path.exists():
        shutil.rmtree(path)


def overlay(src: Path, dest: Path) -> None:
    """Copy the trusted tree ``src`` into ``dest`` (an agent-controlled tree); a symlink
    or non-directory where a directory goes, and anything at a file's target, is
    removed first. Refuses a symlinked ``dest``."""
    if dest.is_symlink() or not dest.is_dir():
        raise UnsafePath(f"overlay destination {dest} is not a real directory")
    for dirpath, dirnames, filenames in os.walk(src):
        rel = Path(dirpath).relative_to(src)
        dirnames[:] = [d for d in dirnames if d not in ("__pycache__",)]
        target_dir = dest / rel
        if rel != Path("."):
            if target_dir.is_symlink() or (target_dir.exists() and not target_dir.is_dir()):
                _clear(target_dir)
            target_dir.mkdir(exist_ok=True)
        for name in filenames:
            if name == ".DS_Store":
                continue
            target = target_dir / name
            if target.is_symlink() or target.exists():
                _clear(target)
            fd = os.open(target, os.O_WRONLY | os.O_CREAT | os.O_EXCL | os.O_NOFOLLOW, 0o644)
            with os.fdopen(fd, "wb") as out, open(Path(dirpath) / name, "rb") as inp:
                shutil.copyfileobj(inp, out)


# --------------------------------------------------------------------------- git

GIT_ENV = {"GIT_CONFIG_NOSYSTEM": "1", "GIT_CONFIG_GLOBAL": "/dev/null",
           "GIT_ATTR_NOSYSTEM": "1", "GIT_TERMINAL_PROMPT": "0", "GIT_OPTIONAL_LOCKS": "0"}
HARDEN = ("-c", "core.fsmonitor=false", "-c", "core.hooksPath=/dev/null",
          "-c", "diff.external=", "-c", "gc.auto=0", "-c", "maintenance.auto=false",
          "-c", "core.untrackedCache=false", "-c", "protocol.allow=never")
DIFF_FLAGS = ("--no-ext-diff", "--no-textconv")
_DIFFING = ("diff", "log", "show")


def _git_env() -> dict[str, str]:
    env = {k: os.environ[k] for k in ("PATH", "LANG") if k in os.environ}
    return {**env, **GIT_ENV}


def _filter_names(repo: Path) -> list[str]:
    """``filter.<name>.*`` drivers in the repo's config, includes followed."""
    proc = subprocess.run(
        wrap([*GIT, *HARDEN, "config", "--includes", "--get-regexp", r"^filter\."],
             writable=[], extra_readable=[repo]),
        cwd=repo, env=_git_env(), capture_output=True, text=True)
    names = set()
    for line in proc.stdout.splitlines():
        key = line.split(" ", 1)[0]
        if key.count(".") >= 2:
            names.add(key[len("filter."):key.rindex(".")])
    return sorted(names)


def git(repo: Path, *args: str, write: bool = True, check: bool = True,
        text: bool = False) -> subprocess.CompletedProcess:
    """``git <args>`` in the agent-touched ``repo``, hardened and sandboxed."""
    repo = check_outside_home(repo)
    if repo.is_symlink():
        raise UnsafePath(f"repo {repo} is a symlink")
    neutral = []
    for name in _filter_names(repo):
        for key in ("clean", "smudge", "process"):
            neutral += ["-c", f"filter.{name}.{key}="]
        neutral += ["-c", f"filter.{name}.required=false"]
    sub, *rest = args
    flags = list(DIFF_FLAGS) if sub in _DIFFING else []
    cmd = [*GIT, *HARDEN, *neutral, sub, *flags, *rest]
    return subprocess.run(
        wrap(cmd, writable=[repo] if write else [], extra_readable=[repo]),
        cwd=repo, env=_git_env(), check=check, capture_output=True, text=text)
