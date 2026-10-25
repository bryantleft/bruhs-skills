"""macOS ``sandbox-exec`` confinement for every process that runs model-driven or
agent-written code (Rulings R19-R22).

An isolated ``HOME`` is not a sandbox: a model with a file tool can still open any
absolute path, connect to any unix socket, read the clipboard or launch an app outside
the sandbox. :func:`wrap` prefixes an argv with ``sandbox-exec -p <profile>``; the
profile (:func:`profile`) allows everything by default and then clamps it down (later
SBPL rules win):

1. *Blocked roots* get no reads, no writes and no unix-socket connects: the real home
   (from the password database, :func:`real_home`), the work base (every run, judge,
   grading and export root, :func:`work_base`), the caller's ``denied`` roots,
   ``/private/tmp``, the private-TMPDIR base (:func:`tmp_base`) and the per-user Darwin
   dir ``/private/var/folders/<x>/<y>`` (its ``T`` temp and ``C`` cache). Every path
   rule is emitted in its ``/System/Volumes/Data`` firmlink form too.
2. ``file-read-metadata`` (stat only, no listing or contents) on the blocked roots,
   their ancestors and the dirs leading to each re-allowed path, so traversal,
   ``getcwd`` and ``realpath`` work.
3. Read-only: the tool installs in :data:`READ_ALLOW` and ``extra_readable``.
4. Writes denied everywhere, then allowed on ``/dev``, the caller's ``writable`` roots
   (each with its private ``TMPDIR``, see below), and two strictly-anchored name forms in
   the (unlistable) Darwin temp dir:
   ``mktemp``'s ``tmp.XXXXXXXXXX`` (macOS ``mktemp`` ignores ``TMPDIR``) and Chrome's
   ProcessSingleton dir ``com.google.Chrome.XXXXXX`` (file part).
5. **Unix sockets** (``network-outbound`` to a path): denied everywhere, then allowed
   only for the system resolver (:data:`SYSTEM_SOCKETS`, mDNSResponder -- DNS uses a
   unix socket) and the caller's ``writable`` roots (a run's own dev-server / MCP
   sockets). Nothing else: the user's ssh-agent, ``~/.docker/run/docker.sock``, and
   other runs' or the user's real Chrome singleton sockets are all unreachable. TCP
   (``remote ip``) is untouched -- localhost dev servers and the chrome-devtools
   websocket keep working (see the localhost note below).
6. Enumeration is closed: ``process-info*`` is denied except ``(target self)`` (no
   ``lsof``/``ps`` on other processes) and ``sysctl`` ``net.local.*`` is denied (no
   ``netstat -f unix`` listing of every bound unix socket on the machine).
7. ``lsopen`` denied: ``open``/LaunchServices can't launch an app (an app launches as a
   child of launchd, outside this sandbox -- the classic escape). ``appleevent-send``
   denied: this is the **primary barrier** against Apple-Event escapes -- an event to a
   running app (e.g. Finder) fails at the sender (``-600``); macOS' own Automation/TCC
   check (``-10004``) is only a second layer behind it. Pasteboard mach services
   (:data:`DENIED_MACH`) denied so ``pbpaste`` can't read the user's clipboard.

Private ``TMPDIR`` (R37). A process's ``TMPDIR`` is not inside its root but at
:func:`tmp_dir` ``= <tmp base>/<12 hex of the root's path hash>`` (default base
``/private/tmp/bb``, ``$BRUHSBENCH_TMP``): the Convex local backend binds a unix socket
under ``TMPDIR``, and macOS limits a socket path to 104 bytes, so ``TMPDIR`` must stay
within :data:`MAX_TMPDIR_LEN` (77) characters however long the results-dir name or run id
is. :func:`profile` makes ``tmp_dir(root)`` read-write for each ``writable`` root and
nothing else under the base, so each process still reaches only its own ``TMPDIR`` (R21).
:func:`private_tmp` creates it (failing fast with :class:`TmpDirTooLong`);
:func:`remove_private_tmp` deletes it with its root.

The MCP's Chrome keeps its ProcessSingleton dir in the Darwin temp dir (macOS Chrome
hard-codes it under ``confstr`` ``_CS_DARWIN_USER_TEMP_DIR``, ignoring ``$TMPDIR``, a
short ``--user-data-dir`` and every flag -- verified), so the profile allows creating
``com.google.Chrome.XXXXXX`` there (file ops only). It needs no outbound connect: Chrome
binds its own fresh singleton, and a refused connect to a pre-existing one just means
"no other instance" (verified: the MCP works without it). So no Chrome singleton --
another run's or the user's real one -- can be connected to. Accepted limitation: **localhost TCP stays open**
(``127.0.0.1`` / ``::1``), because dev servers and the chrome-devtools MCP need it; a run
can in principle reach a port another run is listening on. Ports are picked free per
capture and runs are short-lived, so this is tolerated.

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

import hashlib
import logging
import os
import pwd
import re
import stat
from collections.abc import Iterable, Mapping
from pathlib import Path

SANDBOX_EXEC = Path("/usr/bin/sandbox-exec")
DATA_VOLUME = Path("/System/Volumes/Data")
DEFAULT_WORK_BASE = Path("/private/tmp/bruhsbench")
SHARED_TMP = Path("/private/tmp")
# R37: the Convex local backend binds a unix socket under TMPDIR and macOS caps a socket
# path (sun_path) at 104 bytes, so every private TMPDIR is short: <tmp base>/<12 hex>.
TMP_BASE_ENV = "BRUHSBENCH_TMP"
DEFAULT_TMP_BASE = Path("/private/tmp/bb")
MAX_TMPDIR_LEN = 77
TMP_ID_LEN = 12

log = logging.getLogger(__name__)

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
# Unix sockets every sandboxed process may connect to: the system DNS resolver.
SYSTEM_SOCKETS: tuple[Path, ...] = (
    Path("/private/var/run/mDNSResponder"),
)
# Pasteboard mach services; denied so pbpaste can't read the user's clipboard.
DENIED_MACH: tuple[tuple[str, str], ...] = (
    ("global-name-prefix", "com.apple.pasteboard"),
    ("global-name", "com.apple.pboard"),
)
# Strictly-anchored names in the (unlistable) Darwin temp dir. mktemp is file-only;
# Chrome's ProcessSingleton dir also needs a socket connect (see module docstring).
# The sandbox regex engine has no bounded-repetition ({n,}); anchor the prefix strictly
# instead (``tmp.`` / the Chrome bundle id), which is what keeps system names like
# ``com.apple.*`` from matching.
_MKTEMP_RE = r"tmp\.[A-Za-z0-9]+"
_CHROME_RE = r"(com\.google\.Chrome|org\.chromium\.Chromium)\.[A-Za-z0-9]+"
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


def _literals(paths: Iterable[Path]) -> str:
    return " ".join(f"(literal {_q(f)})" for p in paths for f in _forms(p))


def _temp_regex(tmp: Path, name: str) -> str:
    dirs = "|".join(re.escape(str(f)) for f in _forms(tmp))
    return f'(regex #"^({dirs})/{name}(/|$)")'


def _ancestors(path: Path, stop: Path) -> list[Path]:
    """``stop`` and every directory between it and ``path`` (exclusive)."""
    return [stop] + [d for d in reversed(path.parents) if d.is_relative_to(stop) and d != stop]


def profile(*, writable: Iterable[Path], extra_readable: Iterable[Path] = (),
            denied: Iterable[Path] = ()) -> str:
    """SBPL for an untrusted process that may write only under ``writable``.

    The blocked roots (real home, work base, ``denied``, shared temp dirs, the private
    TMPDIR base) are unreadable, unwritable and unconnectable except for
    :data:`READ_ALLOW`, ``extra_readable`` (read-only) and ``writable`` plus each
    writable root's :func:`tmp_dir` (read-write, incl. their own unix sockets). Raises
    ``ValueError`` for an ``extra_readable`` or ``writable`` root that resolves into the
    real home.
    """
    home = real_home()
    tmp = darwin_temp_dir()
    blocked = [home, *(Path(d).resolve()
                       for d in (work_base(), *denied, SHARED_TMP, tmp_base()))]
    if tmp is not None:
        blocked.append(tmp.parent)
    extra = [Path(p).resolve() for p in extra_readable]
    # each writable root brings its own private TMPDIR (R37), and only its own
    writes = [Path(q).resolve() for p in writable for q in (p, tmp_dir(p))]
    if inside := [p for p in extra + writes if p.is_relative_to(home)]:
        raise ValueError(f"sandbox roots resolve into the real home: {inside}")
    reads = [home / p for p in READ_ALLOW] + extra

    meta: dict[Path, None] = dict.fromkeys(d for b in blocked for d in [*reversed(b.parents), b])
    for p in [*reads, *writes, *([tmp / "x"] if tmp is not None else [])]:
        for b in blocked:
            if p.is_relative_to(b):
                meta.update(dict.fromkeys(_ancestors(p, b)))

    mach = " ".join(f"({f} {_q(n)})" for f, n in DENIED_MACH)
    rules = [
        "(version 1)",
        "(allow default)",
        f"(deny file-read* file-write* {_subpaths(blocked)})",
        f"(allow file-read-metadata {_literals(meta)})",
        f"(allow file-read* {_subpaths(reads)})",
        '(deny file-write* (subpath "/"))',
        f"(allow file-write* {_subpaths([*SYSTEM_WRITABLE, *writes])})",
        '(deny network-outbound (subpath "/"))',
        f"(allow network-outbound {_subpaths([*SYSTEM_SOCKETS, *writes])})",
        "(deny process-info*)",
        "(allow process-info* (target self))",
        # netstat/sysctl net.local.* lists every bound unix socket on the machine
        '(deny sysctl-read (sysctl-name-prefix "net.local"))',
        "(deny lsopen)",
        "(deny appleevent-send)",
        f"(deny mach-lookup {mach})",
    ]
    if writes:
        rules.append(f"(allow file-read* file-write* {_subpaths(writes)})")
    if tmp is not None:
        rules.append(f"(allow file-read* file-write* {_temp_regex(tmp, _MKTEMP_RE)})")
        rules.append(
            f"(allow file-read* file-write* {_temp_regex(tmp, _CHROME_RE)})")
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


# --------------------------------------------------------------------------- TMPDIR (R37)


class TmpDirInvalid(ValueError):
    """``$BRUHSBENCH_TMP`` can't hold the private ``TMPDIR``s."""


