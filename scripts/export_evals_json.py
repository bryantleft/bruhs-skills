#!/usr/bin/env python3
"""export_evals_json.py — Validate the eval case folders and export them as evals.json.

Usage:
    export_evals_json.py [--evals-dir DIR] [--check] [-o PATH]
    export_evals_json.py --help

The source of truth is evals/<case>/ (prompt.md + case.yaml + graders/*.md),
the layout `claude plugin eval` reads. Runners for other agents (Codex, Cursor,
Gemini CLI, and the agentskills.io tooling generally) read a single
evals/evals.json instead. This script turns the first into the second so that
one suite serves every provider, and it checks each case against the rules that
would otherwise make `claude plugin eval` refuse to load it.

    --check     validate only; print a summary, write nothing
    -o PATH     write evals.json to PATH (default: stdout)

The export is generated, not committed. Don't write it to evals/evals.json
inside this repo: skill-creator would then run every case twice, once from the
folder and once from the file.

Exit codes:
    0 — every case is valid (and the export, if any, was written)
    1 — one or more cases are invalid (errors on stderr)
    2 — usage error

Stdlib only; reads only the YAML subset the case files use.
"""

from __future__ import annotations

import argparse
import json
import re
import sys
from pathlib import Path

PLUGIN_DIR = Path(__file__).resolve().parent.parent
SKILL_NAME = "bruhs"

CASE_NAME_RE = re.compile(r"^[a-z][a-z0-9-]*$")
RESERVED_NAMES = {"results", "mocks", "node_modules", "files", "true", "false", "null"}
PROMPT_KEYS = {
    "schema_version", "name", "description", "tags", "plugins", "runs",
    "expected_outcome", "model", "max_turns", "timeout_seconds", "allowed_tools",
    "append_system_prompt", "env",
}
GRADER_TYPES = {"regex", "tool_used", "tool_order", "file_exists", "llm", "baseline"}


def split_frontmatter(text: str) -> tuple[dict[str, str], str]:
    """Split a `---`-fenced frontmatter block (flat key: value lines) from the body."""
    if not text.startswith("---\n"):
        return {}, text
    end = text.find("\n---", 4)
    if end == -1:
        raise ValueError("frontmatter is not closed with ---")
    meta: dict[str, str] = {}
    for line in text[4:end].splitlines():
        if not line.strip() or line.startswith((" ", "\t")):
            continue
        key, sep, value = line.partition(":")
        if not sep:
            raise ValueError(f"frontmatter line is not key: value: {line!r}")
        meta[key.strip()] = value.strip()
    return meta, text[end + 4:].lstrip("\n")


def parse_case_yaml(text: str) -> dict[str, str]:
    """Parse top-level `key: value` and `key: |` block scalars; nested maps keep their raw text."""
    out: dict[str, str] = {}
    lines = text.splitlines()
    i = 0
    while i < len(lines):
        line = lines[i]
        i += 1
        if not line.strip() or line.lstrip().startswith("#") or line.startswith((" ", "\t")):
            continue
        key, _, value = line.partition(":")
        value = value.strip()
        if value in ("|", "|-", ">", ">-", ""):
            body = []
            while i < len(lines) and (not lines[i].strip() or lines[i].startswith((" ", "\t"))):
                body.append(lines[i][2:] if lines[i].startswith("  ") else lines[i].strip())
                i += 1
            out[key.strip()] = "\n".join(body).strip()
        else:
            out[key.strip()] = value
    return out


