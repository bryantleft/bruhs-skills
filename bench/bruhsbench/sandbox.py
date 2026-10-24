"""macOS ``sandbox-exec`` confinement for every process that runs model-driven or
agent-written code (Rulings R19-R22).

An isolated ``HOME`` is not a sandbox: a model with a file tool can still open any
absolute path. :func:`wrap` prefixes an argv with ``sandbox-exec -p <profile>``; the
profile (:func:`profile`) allows everything by default (network, processes, mach,
system paths) and then, in this order (later SBPL rules win):

1. *Blocked roots* get no reads, no writes and no unix-socket connects: the real home
   (from the password database, :func:`real_home`), the work base (every run, judge,
   grading and export root, :func:`work_base`), the caller's ``denied`` roots,
   ``/private/tmp`` (other processes' temp files and the launchd ``SSH_AUTH_SOCK``
   listener) and the per-user Darwin dir ``/private/var/folders/<x>/<y>`` (its ``T``
   temp and ``C`` cache dirs). Every path rule is also emitted in its
   ``/System/Volumes/Data`` firmlink form. Unix sockets matter: the ssh-agent and
   ``~/.docker/run/docker.sock`` are reachable by path, not by file reads.
2. ``file-read-metadata`` (stat only, no listing or contents) on the blocked roots,
   their ancestors and the directories leading to each re-allowed path, so path
   traversal, ``getcwd`` and ``realpath`` work.
3. Read-only: the tool installs in :data:`READ_ALLOW` and ``extra_readable``.
4. Writes are denied everywhere, then allowed on ``/dev``.
5. Read-write (and socket connects) in the Darwin temp dir only for names a process
   creates itself and nobody can guess or list (the dir is unreadable):
   ``mktemp``'s ``<prefix>.XXXXXXXXXX`` (macOS ``mktemp`` ignores ``TMPDIR``) and
   Chrome's ProcessSingleton dirs (``com.google.Chrome.XXXXXX``; the chrome-devtools
   MCP's Chrome aborts without one, and it too ignores ``TMPDIR``)).
   The shared xcrun cache (``xcrun_db``) stays unwritable, since it steers the user's
   own ``/usr/bin`` developer tools; those shims still work but print a "couldn't
   create cache file" warning to stderr.
6. Read-write on the caller's ``writable`` roots. Callers point ``TMPDIR`` inside one
   (:func:`private_tmp`), so no temp dir is shared between runs.

Home paths readable, and why. The CLI entries (launchers, binaries, ``~/.nvm`` for the
``npx`` chrome-devtools MCP) are what the live probes in ``tests/test_sandbox.py`` /
``tests/test_homes.py`` need; the toolchain entries serve task checks and dev servers,
which run with ``HOME`` in their scratch dir (``graders.commands.sandboxed_env``) and
``CARGO_HOME`` / ``RUSTUP_HOME`` / ``PLAYWRIGHT_BROWSERS_PATH`` pointing back at the
real, read-only installs:

    ``~/.local/bin``             the ``claude`` and ``uv`` launchers (symlinks into the
                                 dirs below)
    ``~/.local/share/claude``    the claude binary (``versions/<v>``)
    ``~/.local/share/uv/python`` uv-managed interpreters that venvs (task setup's
                                 ``uv sync``, the harness's own) symlink to
    ``~/.grok/bin``              the ``grok`` launcher symlink
    ``~/.grok/downloads``        the grok binary it points to
    ``~/.nvm``                   node/npx/pnpm (chrome-devtools MCP via ``npx``; JS
                                 checks and dev servers)
    ``~/.cargo``                 cargo/rustc proxies for Rust checks
    ``~/.rustup``                the toolchains those proxies run
    ``~/Library/pnpm``           pnpm's global bin dir (on PATH)
    ``~/Library/Caches/ms-playwright``  Playwright's browsers (checks that run it)

Nothing in the home is writable. Never readable: ``~/.claude``, ``~/.codex``,
``~/.grok`` (other than bin/downloads), ``~/.agents``, ``~/Documents``,
``~/Library/Keychains`` (R20: claude authenticates with a token only), shell
histories, ``~/.ssh``, ``~/.config`` and other dotfiles. Chrome can't nest its own
seatbelt sandbox inside this one, so the chrome-devtools MCP launches it with
``--no-sandbox`` (homes.py); this sandbox still confines it. There is no unsandboxed
fallback: without ``/usr/bin/sandbox-exec`` :func:`wrap` raises
:class:`SandboxUnavailable`.
"""

from __future__ import annotations

import os
import pwd
import re
from collections.abc import Iterable, Mapping
from pathlib import Path

SANDBOX_EXEC = Path("/usr/bin/sandbox-exec")
DATA_VOLUME = Path("/System/Volumes/Data")
DEFAULT_WORK_BASE = Path("/private/tmp/bruhsbench")
SHARED_TMP = Path("/private/tmp")
TMP_DIRNAME = ".tmp"

READ_ALLOW: tuple[Path, ...] = (
    Path(".local/bin"),
    Path(".local/share/claude"),
    Path(".local/share/uv/python"),
    Path(".grok/bin"),
    Path(".grok/downloads"),
    Path(".nvm"),
    Path(".cargo"),
    Path(".rustup"),
    Path("Library/pnpm"),
    Path("Library/Caches/ms-playwright"),
)
SYSTEM_WRITABLE: tuple[Path, ...] = (
    Path("/dev"),
)
_ALNUM = "[A-Za-z0-9]"
# Self-created, unguessable entries allowed in the (unlistable) Darwin temp dir
DARWIN_TEMP_NAMES = (
    r"[^/]+\." + _ALNUM * 10,  # mktemp's default <prefix>.XXXXXXXXXX
    r"(com\.google\.Chrome|org\.chromium\.Chromium)\." + _ALNUM * 6,  # Chrome singleton
)
_CS_DARWIN_USER_TEMP_DIR = 65537  # confstr name; missing from os.confstr_names


