#!/usr/bin/env python3
"""detect_mcp_servers.py — Group installed MCP servers by category, across agents.

Usage:
    detect_mcp_servers.py [--root DIR]
    detect_mcp_servers.py --config PATH [--config PATH ...]
    detect_mcp_servers.py --help

With no --config, reads the MCP configuration of every agent it knows,
at user level and for the project at --root (default: cwd):

    Claude Code   ~/.claude.json (top level and per project), <root>/.mcp.json
    Codex         $CODEX_HOME/config.toml (default ~/.codex), <root>/.codex/config.toml
    Grok CLI      ~/.grok/config.toml, <root>/.grok/config.toml
    Cursor        ~/.cursor/mcp.json, <root>/.cursor/mcp.json
    Gemini CLI    ~/.gemini/settings.json, <root>/.gemini/settings.json
    VS Code       <root>/.vscode/mcp.json
    Windsurf      ~/.codeium/windsurf/mcp_config.json

With --config, reads only the given files. The format is taken from the
extension: .toml files are read for [mcp_servers.<name>] tables, JSON
files for "mcpServers", "servers" and "projects.*.mcpServers".

Emits JSON listing server names grouped by category, plus where each
name was found:

    {
      "linear": ["linear-perdix", "linear-sonner"],
      "notion": ["notion"],
      "github": ["github"],
      "other":  ["context7", "shadcn"],
      "sources": {"linear-perdix": ["claude-code:~/.claude.json", "codex:~/.codex/config.toml"], ...}
    }

Categories come from the server name: names containing "linear",
"notion" or "github" go to that bucket, everything else to "other".

Exit codes:
    0 — success (missing files are skipped; in the default scan an
        unreadable or invalid file is reported on stderr and skipped)
    2 — a file named with --config is invalid or unreadable
"""

from __future__ import annotations

import argparse
import json
import os
import re
import sys
from pathlib import Path

CATEGORIES = ("linear", "notion", "github")
TOML_TABLE_RE = re.compile(r'^\s*\[mcp_servers\.(?:"([^"]+)"|\'([^\']+)\'|([A-Za-z0-9_-]+))')


class ConfigError(Exception):
    pass


def categorize(name: str) -> str:
    lowered = name.lower()
    for cat in CATEGORIES:
        if cat in lowered:
            return cat
    return "other"


def names_from_json(data: object) -> set[str]:
    """Server names from the JSON shapes agents use."""
    names: set[str] = set()
    if not isinstance(data, dict):
        raise ConfigError("top-level is not an object")
    for key in ("mcpServers", "servers"):
        block = data.get(key)
        if isinstance(block, dict):
            names.update(str(k) for k in block)
    projects = data.get("projects")
    if isinstance(projects, dict):
        for proj in projects.values():
            if isinstance(proj, dict) and isinstance(proj.get("mcpServers"), dict):
                names.update(str(k) for k in proj["mcpServers"])
    return names


def names_from_toml(text: str) -> set[str]:
    """Server names from [mcp_servers.<name>] tables (Codex, Grok CLI)."""
    try:
        import tomllib  # Python 3.11+
    except ModuleNotFoundError:
        tomllib = None
    if tomllib is not None:
        try:
            data = tomllib.loads(text)
        except tomllib.TOMLDecodeError as exc:
            raise ConfigError(f"invalid TOML: {exc}") from exc
        servers = data.get("mcp_servers")
        return {str(k) for k in servers} if isinstance(servers, dict) else set()
    names: set[str] = set()
    for line in text.splitlines():
        m = TOML_TABLE_RE.match(line)
        if m:
            names.add(next(g for g in m.groups() if g))
    return names


def read_names(path: Path) -> set[str]:
    try:
        text = path.read_text(encoding="utf-8")
    except OSError as exc:
        raise ConfigError(f"could not read: {exc}") from exc
    if path.suffix == ".toml":
        return names_from_toml(text)
    try:
        data = json.loads(text)
    except json.JSONDecodeError as exc:
        raise ConfigError(f"not valid JSON: {exc}") from exc
    return names_from_json(data)


def default_sources(root: Path) -> list[tuple[str, Path]]:
    home = Path.home()
    codex_home = Path(os.environ.get("CODEX_HOME", home / ".codex"))
    return [
        ("claude-code", home / ".claude.json"),
        ("claude-code", root / ".mcp.json"),
        ("codex", codex_home / "config.toml"),
        ("codex", root / ".codex" / "config.toml"),
        ("grok", home / ".grok" / "config.toml"),
        ("grok", root / ".grok" / "config.toml"),
        ("cursor", home / ".cursor" / "mcp.json"),
        ("cursor", root / ".cursor" / "mcp.json"),
        ("gemini", home / ".gemini" / "settings.json"),
        ("gemini", root / ".gemini" / "settings.json"),
        ("vscode", root / ".vscode" / "mcp.json"),
        ("windsurf", home / ".codeium" / "windsurf" / "mcp_config.json"),
    ]


def display(path: Path) -> str:
    home = str(Path.home())
    s = str(path)
    return "~" + s[len(home):] if s.startswith(home + os.sep) else s


def main(argv: list[str]) -> int:
    parser = argparse.ArgumentParser(
        prog="detect_mcp_servers.py",
        description="List installed MCP servers, across agents, grouped by category.",
    )
    parser.add_argument("--config", action="append", help="read only this file (repeatable)")
    parser.add_argument("--root", default=".", help="project root for project-level configs (default: cwd)")
    args = parser.parse_args(argv[1:])

    explicit = args.config is not None
    if explicit:
        sources = [("config", Path(p)) for p in args.config]
    else:
        sources = default_sources(Path(args.root).resolve())

    found: dict[str, list[str]] = {}
    for agent, path in sources:
        if not path.is_file():
            continue
        try:
            names = read_names(path)
        except ConfigError as exc:
            print(f"error: {path}: {exc}", file=sys.stderr)
            if explicit:
                return 2
            continue
        for name in names:
            found.setdefault(name, []).append(f"{agent}:{display(path)}")

    result: dict[str, object] = {cat: [] for cat in (*CATEGORIES, "other")}
    for name in sorted(found):
        result[categorize(name)].append(name)
    result["sources"] = {name: found[name] for name in sorted(found)}

    print(json.dumps(result, indent=2))
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv))
