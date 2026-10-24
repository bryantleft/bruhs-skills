"""macOS ``sandbox-exec`` confinement for every process that runs model-driven or
agent-written code (Ruling R19).

An isolated ``HOME`` is not a sandbox: a model with a file tool can still open any
absolute path. :func:`wrap` prefixes an argv with ``sandbox-exec -p <profile>``; the
profile (:func:`profile`) allows everything by default (network, processes, mach,
system paths) and then:

* denies all reads and writes under the real home (``Path.home()`` resolved, and its
  ``/System/Volumes/Data`` firmlink form);
* re-allows read-only access to the tool installs in :data:`READ_ALLOW`;
* re-allows read-write access to :data:`READ_WRITE_ALLOW`;
* allows ``file-read-metadata`` (stat, not contents or listings) on the home dir and
  the directories between it and each allowlisted path, so path traversal and
  ``realpath`` work;
* denies writes everywhere outside the home too, except the caller's ``writable``
  roots and :data:`SYSTEM_WRITABLE` (temp dirs, ``/dev``).

Later rules win in SBPL, so the order above is load-bearing.

Home paths allowed, and why. The CLI entries (launchers, binaries, ``~/.nvm`` for the
``npx`` chrome-devtools MCP, the keychain) are what the live probes in
``tests/test_sandbox.py`` / ``tests/test_homes.py`` need; the toolchain entries serve
task checks and dev servers, which run with ``HOME`` in their scratch dir
(``graders.commands.sandboxed_env``) and ``CARGO_HOME`` / ``RUSTUP_HOME`` /
``PLAYWRIGHT_BROWSERS_PATH`` pointing back at the real, read-only installs:

read-only
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
read-write
    ``~/Library/Keychains``      claude's default auth: the isolated home links
                                 ``Library/Keychains`` here (homes.py) and claude
                                 writes refreshed OAuth tokens back

Never allowed: ``~/.claude``, ``~/.codex``, ``~/.grok`` (other than bin/downloads),
``~/.agents``, ``~/Documents``, shell histories, ``~/.ssh``, ``~/.config`` and other
dotfiles. Chrome can't nest its own seatbelt sandbox inside this one, so the
chrome-devtools MCP launches it with ``--no-sandbox`` (homes.py); this sandbox still
confines it. There is no unsandboxed fallback: without ``/usr/bin/sandbox-exec``
:func:`wrap` raises :class:`SandboxUnavailable`.
"""

from __future__ import annotations

from collections.abc import Iterable
from pathlib import Path

SANDBOX_EXEC = Path("/usr/bin/sandbox-exec")
DATA_VOLUME = Path("/System/Volumes/Data")

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
READ_WRITE_ALLOW: tuple[Path, ...] = (
    Path("Library/Keychains"),
)
SYSTEM_WRITABLE: tuple[Path, ...] = (
    Path("/private/tmp"),
    Path("/private/var/folders"),
    Path("/dev"),
)


class SandboxUnavailable(RuntimeError):
    pass


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


def _ancestors(path: Path, stop: Path) -> list[Path]:
    """``stop`` and every directory between it and ``path`` (exclusive)."""
    out = [stop]
    for parent in reversed(path.parents):
        if parent.is_relative_to(stop) and parent != stop:
            out.append(parent)
    return out


def profile(*, writable: Iterable[Path], extra_readable: Iterable[Path] = ()) -> str:
    """SBPL for an untrusted process that may write only under ``writable``."""
    home = Path.home().resolve()
    reads = [home / p for p in READ_ALLOW] + [Path(p) for p in extra_readable]
    read_writes = [home / p for p in READ_WRITE_ALLOW]
    writes = [Path(p) for p in writable] + list(SYSTEM_WRITABLE)
    meta: dict[Path, None] = dict.fromkeys([*reversed(home.parents), home])
    for p in [*reads, *read_writes]:
        if p.resolve().is_relative_to(home):
            meta.update(dict.fromkeys(_ancestors(p.resolve(), home)))
    literals = " ".join(f"(literal {_q(f)})" for p in meta for f in _forms(p))
    return "\n".join([
        "(version 1)",
        "(allow default)",
        f"(deny file-read* file-write* {_subpaths([home])})",
        f"(allow file-read-metadata {literals})",
        f"(allow file-read* {_subpaths(reads)})",
        f"(allow file-read* file-write* {_subpaths(read_writes)})",
        '(deny file-write* (subpath "/"))',
        f"(allow file-write* {_subpaths(writes + read_writes)})",
        "",
    ])


def wrap(cmd: list[str], *, writable: Iterable[Path],
         extra_readable: Iterable[Path] = ()) -> list[str]:
    """``cmd`` run under :func:`profile`; raises :class:`SandboxUnavailable` if the
    sandbox can't be applied (never runs ``cmd`` unconfined)."""
    if not SANDBOX_EXEC.is_file():
        raise SandboxUnavailable(f"{SANDBOX_EXEC} not found; refusing to run {cmd[:1]} "
                                 "unsandboxed")
    return [str(SANDBOX_EXEC), "-p",
            profile(writable=writable, extra_readable=extra_readable), *cmd]