class SandboxUnavailable(RuntimeError):
    pass


def real_home() -> Path:
    """The user's home from the password database (not ``$HOME``, which the harness
    rewrites for agents and checks)."""
    entry = pwd.getpwuid(os.getuid()).pw_dir
    if not entry:
        raise SandboxUnavailable("no home directory in the password database")
    home = Path(entry).resolve()
    if not home.is_dir() or home == Path("/"):
        raise SandboxUnavailable(f"home directory {entry!r} does not resolve to a directory")
    return home


def work_base() -> Path:
    """Where every run, judge and grading root lives (``$BRUHSBENCH_WORK``)."""
    return Path(os.environ.get("BRUHSBENCH_WORK") or DEFAULT_WORK_BASE)


def darwin_temp_dir() -> Path | None:
    """The per-user temp dir (``/private/var/folders/<x>/<y>/T``), if there is one."""
    try:
        value = os.confstr(_CS_DARWIN_USER_TEMP_DIR)
    except (ValueError, OSError):
        return None
    return Path(value).resolve() if value else None


def _q(path: Path | str) -> str:
    """An SBPL string literal."""
    return '"' + str(path).replace("\\", "\\\\").replace('"', '\\"') + '"'


def _forms(path: Path) -> list[Path]:
    """``path`` resolved, plus its ``/System/Volumes/Data`` firmlink form."""
    real = Path(path).resolve()
    out = [real]
    if not real.is_relative_to(DATA_VOLUME):
        out.append(DATA_VOLUME / real.relative_to("/"))
    return out


def _subpaths(paths: Iterable[Path]) -> str:
    return " ".join(f"(subpath {_q(f)})" for p in paths for f in _forms(p))


def _temp_names(tmp: Path) -> str:
    dirs = "|".join(re.escape(str(f)) for f in _forms(tmp))
    names = "|".join(DARWIN_TEMP_NAMES)
    return f'(regex #"^({dirs})/({names})(/|$)")'


def _ancestors(path: Path, stop: Path) -> list[Path]:
    """``stop`` and every directory between it and ``path`` (exclusive)."""
    return [stop] + [d for d in reversed(path.parents) if d.is_relative_to(stop) and d != stop]


def profile(*, writable: Iterable[Path], extra_readable: Iterable[Path] = (),
            denied: Iterable[Path] = ()) -> str:
    """SBPL for an untrusted process that may write only under ``writable``.

    The blocked roots (real home, work base, ``denied``, shared temp dirs) are
    unreadable, unwritable and unconnectable except for :data:`READ_ALLOW`,
    ``extra_readable`` (read-only) and ``writable`` (read-write). Raises ``ValueError``
    for an ``extra_readable`` or ``writable`` root that resolves into the real home.
    """
    home = real_home()
    tmp = darwin_temp_dir()
    blocked = [home, *(Path(d).resolve() for d in (work_base(), *denied, SHARED_TMP))]
    if tmp is not None:
        blocked.append(tmp.parent)
    extra = [Path(p).resolve() for p in extra_readable]
    writes = [Path(p).resolve() for p in writable]
    if inside := [p for p in extra + writes if p.is_relative_to(home)]:
        raise ValueError(f"sandbox roots resolve into the real home: {inside}")
    reads = [home / p for p in READ_ALLOW] + extra

    meta: dict[Path, None] = dict.fromkeys(d for b in blocked for d in [*reversed(b.parents), b])
    for p in [*reads, *writes, *([tmp / "x"] if tmp is not None else [])]:
        for b in blocked:
            if p.is_relative_to(b):
                meta.update(dict.fromkeys(_ancestors(p, b)))
    literals = " ".join(f"(literal {_q(f)})" for p in meta for f in _forms(p))

    rules = [
        "(version 1)",
        "(allow default)",
        f"(deny file-read* file-write* {_subpaths(blocked)})",
        f"(deny network-outbound {_subpaths(blocked)})",
        f"(allow file-read-metadata {literals})",
        f"(allow file-read* {_subpaths(reads)})",
        '(deny file-write* (subpath "/"))',
        f"(allow file-write* {_subpaths(SYSTEM_WRITABLE)})",
    ]
    if tmp is not None:
        rules.append(f"(allow file-read* file-write* network-outbound {_temp_names(tmp)})")
    if writes:
        rules.append(f"(allow file-read* file-write* network-outbound {_subpaths(writes)})")
    return "\n".join(rules) + "\n"


def wrap(cmd: list[str], *, writable: Iterable[Path], extra_readable: Iterable[Path] = (),
         denied: Iterable[Path] = ()) -> list[str]:
    """``cmd`` run under :func:`profile`; raises :class:`SandboxUnavailable` if the
    sandbox can't be applied (never runs ``cmd`` unconfined)."""
    if not SANDBOX_EXEC.is_file():
        raise SandboxUnavailable(f"{SANDBOX_EXEC} not found; refusing to run {cmd[:1]} "
                                 "unsandboxed")
    return [str(SANDBOX_EXEC), "-p",
            profile(writable=writable, extra_readable=extra_readable, denied=denied), *cmd]


def private_tmp(env: Mapping[str, str], root: Path) -> dict[str, str]:
    """``env`` with ``TMPDIR`` at ``root/.tmp`` (created): a sandboxed process has no
    shared temp dir to write to."""
    tmp = Path(root) / TMP_DIRNAME
    tmp.mkdir(parents=True, exist_ok=True)
    return {**env, "TMPDIR": str(tmp)}
