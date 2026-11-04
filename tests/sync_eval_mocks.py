#!/usr/bin/env python3
"""sync_eval_mocks.py — Generate each eval case's Linear MCP mocks from one template.

Usage:
    tests/sync_eval_mocks.py [--check]

claude plugin eval never loads personal MCP servers, so a case that talks to
Linear needs a mocked server under the name its bruhs:state block uses. Mocks
can't be shared suite-wide (that would hand Linear tools to the cases that
test "no Linear configured"), and the eval loader rejects symlinks, so every
case that needs Linear gets its own copy. This script writes those copies.

For each evals/<case>/scaffold.sh, every `"mcpServer": "<name>"` it writes
gets evals/<case>/mocks/<name>/, built from tests/fixtures/linear-mock/ with
the team placeholders filled in from the server name (linear-perdix → team
PERDIX). Generated server directories a case no longer needs are removed;
mocks for other servers (any directory without linear_get_issue.md) are left
alone.

    --check   change nothing; exit 1 if any case's mocks are out of date

Exit codes: 0 in sync (or synced), 1 out of date under --check.
Stdlib only.
"""

from __future__ import annotations

import argparse
import hashlib
import re
import shutil
import sys
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parent.parent
EVALS = REPO_ROOT / "evals"
TEMPLATE = REPO_ROOT / "tests" / "fixtures" / "linear-mock"
SERVER_RE = re.compile(r'"mcpServer"\s*:\s*"([^"]+)"')
TEAM_KEYS = {"sonner": "SON"}  # workspaces whose ticket prefix isn't the server suffix


def team_values(server: str) -> dict[str, str]:
    suffix = server.split("linear-", 1)[-1] if server.startswith("linear-") else server
    key = TEAM_KEYS.get(suffix, re.sub(r"[^A-Za-z0-9]", "", suffix).upper() or "ENG")
    digest = hashlib.sha1(server.encode()).hexdigest()
    prefix = digest[:8]
    return {
        "__TEAM_UUID_PREFIX__": prefix,
        "__TEAM_UUID__": f"{prefix}-0000-4000-8000-000000000000",
        "__TEAM_KEY_LOWER__": key.lower(),
        "__TEAM_KEY__": key,
        "__TEAM_NAME__": key.capitalize(),
    }


def render(server: str) -> dict[str, bytes]:
    """Relative path → content for one server's mock directory."""
    values = team_values(server)
    out: dict[str, bytes] = {}
    for src in sorted(TEMPLATE.rglob("*")):
        if not src.is_file():
            continue
        rel = src.relative_to(TEMPLATE).as_posix()
        data = src.read_text()
        if not rel.startswith("fixtures/"):
            for placeholder, value in values.items():
                data = data.replace(placeholder, value)
        out[rel] = data.encode()
    return out


def is_generated(server_dir: Path) -> bool:
    return (server_dir / "linear_get_issue.md").is_file()


def current(server_dir: Path) -> dict[str, bytes]:
    return {
        p.relative_to(server_dir).as_posix(): p.read_bytes()
        for p in sorted(server_dir.rglob("*"))
        if p.is_file()
    }


def main(argv: list[str]) -> int:
    parser = argparse.ArgumentParser(description=__doc__.split("\n\n")[0])
    parser.add_argument("--check", action="store_true", help="report drift, change nothing")
    args = parser.parse_args(argv)

    stale: list[str] = []
    for case in sorted(p for p in EVALS.iterdir() if p.is_dir() and not p.name.startswith("_")):
        scaffold = case / "scaffold.sh"
        wanted = set(SERVER_RE.findall(scaffold.read_text())) if scaffold.is_file() else set()
        mocks = case / "mocks"

        existing = {d.name for d in mocks.iterdir() if d.is_dir() and is_generated(d)} if mocks.is_dir() else set()
        for server in sorted(existing - wanted):
            stale.append(f"{case.name}: mocks/{server}/ is no longer needed")
            if not args.check:
                shutil.rmtree(mocks / server)

        for server in sorted(wanted):
            target = mocks / server
            files = render(server)
            if target.is_dir() and current(target) == files:
                continue
            stale.append(f"{case.name}: mocks/{server}/ is out of date")
            if not args.check:
                if target.exists():
                    shutil.rmtree(target)
                for rel, data in files.items():
                    path = target / rel
                    path.parent.mkdir(parents=True, exist_ok=True)
                    path.write_bytes(data)

        if not args.check and mocks.is_dir() and not any(mocks.iterdir()):
            mocks.rmdir()

    if args.check:
        for line in stale:
            print(line, file=sys.stderr)
        if stale:
            print("run: python3 tests/sync_eval_mocks.py", file=sys.stderr)
            return 1
        print("eval mocks in sync")
        return 0
    print(f"synced {len(stale)} mock directories" if stale else "eval mocks already in sync")
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
