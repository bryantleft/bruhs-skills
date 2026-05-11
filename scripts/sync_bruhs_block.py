#!/usr/bin/env python3
"""sync_bruhs_block.py — Atomically sync the bruhs-managed block in CLAUDE.md / AGENTS.md.

Replaces the older `write_bruhs_config.py` flow that wrote to
`.claude/bruhs.json`. The plugin now keeps project state and stack-specific
rules inside marker-bounded blocks in CLAUDE.md and AGENTS.md so the model
sees them every session.

Usage:
    # State block (JSON config, validated)
    cat state.json | sync_bruhs_block.py --kind state --root PATH
    # Rules block (pre-rendered markdown — produced by derive_stack_rules.py)
    cat rules.md  | sync_bruhs_block.py --kind rules --root PATH
    # Other flags
    --files CLAUDE.md,AGENTS.md   files to sync (default: both)
    --dry-run                      print would-be writes; touch nothing

Markers (versioned):
    <!-- bruhs:<kind>:begin v1 -->
    <!-- AUTO-MAINTAINED BY /bruhs. Edits will be overwritten. -->
    ...content...
    <!-- bruhs:<kind>:end -->

If the marker block is not found, it is appended to the end of the file
under a `## bruhs-managed` heading. If the file does not exist, it is
created with a minimal header. Existing content outside the markers is
never touched.

Schema validation (--kind state only):
    - top-level must be an object
    - "stack" must be present and be an object
    - "tooling" must be present and be an object
    - if "integrations.linear" is present, it must include string
      "mcpServer" and string "team"

Exit codes:
    0 — success
    2 — usage error, invalid JSON, or schema violation
    3 — filesystem error
"""

from __future__ import annotations

import argparse
import json
import os
import re
import sys
from pathlib import Path
from typing import Any

VALID_KINDS = ("state", "rules")
HEADER_COMMENT = (
    "<!-- AUTO-MAINTAINED BY /bruhs. Edits inside this block will be overwritten. "
    "Add hand-written rules outside the block. -->"
)


def validate_state(data: Any) -> list[str]:
    errors: list[str] = []
    if not isinstance(data, dict):
        return ["state must be a JSON object"]
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
    elif integrations is not None:
        errors.append("integrations must be an object when present")

    return errors


def render_state_body(state: dict) -> str:
    return (
        "### Project State (managed by /bruhs)\n\n"
        "```json\n"
        + json.dumps(state, indent=2) + "\n"
        + "```\n"
    )


def render_rules_body(rules_md: str) -> str:
    rules_md = rules_md.strip()
    if not rules_md:
        rules_md = "_No stack-specific rules detected._"
    return (
        "### Stack-Specific Rules (managed by /bruhs)\n\n"
        f"{rules_md}\n"
    )


def block_text(kind: str, body: str) -> str:
    begin = f"<!-- bruhs:{kind}:begin v1 -->"
    end = f"<!-- bruhs:{kind}:end -->"
    return f"{begin}\n{HEADER_COMMENT}\n\n{body}\n{end}"


def splice_block(existing: str, kind: str, new_block: str) -> str:
    """Replace existing bruhs:<kind> block, or append if not present."""
    pattern = re.compile(
        rf"<!--\s*bruhs:{re.escape(kind)}:begin[^>]*-->.*?<!--\s*bruhs:{re.escape(kind)}:end\s*-->",
        re.DOTALL,
    )
    if pattern.search(existing):
        return pattern.sub(new_block, existing, count=1)

    sep = "" if existing.endswith("\n\n") else ("\n" if existing.endswith("\n") else "\n\n")
    return f"{existing}{sep}\n## bruhs-managed\n\n{new_block}\n"


def ensure_file(path: Path) -> str:
    if path.exists():
        return path.read_text(encoding="utf-8")
    if path.name == "CLAUDE.md":
        return "# CLAUDE.md\n\nProject instructions for Claude Code.\n"
    if path.name == "AGENTS.md":
        return "# AGENTS.md\n\nProject instructions for AI coding agents.\n"
    return ""


def atomic_write(path: Path, content: str) -> None:
    tmp = path.with_suffix(path.suffix + ".tmp")
    with open(tmp, "w", encoding="utf-8") as fh:
        fh.write(content)
        fh.flush()
        os.fsync(fh.fileno())
    os.replace(tmp, path)


def main(argv: list[str]) -> int:
    parser = argparse.ArgumentParser(
        prog="sync_bruhs_block.py",
        description="Sync the bruhs-managed block in CLAUDE.md / AGENTS.md.",
    )
    parser.add_argument("--kind", required=True, choices=VALID_KINDS)
    parser.add_argument("--root", default=os.getcwd())
    parser.add_argument(
        "--files",
        default="CLAUDE.md,AGENTS.md",
        help="Comma-separated filenames relative to root (default: CLAUDE.md,AGENTS.md)",
    )
    parser.add_argument("--dry-run", action="store_true")
    args = parser.parse_args(argv[1:])

    raw = sys.stdin.read()
    if not raw.strip():
        print("error: no content received on stdin", file=sys.stderr)
        return 2

    if args.kind == "state":
        try:
            state = json.loads(raw)
        except json.JSONDecodeError as exc:
            print(f"error: invalid JSON on stdin: {exc}", file=sys.stderr)
            return 2
        errs = validate_state(state)
        if errs:
            for err in errs:
                print(f"error: {err}", file=sys.stderr)
            return 2
        body = render_state_body(state)
    else:
        body = render_rules_body(raw)

    new_block = block_text(args.kind, body)
    root = Path(args.root).resolve()
    filenames = [f.strip() for f in args.files.split(",") if f.strip()]

    seen: set[Path] = set()
    written: list[str] = []
    for name in filenames:
        path = root / name
        real = path.resolve() if path.exists() else path
        if real in seen:
            continue
        seen.add(real)

        try:
            existing = ensure_file(path)
        except OSError as exc:
            print(f"error: could not read {path}: {exc}", file=sys.stderr)
            return 3

        updated = splice_block(existing, args.kind, new_block)
        if args.dry_run:
            print(f"--- would write {path.as_posix()} ---")
            sys.stdout.write(updated)
            continue

        try:
            path.parent.mkdir(parents=True, exist_ok=True)
            atomic_write(path, updated)
        except OSError as exc:
            print(f"error: could not write {path}: {exc}", file=sys.stderr)
            return 3
        written.append(path.as_posix())

    if not args.dry_run:
        for p in written:
            print(p)
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv))
