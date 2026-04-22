#!/usr/bin/env python3
"""detect_stack.py — Detect a project's tech stack from config files.

Usage:
    detect_stack.py [PROJECT_ROOT]
    detect_stack.py --help

Reads config files under PROJECT_ROOT (default: cwd) and prints a JSON
summary of the detected languages, frameworks, styling, database, auth,
testing, tooling, libraries, monorepo structure, and confidence levels.

Confidence levels:
    high   — detected from an explicit dependency name
    medium — detected from a file marker only
    low    — inferred from weak signals

Exit codes:
    0 — success
    2 — usage error

Reads: package.json, tsconfig.json, pnpm-workspace.yaml, turbo.json,
nx.json, Cargo.toml, pyproject.toml, go.mod, default.project.json.
Stdlib only; portable across macOS and Linux.
"""

from __future__ import annotations

import json
import os
import sys
from pathlib import Path
from typing import Any


def read_text(path: Path) -> str | None:
    try:
        return path.read_text(encoding="utf-8")
    except (OSError, UnicodeDecodeError):
        return None


def read_json(path: Path) -> dict[str, Any] | None:
    text = read_text(path)
    if text is None:
        return None
    try:
        data = json.loads(text)
        return data if isinstance(data, dict) else None
    except json.JSONDecodeError:
        return None


def parse_toml(text: str) -> dict[str, Any]:
    """Parse TOML using stdlib tomllib (Python 3.11+) or a minimal fallback."""
    try:
        import tomllib  # type: ignore[import-not-found]

        return tomllib.loads(text)
    except ImportError:
        pass
    try:
        import tomli  # type: ignore[import-not-found]

        return tomli.loads(text)
    except ImportError:
        pass
    # Minimal fallback: extract [section] blocks and key = "value" pairs.
    result: dict[str, Any] = {}
    current: dict[str, Any] = result
    for raw in text.splitlines():
        line = raw.strip()
        if not line or line.startswith("#"):
            continue
        if line.startswith("[") and line.endswith("]"):
            parts = line[1:-1].split(".")
            node: dict[str, Any] = result
            for part in parts:
                part = part.strip()
                node = node.setdefault(part, {})
            current = node
            continue
        if "=" in line:
            key, _, value = line.partition("=")
            key = key.strip()
            value = value.strip().rstrip(",")
            if value.startswith('"') and value.endswith('"'):
                current[key] = value[1:-1]
            elif value.startswith("[") and value.endswith("]"):
                items = [
                    item.strip().strip('"').strip("'")
                    for item in value[1:-1].split(",")
                    if item.strip()
                ]
                current[key] = items
            elif value.startswith("{"):
                current[key] = {}
            else:
                current[key] = value.strip('"').strip("'")
    return result