class TmpDirTooLong(TmpDirInvalid):
    """A private ``TMPDIR`` would be too long for a unix socket path under it."""


def tmp_base() -> Path:
    """Where private ``TMPDIR``s live (``$BRUHSBENCH_TMP``, default ``/private/tmp/bb``),
    with its parent resolved (``/tmp`` -> ``/private/tmp``) but not its last component, so
    a symlink planted there is refused by :func:`private_tmp`, never followed.
    :class:`TmpDirInvalid` for a relative ``$BRUHSBENCH_TMP``."""
    raw = os.environ.get(TMP_BASE_ENV) or str(DEFAULT_TMP_BASE)
    if not os.path.isabs(raw):
        raise TmpDirInvalid(f"${TMP_BASE_ENV}={raw!r} must be an absolute path")
    path = Path(os.path.normpath(raw))
    if path.name in ("", ".."):
        raise TmpDirInvalid(f"${TMP_BASE_ENV}={raw!r} must name a directory below /")
    return path.parent.resolve() / path.name


def tmp_dir(root: Path) -> Path:
    """The private ``TMPDIR`` of the sandboxed process whose writable root is ``root``:
    ``<tmp_base>/<12 hex of sha256(resolved root)>``, short whatever ``root`` is."""
    key = str(Path(root).resolve()).encode()
    return tmp_base() / hashlib.sha256(key).hexdigest()[:TMP_ID_LEN]


