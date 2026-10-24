"""Audit F1: the agent's reported findings vs the task's ``known_issues.json`` (Ruling R6).

known_issues.json entries: ``{id, file?, lines?: [a, b], severity, decoy: bool, summary}``.
Findings come from the injected ``extract_findings`` (see ``graders.__init__``) over the
final message plus report-like files the agent added or changed.

Matching, per finding:

* entries with file + lines whose range overlaps the finding's line(s) in the same file:
  one -> that entry; several -> ``match_finding`` picks among them;
* otherwise ``match_finding`` decides among the entries without file/lines (plus, when
  the finding names no line, the entries in its file; when it names no file, all entries).

A match on a decoy counts as a false positive (and ``decoys_flagged``); a finding matching
nothing is a false positive; a second finding on an already-found issue is ignored.
Precision/recall/F1 are 0.0 when undefined; ``severity_accuracy`` (share of true positives
whose severity matches, case-insensitive) is None without true positives.
"""

from __future__ import annotations

import json
from pathlib import Path, PurePosixPath

from .. import untrusted
from ..types import Task
from . import ExtractFindings, MatchFinding, final_text, not_applicable, workspace_of, write_grade
from .scope import parse_diff

REPORT_SUFFIXES = (".md", ".markdown", ".txt", ".rst", ".json")
MAX_FILE_CHARS = 200_000


def _norm(path: str, workspace: Path | None) -> str:
    p = path.strip().replace("\\", "/")
    if workspace is not None and p.startswith("/"):
        for root in {str(workspace), str(workspace.resolve())}:
            if p.startswith(root.rstrip("/") + "/"):
                p = p[len(root.rstrip("/")) + 1:]
    while p.startswith("./"):
        p = p[2:]
    return p


def _same_file(a: str, b: str) -> bool:
    if a == b:
        return True
    # tolerate a path given relative to a subdirectory, or just the file name
    pa, pb = PurePosixPath(a).parts, PurePosixPath(b).parts
    short, long = (pa, pb) if len(pa) <= len(pb) else (pb, pa)
    return bool(short) and long[-len(short):] == short


def _finding_range(f: dict) -> tuple[int, int] | None:
    lines = f.get("lines")
    if isinstance(lines, (list, tuple)) and len(lines) == 2 and all(isinstance(x, int) for x in lines):
        return min(lines), max(lines)
    line = f.get("line")
    return (line, line) if isinstance(line, int) and not isinstance(line, bool) else None


def _located(entry: dict) -> bool:
    lines = entry.get("lines")
    return bool(entry.get("file")) and isinstance(lines, list) and len(lines) == 2


def report_files(run_dir: Path, workspace: Path | None) -> dict[str, str]:
    """Report-like files (by suffix) the agent added or modified, read from its workspace."""
    if workspace is None:
        return {}
    diff_path = Path(run_dir) / "diff.patch"
    diff = diff_path.read_text(errors="replace") if diff_path.is_file() else ""
    files: dict[str, str] = {}
    for change in parse_diff(diff):
        if not change.paths:
            continue
        rel = change.paths[-1]
        if not rel.lower().endswith(REPORT_SUFFIXES):
            continue
        try:  # agent-controlled tree: no symlinks, regular files only (R22)
            files[rel] = untrusted.read_text(untrusted.check_outside_home(workspace),
                                             rel)[:MAX_FILE_CHARS]
        except untrusted.UnsafePath:
            continue
    return files


def match(finding: dict, known: list[dict], workspace: Path | None,
          match_finding: MatchFinding) -> str | None:
    file = _norm(str(finding.get("file") or ""), workspace)
    rng = _finding_range(finding)
    located = [e for e in known if _located(e)]
    in_file = [e for e in located if file and _same_file(file, _norm(e["file"], None))]
    if rng is not None:
        overlap = [e for e in in_file if e["lines"][0] <= rng[1] and rng[0] <= e["lines"][1]]
        if len(overlap) == 1:
            return overlap[0]["id"]
        if overlap:
            return match_finding(finding, overlap)
    if not file:
        candidates = known
    else:
        candidates = [e for e in known if not _located(e)] + (in_file if rng is None else [])
    return match_finding(finding, candidates) if candidates else None


def _ratio(n: int, d: int) -> float:
    return n / d if d else 0.0


def grade(task: Task, run_dir: Path, *, extract_findings: ExtractFindings,
          match_finding: MatchFinding) -> dict:
    if task.category != "audit":
        return not_applicable(run_dir, "audit", f"category {task.category}")
    if task.known_issues is None or not task.known_issues.is_file():
        return not_applicable(run_dir, "audit", "no known_issues.json")
    known = json.loads(task.known_issues.read_text())
    by_id = {e["id"]: e for e in known}
    workspace = workspace_of(run_dir)
    findings = extract_findings(final_text(run_dir), report_files(run_dir, workspace))

    found: dict[str, dict] = {}  # known id -> first finding matching it
    unmatched = 0
    for f in findings:
        kid = match(f, known, workspace, match_finding)
        if kid not in by_id:
            unmatched += 1
        elif kid not in found:
            found[kid] = f

    hits = [k for k in found if not by_id[k].get("decoy")]
    decoys = [k for k in found if by_id[k].get("decoy")]
    real = [e for e in known if not e.get("decoy")]
    tp, fp, fn = len(hits), unmatched + len(decoys), len(real) - len(hits)
    precision, recall = _ratio(tp, tp + fp), _ratio(tp, tp + fn)
    f1 = _ratio(2 * precision * recall, precision + recall)
    sev_ok = sum(str(found[k].get("severity") or "").lower() == str(by_id[k].get("severity")).lower()
                 for k in hits)
    return write_grade(run_dir, "audit", {
        "applicable": True, "findings": len(findings),
        "tp": tp, "fp": fp, "fn": fn, "decoys_flagged": len(decoys),
        "precision": precision, "recall": recall, "f1": f1,
        "severity_accuracy": sev_ok / tp if tp else None,
        "matched": sorted(hits), "missed": sorted(e["id"] for e in real if e["id"] not in found),
    })