def detect_node(
    root: Path, result: dict[str, Any], confidence: dict[str, str]
) -> None:
    pkg = read_json(root / "package.json")
    if not pkg:
        return
    deps: dict[str, str] = {}
    for key in ("dependencies", "devDependencies", "peerDependencies"):
        section = pkg.get(key)
        if isinstance(section, dict):
            deps.update({str(k): str(v) for k, v in section.items()})
    dev_deps = pkg.get("devDependencies") or {}

    has = lambda name: name in deps
    starts = lambda prefix: any(k.startswith(prefix) for k in deps)

    if "typescript" not in result["languages"]:
        if has("typescript") or (root / "tsconfig.json").exists():
            result["languages"].append("typescript")
            confidence["languages"] = "high" if has("typescript") else "medium"
    if "javascript" not in result["languages"]:
        result["languages"].append("javascript")
        confidence.setdefault("languages", "high")

    framework_map = [
        ("next", "nextjs"),
        ("@tanstack/react-start", "tanstack-start"),
        ("astro", "astro"),
        ("@remix-run/react", "remix"),
        ("hono", "hono"),
        ("@hono/node-server", "hono"),
        ("react-native", "react-native"),
        ("expo", "expo"),
        ("electron", "electron"),
    ]
    for dep, label in framework_map:
        if has(dep) and label not in result["frameworks"]:
            result["frameworks"].append(label)
            confidence["frameworks"] = "high"
    if starts("@tauri-apps/") and "tauri" not in result["frameworks"]:
        result["frameworks"].append("tauri")
        confidence["frameworks"] = "high"

    if has("tailwindcss") and "tailwind" not in result["styling"]:
        result["styling"].append("tailwind")
        confidence["styling"] = "high"
    if (
        (root / "components" / "ui").is_dir()
        or (root / "packages" / "ui").is_dir()
    ) and "shadcn" not in result["styling"]:
        result["styling"].append("shadcn")
        confidence["styling"] = "medium"

    db_map = [
        ("drizzle-orm", "drizzle"),
        ("@prisma/client", "prisma"),
        ("convex", "convex"),
    ]
    for dep, label in db_map:
        if has(dep) and label not in result["database"]:
            result["database"].append(label)
            confidence["database"] = "high"

    if has("better-auth") and "better-auth" not in result["auth"]:
        result["auth"].append("better-auth")
        confidence["auth"] = "high"
    if has("@clerk/nextjs") and "clerk" not in result["auth"]:
        result["auth"].append("clerk")
        confidence["auth"] = "high"
    if starts("@workos-inc/") and "workos" not in result["auth"]:
        result["auth"].append("workos")
        confidence["auth"] = "high"

    test_map = [
        ("vitest", "vitest"),
        ("jest", "jest"),
        ("@playwright/test", "playwright"),
    ]
    for dep, label in test_map:
        if has(dep) and label not in result["testing"]:
            result["testing"].append(label)
            confidence["testing"] = "high"

    if (
        ("biome" in dev_deps or "@biomejs/biome" in dev_deps)
        and "biome" not in result["tooling"]
    ):
        result["tooling"].append("biome")
        confidence["tooling"] = "high"
    if has("eslint") and "eslint" not in result["tooling"]:
        result["tooling"].append("eslint")
        confidence["tooling"] = "high"

    lib_map = [
        ("zod", "zod"),
        ("@tanstack/react-query", "tanstack-query"),
        ("effect", "effect"),
    ]
    for dep, label in lib_map:
        if has(dep) and label not in result["libraries"]:
            result["libraries"].append(label)
            confidence["libraries"] = "high"


def detect_monorepo(
    root: Path, result: dict[str, Any], confidence: dict[str, str]
) -> None:
    has_turbo = (root / "turbo.json").exists()
    has_nx = (root / "nx.json").exists()
    has_pnpm_ws = (root / "pnpm-workspace.yaml").exists()
    if has_turbo:
        result["structure"] = "monorepo"
        result["monorepo_tool"] = "turborepo"
        confidence["structure"] = "high"
    elif has_nx:
        result["structure"] = "monorepo"
        result["monorepo_tool"] = "nx"
        confidence["structure"] = "high"
    elif has_pnpm_ws:
        result["structure"] = "monorepo"
        result["monorepo_tool"] = "pnpm"
        confidence["structure"] = "high"
    elif (root / "package.json").exists() or (root / "Cargo.toml").exists() or (
        root / "pyproject.toml"
    ).exists() or (root / "go.mod").exists():
        result["structure"] = "single"
        confidence["structure"] = "medium"


def detect_rust(
    root: Path, result: dict[str, Any], confidence: dict[str, str]
) -> None:
    cargo_path = root / "Cargo.toml"
    text = read_text(cargo_path)
    if text is None:
        return
    if "rust" not in result["languages"]:
        result["languages"].append("rust")
        confidence["languages"] = "high"
    data = parse_toml(text)
    deps = data.get("dependencies") or {}
    if isinstance(deps, dict):
        dep_names = {str(k).lower() for k in deps.keys()}
    else:
        dep_names = set()
    framework_map = [
        ("tokio", "tokio"),
        ("axum", "axum"),
        ("leptos", "leptos"),
        ("tauri", "tauri"),
        ("gpui", "gpui"),
        ("async-std", "async-std"),
    ]
    for dep, label in framework_map:
        if dep in dep_names and label not in result["frameworks"]:
            result["frameworks"].append(label)
            confidence["frameworks"] = "high"
    pkg = data.get("package") or {}
    if isinstance(pkg, dict):
        edition = pkg.get("edition")
        if isinstance(edition, str):
            result.setdefault("rust_edition", edition)


