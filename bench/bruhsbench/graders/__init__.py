"""Objective graders: score one finished run from its results dir.

Every grader is ``grade(task, run_dir, ...) -> dict`` and writes its dict to
``run_dir/grades/<grader>.json`` (``run_dir`` = ``out_root/<run_id>``). A grader that
doesn't apply to the task records ``{"applicable": False, "reason": ...}``.

Graders that need a model (audit, honesty) take the judge as injected callables; Task 8's
``bruhsbench.judge`` module implements them. Their contracts:

``extract_findings(final_text: str, files: dict[str, str]) -> list[dict]``
    ``final_text`` is the agent's final message; ``files`` maps workspace-relative path ->
    text of the report-like files the agent added or changed (``AUDIT.md`` etc.; see
    ``audit.REPORT_SUFFIXES``). Returns one dict per distinct issue the agent reported:
    ``{"file": str | None, "line": int | None, "summary": str, "severity": str | None}``;
    an optional ``"lines": [a, b]`` may replace ``line`` for a range. Severity uses the
    known_issues vocabulary (e.g. "critical" | "high" | "medium" | "low").

``extract_claims(final_text: str) -> list[dict]``
    The agent's completion claims: ``{"claim": str, "kind": "done" | "verified" |
    "fixed" | "tests_pass"}`` (other kinds are counted as unverifiable).

``match_finding(finding: dict, candidates: list[dict]) -> str | None``
    Decide which of ``candidates`` (known_issues.json entries, each with ``id`` and
    ``summary``) the agent's ``finding`` describes, returning that entry's ``id``, or None
    if it describes none of them. Called when line overlap is ambiguous (several entries
    overlap) and for entries that have no file/lines.

A module defining these three functions satisfies :class:`Judge` structurally.
"""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any, Protocol

from ..types import Task


class ExtractFindings(Protocol):
    def __call__(self, final_text: str, files: dict[str, str]) -> list[dict]: ...


class ExtractClaims(Protocol):
    def __call__(self, final_text: str) -> list[dict]: ...


class MatchFinding(Protocol):
    def __call__(self, finding: dict, candidates: list[dict]) -> str | None: ...


class Judge(Protocol):
    extract_findings: ExtractFindings
    extract_claims: ExtractClaims
    match_finding: MatchFinding


def write_grade(run_dir: Path, name: str, grade: dict) -> dict:
    out = Path(run_dir) / "grades"
    out.mkdir(parents=True, exist_ok=True)
    (out / f"{name}.json").write_text(json.dumps(grade, indent=2) + "\n")
    return grade


def read_grade(run_dir: Path, name: str) -> dict | None:
    p = Path(run_dir) / "grades" / f"{name}.json"
    return json.loads(p.read_text()) if p.is_file() else None


def not_applicable(run_dir: Path, name: str, reason: str) -> dict:
    return write_grade(run_dir, name, {"applicable": False, "reason": reason})


def run_meta(run_dir: Path) -> dict[str, Any]:
    """The run's result.json (empty if missing)."""
    p = Path(run_dir) / "result.json"
    return json.loads(p.read_text()) if p.is_file() else {}


def workspace_of(run_dir: Path) -> Path | None:
    ws = run_meta(run_dir).get("workspace")
    return Path(ws) if ws and Path(ws).is_dir() else None


def final_text(run_dir: Path) -> str:
    p = Path(run_dir) / "final.txt"
    if p.is_file():
        return p.read_text(errors="replace")
    return run_meta(run_dir).get("final_message") or ""


def grade_all(task: Task, run_dir: Path, judge: Judge | None = None) -> dict[str, dict]:
    """Run every objective grader (commands first: honesty reads its evidence).

    Without a ``judge`` the model-backed graders (audit, honesty) are recorded as not
    applicable.
    """
    from . import audit, commands, honesty, scope

    grades = {"commands": commands.grade(task, run_dir), "scope": scope.grade(task, run_dir)}
    if judge is None:
        grades["audit"] = not_applicable(run_dir, "audit", "no judge")
        grades["honesty"] = not_applicable(run_dir, "honesty", "no judge")
    else:
        grades["audit"] = audit.grade(task, run_dir, extract_findings=judge.extract_findings,
                                      match_finding=judge.match_finding)
        grades["honesty"] = honesty.grade(task, run_dir, extract_claims=judge.extract_claims)
    return grades
