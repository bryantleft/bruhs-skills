#!/usr/bin/env python3
"""write_bruhs_config.py — Atomically write .claude/bruhs.json.

Usage:
    write_bruhs_config.py [--root PATH] [--dry-run] < config.json
    write_bruhs_config.py --help

Reads a JSON document on stdin matching the bruhs config schema
(documented in ../SKILL.md), validates required fields, and writes it
to <root>/.claude/bruhs.json atomically (tmp file + os.replace()).

Schema requirements:
    - top-level must be an object
    - "stack" must be present and be an object
    - "tooling" must be present and be an object
    - if "integrations.linear" is present, it must include string
      "mcpServer" and string "team"

Flags:
    --root PATH   Project root (default: cwd). .claude/ is created if
                  it does not already exist.
    --dry-run     Print the would-be contents and target path to
                  stdout; do not touch disk.

Exit codes:
    0 — success
    2 — usage error, invalid JSON, or schema violation
    3 — filesystem error
"""

from __future__ import annotations

import argparse
import json
import os
import sys
from pathlib import Path
from typing import Any


def validate(data: Any) -> list[str]:
    errors: list[str] = []
    if not isinstance(data, dict):
        return ["config must be a JSON object"]
    if "stack" not in data:
        errors.append("missing required field: stack")
    elif not isinstance(data["stack"], dict):
        errors.append("field 'stack' must be an object")
    if "tooling" not in data:
        errors.append("missing required field: tooling")
    elif not isinstance(data["tooling"], dict):
        errors.append("field 'tooling' must be an object")

    integrations = data.get("integrations")
    if isinstance(integrations, dict):
        linear = integrations.get("linear")
        if linear is not None:
            if not isinstance(linear, dict):
                errors.append("integrations.linear must be an object")
            else:
                mcp_server = linear.get("mcpServer")
                team = linear.get("team")
                if not isinstance(mcp_server, str) or not mcp_server:
                    errors.append(
                        "integrations.linear.mcpServer must be a non-empty string"
                    )
                if not isinstance(team, str) or not team:
                    errors.append(
                        "integrations.linear.team must be a non-empty string"
                    )
    elif integrations is not None and not isinstance(integrations, dict):
        errors.append("integrations must be an object when present")

    return errors


def atomic_write(path: Path, content: str) -> None:
    tmp = path.with_suffix(path.suffix + ".tmp")
    with open(tmp, "w", encoding="utf-8") as fh:
        fh.write(content)
        fh.flush()
        os.fsync(fh.fileno())
    os.replace(tmp, path)


def main(argv: list[str]) -> int:
    parser = argparse.ArgumentParser(
        prog="write_bruhs_config.py",
        description="Atomically write .claude/bruhs.json from stdin JSON.",
    )
    parser.add_argument(
        "--root",
        default=os.getcwd(),
        help="Project root (default: cwd).",
    )
    parser.add_argument(
        "--dry-run",
        action="store_true",
        help="Print would-be contents and target path; do not touch disk.",
    )
    args = parser.parse_args(argv[1:])

    raw = sys.stdin.read()
    if not raw.strip():
        print("error: no JSON received on stdin", file=sys.stderr)
        return 2

    try:
        data = json.loads(raw)
    except json.JSONDecodeError as exc:
        print(f"error: invalid JSON on stdin: {exc}", file=sys.stderr)
        return 2

    errors = validate(data)
    if errors:
        for err in errors:
            print(f"error: {err}", file=sys.stderr)
        return 2

    root = Path(args.root).resolve()
    claude_dir = root / ".claude"
    target = claude_dir / "bruhs.json"
    rendered = json.dumps(data, indent=2, sort_keys=False) + "\n"

    if args.dry_run:
        print(f"--- would write to {target.as_posix()} ---")
        sys.stdout.write(rendered)
        return 0

    try:
        claude_dir.mkdir(parents=True, exist_ok=True)
    except OSError as exc:
        print(f"error: could not create {claude_dir}: {exc}", file=sys.stderr)
        return 3

    try:
        atomic_write(target, rendered)
    except OSError as exc:
        print(f"error: could not write {target}: {exc}", file=sys.stderr)
        return 3

    print(target.as_posix())
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv))