def detect_python(
    root: Path, result: dict[str, Any], confidence: dict[str, str]
) -> None:
    py_path = root / "pyproject.toml"
    text = read_text(py_path)
    if text is None:
        return
    if "python" not in result["languages"]:
        result["languages"].append("python")
        confidence["languages"] = "high"
    data = parse_toml(text)
    raw_deps: list[str] = []
    project = data.get("project")
    if isinstance(project, dict):
        d = project.get("dependencies")
        if isinstance(d, list):
            raw_deps.extend(str(x) for x in d)
        optional = project.get("optional-dependencies")
        if isinstance(optional, dict):
            for group in optional.values():
                if isinstance(group, list):
                    raw_deps.extend(str(x) for x in group)
    tool = data.get("tool")
    if isinstance(tool, dict):
        poetry = tool.get("poetry")
        if isinstance(poetry, dict):
            p_deps = poetry.get("dependencies")
            if isinstance(p_deps, dict):
                raw_deps.extend(str(k) for k in p_deps.keys())
    normalized = {_norm_pypi(s) for s in raw_deps}

    framework_map = [
        ("fastapi", "fastapi"),
        ("django", "django"),
        ("flask", "flask"),
    ]
    for dep, label in framework_map:
        if dep in normalized and label not in result["frameworks"]:
            result["frameworks"].append(label)
            confidence["frameworks"] = "high"

    for lib in ("pydantic", "sqlalchemy"):
        if lib in normalized and lib not in result["libraries"]:
            result["libraries"].append(lib)
            confidence["libraries"] = "high"

    if "pytest" in normalized and "pytest" not in result["testing"]:
        result["testing"].append("pytest")
        confidence["testing"] = "high"

    for tool_name in ("ruff", "mypy", "ty"):
        if tool_name in normalized and tool_name not in result["tooling"]:
            result["tooling"].append(tool_name)
            confidence["tooling"] = "high"


def _norm_pypi(spec: str) -> str:
    name = spec.strip()
    for sep in ("[", "=", "<", ">", "!", "~", ";", " "):
        idx = name.find(sep)
        if idx >= 0:
            name = name[:idx]
    return name.strip().lower().replace("_", "-")


def detect_go(
    root: Path, result: dict[str, Any], confidence: dict[str, str]
) -> None:
    if (root / "go.mod").exists() and "go" not in result["languages"]:
        result["languages"].append("go")
        confidence["languages"] = "high"


def detect_roblox(
    root: Path, result: dict[str, Any], confidence: dict[str, str]
) -> None:
    rojo_path = root / "default.project.json"
    data = read_json(rojo_path)
    if not data:
        return
    text = json.dumps(data).lower()
    if "roblox" in text or "datamodel" in text or "starterplayer" in text:
        if "luau" not in result["languages"]:
            result["languages"].append("luau")
            confidence["languages"] = "high"
        if "roblox" not in result["frameworks"]:
            result["frameworks"].append("roblox")
            confidence["frameworks"] = "medium"
        if "rojo" not in result["tooling"]:
            result["tooling"].append("rojo")
            confidence["tooling"] = "high"


def detect_typescript_marker(
    root: Path, result: dict[str, Any], confidence: dict[str, str]
) -> None:
    if (root / "tsconfig.json").exists() and "typescript" not in result["languages"]:
        result["languages"].append("typescript")
        confidence["languages"] = "medium"


def main(argv: list[str]) -> int:
    if any(arg in ("-h", "--help") for arg in argv[1:]):
        print(__doc__)
        return 0
    args = [a for a in argv[1:] if not a.startswith("-")]
    if len(args) > 1:
        print(f"error: too many arguments: {args}", file=sys.stderr)
        return 2
    root = Path(args[0] if args else os.getcwd()).resolve()
    if not root.is_dir():
        print(f"error: not a directory: {root}", file=sys.stderr)
        return 2

    result: dict[str, Any] = {
        "root": root.as_posix(),
        "structure": "unknown",
        "monorepo_tool": None,
        "languages": [],
        "frameworks": [],
        "styling": [],
        "database": [],
        "auth": [],
        "testing": [],
        "tooling": [],
        "libraries": [],
        "confidence": {},
    }
    confidence: dict[str, str] = result["confidence"]

    detect_monorepo(root, result, confidence)
    detect_typescript_marker(root, result, confidence)
    detect_node(root, result, confidence)
    detect_rust(root, result, confidence)
    detect_python(root, result, confidence)
    detect_go(root, result, confidence)
    detect_roblox(root, result, confidence)

    print(json.dumps(result, indent=2, sort_keys=False))
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv))
