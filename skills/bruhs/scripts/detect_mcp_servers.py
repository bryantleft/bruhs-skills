#!/usr/bin/env python3
"""detect_mcp_servers.py — Group installed MCP servers by category.

Usage:
    detect_mcp_servers.py [--config PATH]
    detect_mcp_servers.py --help

Reads ~/.claude.json (or --config PATH) and emits JSON listing MCP
servers grouped by category:

    {
      "linear": ["linear-sonner", "linear-perdix"],
      "notion": ["notion"],
      "github": ["github"],
      "other":  ["context7", "shadcn", "vercel"]
    }

Categories are derived from the server name: names containing "linear",
"notion", or "github" are bucketed accordingly; everything else lands
in "other".

Exit codes:
    0 — success (including when the config file is missing)
    2 — invalid JSON or unexpected IO error
"""

from __future__ import annotations

import argparse
import json
import os
import sys
from pathlib import Path


CATEGORIES = ("linear", "notion", "github")


def categorize(name: str) -> str:
    lowered = name.lower()
    for cat in CATEGORIES:
        if cat in lowered:
            return cat
    return "other"


def extract_server_names(data: dict) -> list[str]:
    """Pull MCP server names from the top-level and from project entries."""
    names: set[str] = set()
    top = data.get("mcpServers")
    if isinstance(top, dict):
        names.update(str(k) for k in top.keys())
    projects = data.get("projects")
    if isinstance(projects, dict):
        for proj in projects.values():
            if not isinstance(proj, dict):
                continue
            servers = proj.get("mcpServers")
            if isinstance(servers, dict):
                names.update(str(k) for k in servers.keys())
    return sorted(names)


def main(argv: list[str]) -> int:
    parser = argparse.ArgumentParser(
        prog="detect_mcp_servers.py",
        description="List installed MCP servers grouped by category.",
    )
    parser.add_argument(
        "--config",
        default=str(Path.home() / ".claude.json"),
        help="Path to claude config JSON (default: ~/.claude.json).",
    )
    args = parser.parse_args(argv[1:])

    config_path = Path(args.config)
    result: dict[str, list[str]] = {cat: [] for cat in CATEGORIES}
    result["other"] = []

    if not config_path.exists():
        print(json.dumps(result, indent=2))
        return 0

    try:
        text = config_path.read_text(encoding="utf-8")
    except OSError as exc:
        print(f"error: could not read {config_path}: {exc}", file=sys.stderr)
        return 2

    try:
        data = json.loads(text)
    except json.JSONDecodeError as exc:
        print(
            f"error: {config_path} is not valid JSON: {exc}",
            file=sys.stderr,
        )
        return 2

    if not isinstance(data, dict):
        print(
            f"error: {config_path} top-level is not an object",
            file=sys.stderr,
        )
        return 2

    for name in extract_server_names(data):
        result[categorize(name)].append(name)

    for cat in result:
        result[cat].sort()

    print(json.dumps(result, indent=2))
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv))
