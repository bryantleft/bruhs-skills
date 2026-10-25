"""Harness-side operations on trees an agent or agent-written code controlled (R22).

The harness itself is not sandboxed, so anything it does with an agent's files must
not let the agent steer it:

* :func:`read_file` / :func:`files` never follow a symlink (every path component is
  opened ``O_NOFOLLOW`` from the trusted root down) and accept only regular files with
  a single link; anything else raises :class:`UnsafePath` (callers skip and record it).
* :func:`overlay` copies trusted files into an untrusted tree, removing symlinks along
  every destination path first, so a planted ``tests -> ~/`` link can't redirect it.
* :func:`remove` deletes a tree by dir fds, removing symlinks as links.
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
from collections.abc import Iterable
from pathlib import Path

from .sandbox import real_home, work_base, wrap
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
                try:  # an entry can vanish mid-walk; just skip it
                    st = os.stat(name, dir_fd=dfd, follow_symlinks=False)
                except (FileNotFoundError, NotADirectoryError, OSError):
                    continue
                if stat.S_ISREG(st.st_mode) and name.endswith(suffix):
                    found.append(str(Path(*parts, dirpath, name)))
    finally:
        os.close(top)
    return sorted(found)


def _clear_at(dfd: int, name: str) -> None:
    """Remove ``name`` under ``dfd`` whether it's a symlink, file or directory."""
    try:
        st = os.stat(name, dir_fd=dfd, follow_symlinks=False)
    except FileNotFoundError:
        return
    if stat.S_ISDIR(st.st_mode):
        _rmtree_at(dfd, name)
    else:
        os.unlink(name, dir_fd=dfd)


def _rmtree_at(dfd: int, name: str) -> None:
    """Recursively remove ``name`` under ``dfd`` without following symlinks; entries that
    vanish meanwhile are skipped."""
    try:
        sub = os.open(name, os.O_RDONLY | os.O_DIRECTORY | os.O_NOFOLLOW, dir_fd=dfd)
    except FileNotFoundError:
        return
    try:
        try:  # a read-only dir (e.g. a Go module cache) can't have its entries unlinked
            os.fchmod(sub, 0o700)
        except OSError:
            pass
        for entry in os.listdir(sub):
            try:
                st = os.stat(entry, dir_fd=sub, follow_symlinks=False)
                if stat.S_ISDIR(st.st_mode):
                    _rmtree_at(sub, entry)
                else:
                    os.unlink(entry, dir_fd=sub)
            except FileNotFoundError:
                continue
    finally:
        os.close(sub)
    try:
        os.rmdir(name, dir_fd=dfd)
    except FileNotFoundError:
        pass


def remove(root: Path, name: str) -> None:
    """Delete ``root/name`` (file, symlink or whole tree) without following any symlink:
    ``root`` is opened ``O_NOFOLLOW`` and the tree is walked by dir fds, so a link an
    agent planted is removed as a link, never traversed. ``name`` must be one plain path
    component."""
    if _parts(name) != (name,):
        raise UnsafePath(f"not a single path component: {name!r}")
    fd = os.open(root, _DIR_FLAGS)
    try:
        _clear_at(fd, name)
    finally:
        os.close(fd)


def _child_dir(dfd: int, name: str) -> int:
    """Open (creating, never through a symlink) a real subdirectory ``name`` of ``dfd``."""
    try:
        return os.open(name, _DIR_FLAGS, dir_fd=dfd)
    except NotADirectoryError:
        _clear_at(dfd, name)
    except FileNotFoundError:
        pass
    except OSError:  # e.g. ELOOP: a symlink is in the way
        _clear_at(dfd, name)
    try:
        os.mkdir(name, 0o755, dir_fd=dfd)
    except FileExistsError:
        _clear_at(dfd, name)
        os.mkdir(name, 0o755, dir_fd=dfd)
    return os.open(name, _DIR_FLAGS, dir_fd=dfd)


def overlay(src: Path, dest: Path) -> None:
    """Copy the trusted tree ``src`` into the agent-controlled tree ``dest``, descending
    with ``O_NOFOLLOW`` dir fds so no symlink in an intermediate component is ever
    followed. A symlink or non-directory where a directory must go, and anything at a
    file's target, is removed first. Refuses a symlinked ``dest`` root."""
    if dest.is_symlink() or not dest.is_dir():
        raise UnsafePath(f"overlay destination {dest} is not a real directory")
    root = os.open(dest, _DIR_FLAGS)
    try:
        _overlay_into(Path(src), root)
    finally:
        os.close(root)


def _overlay_into(src_dir: Path, dfd: int) -> None:
    for entry in sorted(os.scandir(src_dir), key=lambda e: e.name):
        if entry.name in ("__pycache__", ".DS_Store"):
            continue
        if entry.is_dir(follow_symlinks=False):
            child = _child_dir(dfd, entry.name)
            try:
                _overlay_into(Path(entry.path), child)
            finally:
                os.close(child)
        elif entry.is_file(follow_symlinks=False):
            _clear_at(dfd, entry.name)
            fd = os.open(entry.name, os.O_WRONLY | os.O_CREAT | os.O_EXCL | os.O_NOFOLLOW,
                         0o644, dir_fd=dfd)
            with os.fdopen(fd, "wb") as out, open(entry.path, "rb") as inp:
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


def _filter_names(repo: Path, denied: Iterable[Path]) -> list[str]:
    """``filter.<name>.*`` drivers in the repo's config, includes followed. NUL-delimited
    so values with newlines can't inject keys. Fails closed: if the config can't be read
    the drivers are unknown, so :class:`UnsafePath` is raised instead of running git."""
    proc = subprocess.run(
        wrap([*GIT, *HARDEN, "config", "--includes", "--null", "--get-regexp", r"^filter\."],
             writable=[], extra_readable=[repo], denied=denied),
        cwd=repo, env=_git_env(), capture_output=True, text=True)
    if proc.returncode == 1 and not proc.stdout:  # no matching keys
        return []
    if proc.returncode != 0:
        raise UnsafePath(f"git config unreadable in {repo} (exit {proc.returncode}): "
                         f"{proc.stderr.strip()[-300:]}")
    names = set()
    for record in proc.stdout.split("\0"):
        key = record.split("\n", 1)[0]  # "key\nvalue"; key is the first line
        if key.startswith("filter.") and key.count(".") >= 2:
            names.add(key[len("filter."):key.rindex(".")])
    return sorted(names)


def git(repo: Path, *args: str, write: bool = True, check: bool = True,
        text: bool = False, denied: Iterable[Path] = ()) -> subprocess.CompletedProcess:
    """``git <args>`` in the agent-touched ``repo``, hardened and sandboxed. ``denied``
    roots (e.g. the work root) are unreadable so a sibling run can't be touched."""
    repo = check_outside_home(repo)
    if repo.is_symlink():
        raise UnsafePath(f"repo {repo} is a symlink")
    # Always deny the work base so git on one repo can't touch a sibling run (R21/R22).
    denied = [*denied, work_base()]
    neutral = []
    for name in _filter_names(repo, denied):
        for key in ("clean", "smudge", "process"):
            neutral += ["-c", f"filter.{name}.{key}="]
        neutral += ["-c", f"filter.{name}.required=false"]
    sub, *rest = args
    flags = list(DIFF_FLAGS) if sub in _DIFFING else []
    cmd = [*GIT, *HARDEN, *neutral, sub, *flags, *rest]
    return subprocess.run(
        wrap(cmd, writable=[repo] if write else [], extra_readable=[repo], denied=denied),
        cwd=repo, env=_git_env(), check=check, capture_output=True, text=text)
