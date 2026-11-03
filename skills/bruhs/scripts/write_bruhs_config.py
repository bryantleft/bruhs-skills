#!/usr/bin/env python3
"""write_bruhs_config.py — DEPRECATED shim.

Project state now lives in marker-bounded blocks inside `CLAUDE.md` and
`AGENTS.md` rather than `.claude/bruhs.json`. This shim forwards the
incoming JSON to `sync_bruhs_block.py --kind state` so existing callers
keep working during the transition.

Behavior:
    - Validates and writes the state block exactly as `sync_bruhs_block.py`
      would. Prints a deprecation notice to stderr.
    - Does NOT write `.claude/bruhs.json` anymore.
    - Does NOT derive the rules block automatically. Callers that want
      stack-specific rules should additionally run:
          cat state.json | derive_stack_rules.py | sync_bruhs_block.py --kind rules

Flags mirror the original script (`--root`, `--dry-run`). Exit codes
match `sync_bruhs_block.py`.

Remove this shim in a future release once all callers are migrated.
"""

from __future__ import annotations

import argparse
import os
import subprocess
import sys
from pathlib import Path


def main(argv: list[str]) -> int:
    parser = argparse.ArgumentParser(
        prog="write_bruhs_config.py",
        description="(DEPRECATED) Forwarder to sync_bruhs_block.py --kind state.",
    )
    parser.add_argument("--root", default=os.getcwd())
    parser.add_argument("--dry-run", action="store_true")
    args = parser.parse_args(argv[1:])

    here = Path(__file__).resolve().parent
    target = here / "sync_bruhs_block.py"
    if not target.exists():
        print(
            f"error: sync_bruhs_block.py not found alongside this shim ({target})",
            file=sys.stderr,
        )
        return 3

    print(
        "warning: write_bruhs_config.py is deprecated — forwarding to "
        "sync_bruhs_block.py --kind state. State now lives in CLAUDE.md / AGENTS.md.",
        file=sys.stderr,
    )

    cmd = [sys.executable, str(target), "--kind", "state", "--root", args.root]
    if args.dry_run:
        cmd.append("--dry-run")

    raw = sys.stdin.read()
    proc = subprocess.run(cmd, input=raw, text=True)
    return proc.returncode


if __name__ == "__main__":
    sys.exit(main(sys.argv))