def check_tmp_base() -> None:
    """Raise :class:`TmpDirTooLong` if private ``TMPDIR``s would exceed
    :data:`MAX_TMPDIR_LEN` characters (only a long ``$BRUHSBENCH_TMP`` can do that; its
    resolved form is what counts)."""
    length = len(str(tmp_base())) + 1 + TMP_ID_LEN
    if length > MAX_TMPDIR_LEN:
        raise TmpDirTooLong(
            f"private TMPDIRs under {tmp_base()} would be {length} characters, over "
            f"{MAX_TMPDIR_LEN}: unix sockets under them (the Convex local backend's) would "
            f"not fit macOS' 104-byte socket path. Set ${TMP_BASE_ENV} to a shorter dir.")


def _real_dir(path: Path) -> bool:
    try:
        st = os.lstat(path)
    except FileNotFoundError:
        return False
    return stat.S_ISDIR(st.st_mode) and st.st_uid == os.getuid()


def _ensure_tmp_base() -> Path:
    """The tmp base, created ``0700``; refused if it is a symlink or someone else's
    (``/private/tmp`` is world-writable)."""
    base = tmp_base()
    try:
        os.mkdir(base, 0o700)
    except FileExistsError:
        pass
    if not _real_dir(base):
        raise SandboxUnavailable(f"{base} is not a directory you own (a symlink, or "
                                 f"another user's); set ${TMP_BASE_ENV}")
    if stat.S_IMODE(os.lstat(base).st_mode) & 0o077:
        os.chmod(base, 0o700)
    return base


def private_tmp(env: Mapping[str, str], root: Path) -> dict[str, str]:
    """``env`` with ``TMPDIR`` (and zsh's ``TMPPREFIX``, xcrun's ``xcrun_db``) at
    :func:`tmp_dir` of ``root`` (created): a sandboxed
    process has no shared temp dir to write to. :func:`profile` makes it writable for
    exactly the process that may write ``root``. Raises :class:`TmpDirTooLong` (R37)."""
    check_tmp_base()
    _ensure_tmp_base()
    tmp = tmp_dir(root)
    if os.path.lexists(tmp) and not _real_dir(tmp):  # e.g. a link a process left there
        remove_private_tmp(root)
    try:
        os.mkdir(tmp, 0o700)
    except FileExistsError:  # reused (a real dir of ours, checked above): private again
        os.chmod(tmp, 0o700, follow_symlinks=False)
    # Temp files that ignore TMPDIR go there too: zsh here-documents use $TMPPREFIX
    # (default /tmp/zsh), and /usr/bin/git's xcrun shim caches in the Darwin temp dir
    # unless $xcrun_db names a file. Denied, they broke agents' scripts in both arms.
    return {**env, "TMPDIR": str(tmp), "TMPPREFIX": str(tmp / "zsh"),
            "xcrun_db": str(tmp / "xcrun_db")}


def remove_private_tmp(root: Path) -> None:
    """Delete ``root``'s private ``TMPDIR`` without following symlinks. Best effort: a
    failure is logged, never raised (it only costs space in ``/private/tmp``)."""
    from . import untrusted  # untrusted imports this module

    tmp = tmp_dir(root)
    if not os.path.lexists(tmp):
        return
    try:
        untrusted.remove(tmp.parent, tmp.name)
    except (OSError, ValueError) as exc:
        log.warning("could not delete private TMPDIR %s of %s: %s", tmp, root, exc)
