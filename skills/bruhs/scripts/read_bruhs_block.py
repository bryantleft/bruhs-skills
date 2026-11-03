#!/usr/bin/env python3
"""read_bruhs_block.py — Read a bruhs-managed block from CLAUDE.md / AGENTS.md.

Used by commands (cook, yeet, slop, doodle) to load project state previously
written by `sync_bruhs_block.py`. Replaces direct reads of `.claude/bruhs.json`.

Usage:
    read_bruhs_block.py [--kind state|rules] [--root PATH] [--files CLAUDE.md,AGENTS.md]

Read order:
    Tries each file in --files order. The first file containing a matching
    block wins. Default order: CLAUDE.md, AGENTS.md.

Output:
    --kind state (default): the JSON inside the ```json ... ``` fence is
                            printed to stdout.
    --kind rules: the markdown body (everything between the markers, minus
                  the auto-maintained header comment) is printed to stdout.

Legacy fallback:
    For `--kind state`, if neither file contains a state block, the script
    falls back to reading `.claude/bruhs.json` if present. This eases the
    transition for projects that haven't been migrated yet.

Exit codes:
    0 — found and printed
    1 — no block found in any file (and no legacy bruhs.json for state)
    2 — usage error
"""

from __future__ import annotations

import argparse
import os
import re
import sys
from pathlib import Path

VALID_KINDS = ("state", "rules")


def find_block(text: str, kind: str) -> str | None:
    pattern = re.compile(
        rf"<!--\s*bruhs:{re.escape(kind)}:begin[^>]*-->\s*(?:<!--[^>]*-->)?\s*(.*?)\s*<!--\s*bruhs:{re.escape(kind)}:end\s*-->",
        re.DOTALL,
    )
    m = pattern.search(text)
    if not m:
        return None
    return m.group(1).strip()


def extract_json(body: str) -> str | None:
    m = re.search(r"```json\s*(.*?)```", body, re.DOTALL)
    if not m:
        return None
    return m.group(1).strip()


def main(argv: list[str]) -> int:
    parser = argparse.ArgumentParser(
        prog="read_bruhs_block.py",
        description="Read a bruhs-managed block from CLAUDE.md / AGENTS.md.",
    )
    parser.add_argument("--kind", default="state", choices=VALID_KINDS)
    parser.add_argument("--root", default=os.getcwd())
    parser.add_argument(
        "--files",
        default="CLAUDE.md,AGENTS.md",
        help="Comma-separated filenames relative to root (default: CLAUDE.md,AGENTS.md)",
    )
    args = parser.parse_args(argv[1:])

    root = Path(args.root).resolve()
    filenames = [f.strip() for f in args.files.split(",") if f.strip()]

    for name in filenames:
        path = root / name
        if not path.exists():
            continue
        text = path.read_text(encoding="utf-8")
        body = find_block(text, args.kind)
        if body is None:
            continue
        if args.kind == "state":
            payload = extract_json(body)
            if payload is None:
                print(
                    f"error: state block in {path} missing ```json fence",
                    file=sys.stderr,
                )
                return 1
            sys.stdout.write(payload + "\n")
            return 0
        sys.stdout.write(body + "\n")
        return 0

    if args.kind == "state":
        legacy = root / ".claude" / "bruhs.json"
        if legacy.exists():
            sys.stdout.write(legacy.read_text(encoding="utf-8"))
            print(
                f"warning: read legacy {legacy.as_posix()} — run /bruhs:claim to migrate",
                file=sys.stderr,
            )
            return 0

    print(
        f"error: no bruhs:{args.kind} block found in {', '.join(filenames)}",
        file=sys.stderr,
    )
    return 1


if __name__ == "__main__":
    sys.exit(main(sys.argv))