def load_case(case_dir: Path) -> tuple[dict, list[str]]:
    errors: list[str] = []
    name = case_dir.name
    if not CASE_NAME_RE.match(name) or name in RESERVED_NAMES:
        errors.append(f"case name {name!r} must be lowercase-hyphenated, start with a letter, and not be reserved")

    prompt_path = case_dir / "prompt.md"
    prompt_meta: dict[str, str] = {}
    prompt = ""
    if prompt_path.is_file():
        try:
            prompt_meta, prompt = split_frontmatter(prompt_path.read_text())
        except ValueError as exc:
            errors.append(f"prompt.md: {exc}")
        unknown = set(prompt_meta) - PROMPT_KEYS
        if unknown:
            errors.append(f"prompt.md: unknown frontmatter keys {sorted(unknown)} (the CLI refuses the case)")
    case_yaml: dict[str, str] = {}
    yaml_path = case_dir / "case.yaml"
    if yaml_path.is_file():
        case_yaml = parse_case_yaml(yaml_path.read_text())
        if case_yaml.get("schema_version") not in ('"1.1"', "'1.1'"):
            errors.append('case.yaml: schema_version must be the quoted string "1.1"')
        if case_yaml.get("name") != name:
            errors.append(f"case.yaml: name {case_yaml.get('name')!r} must match the folder name {name!r}")
    if not prompt.strip():
        errors.append("prompt.md is missing or has an empty prompt body")

    assertions: list[str] = []
    grader_files = sorted((case_dir / "graders").glob("*.md"))
    if not grader_files:
        errors.append("no graders/*.md (the CLI refuses a case without a grader)")
    for grader in grader_files:
        try:
            meta, body = split_frontmatter(grader.read_text())
        except ValueError as exc:
            errors.append(f"graders/{grader.name}: {exc}")
            continue
        gtype = meta.get("type")
        if gtype not in GRADER_TYPES:
            errors.append(f"graders/{grader.name}: type {gtype!r} is not one of {sorted(GRADER_TYPES)}")
            continue
        if gtype in ("llm", "baseline"):
            if not body.strip():
                errors.append(f"graders/{grader.name}: {gtype} grader has no rubric body")
            assertions.append(body.strip())
        else:
            options = ", ".join(f"{k}={v}" for k, v in meta.items() if k not in ("type", "weight", "arm"))
            assertions.append(f"[{gtype} check: {options}] {body.strip()}".strip())

    entry = {
        "eval_name": name,
        "prompt": prompt.strip(),
        "expected_output": case_yaml.get("expected_outcome", ""),
        "context": case_yaml.get("description", ""),
        "files": [],
        "assertions": assertions,
    }
    return entry, errors


def main(argv: list[str]) -> int:
    parser = argparse.ArgumentParser(description=__doc__.split("\n\n")[0])
    parser.add_argument("--evals-dir", type=Path, default=PLUGIN_DIR / "evals")
    parser.add_argument("--check", action="store_true", help="validate only")
    parser.add_argument("-o", "--output", type=Path, help="write evals.json here (default: stdout)")
    args = parser.parse_args(argv)

    if not args.evals_dir.is_dir():
        print(f"error: {args.evals_dir} is not a directory", file=sys.stderr)
        return 2

    case_dirs = sorted(
        p for p in args.evals_dir.iterdir()
        if p.is_dir() and ((p / "prompt.md").is_file() or (p / "case.yaml").is_file())
    )
    if not case_dirs:
        print(f"error: no eval cases under {args.evals_dir}", file=sys.stderr)
        return 1

    entries, failed = [], 0
    for case_dir in case_dirs:
        entry, errors = load_case(case_dir)
        if errors:
            failed += 1
            for err in errors:
                print(f"{case_dir.name}: {err}", file=sys.stderr)
        entry["id"] = len(entries) + 1
        entries.append(entry)

    if failed:
        print(f"{failed} of {len(case_dirs)} cases are invalid", file=sys.stderr)
        return 1
    if args.check:
        graders = sum(len(e["assertions"]) for e in entries)
        print(f"{len(entries)} cases valid, {graders} graders")
        return 0

    doc = {"skill_name": SKILL_NAME, "evals": [{"id": e.pop("id"), **e} for e in entries]}
    text = json.dumps(doc, indent=2, ensure_ascii=False) + "\n"
    if args.output:
        args.output.write_text(text)
        print(f"wrote {len(entries)} cases to {args.output}", file=sys.stderr)
    else:
        sys.stdout.write(text)
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
