"""Audit F1: the agent's reported findings vs the task's ``known_issues.json`` (Rulings R6, R29).

known_issues.json entries: ``{id, file?, lines?: [a, b], locations?: [{file, lines}],
severity, decoy: bool, summary}``. ``file``/``lines`` is the primary site; ``locations``
adds other sites where a correct finding may cite the same issue. Findings come from the
injected ``extract_findings`` (see ``graders.__init__``) over the final message plus
report-like files the agent added or changed.

Matching, per finding (``unmatched`` = entries no earlier finding matched):

1. a finding with file + line(s) overlapping known sites in the same file: exactly one
   real entry -> that entry; exactly one decoy -> ``match_finding`` arbitrates between that
   decoy and the other unmatched entries (so a valid finding cited on a decoy's line isn't
   counted as flagging the decoy); several -> ``match_finding`` picks among them;
2. a finding with no line: ``match_finding`` over the unlocated entries (plus, with a
   file, that file's entries; with no file, all entries);
3. still nothing (including a located finding overlapping no site): ``match_finding``
   over every unmatched entry, decoys included;
4. still nothing: ``classify_finding`` labels it ``valid_unlisted`` (a real problem the
   task didn't plant) or ``incorrect``, judged against the code it cites at bench-base.

A match on a decoy counts in ``decoys_flagged``; a second finding on an already-found
issue is ignored. precision = tp / (tp + incorrect + decoys_flagged): valid findings that
weren't planted don't lower it, and are reported as ``valid_unlisted``. ``fp`` =
incorrect + decoys_flagged. Precision/recall/F1 are 0.0 when undefined;
``severity_accuracy`` (share of true positives whose severity matches,
case-insensitive) is None without true positives.
"""

from __future__ import annotations

import json
from pathlib import Path, PurePosixPath

from .. import untrusted
from ..types import Task
from ..workspace import BASE_TAG
from . import (ClassifyFinding, ExtractFindings, MatchFinding, final_text, not_applicable,
               workspace_of, write_grade)
from .scope import parse_diff

REPORT_SUFFIXES = (".md", ".markdown", ".txt", ".rst", ".json")
MAX_FILE_CHARS = 200_000
CODE_CONTEXT_LINES = 30  # lines of code shown around a finding's cited range
MAX_CODE_CHARS = 12_000
VERDICTS = ("valid_unlisted", "incorrect")


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


def sites(entry: dict) -> list[tuple[str, tuple[int, int]]]:
    """Every ``(file, (a, b))`` where ``entry`` may be cited: primary site first."""
    out = []
    for loc in [entry, *(entry.get("locations") or [])]:
        lines = loc.get("lines")
        if loc.get("file") and isinstance(lines, list) and len(lines) == 2:
            out.append((_norm(loc["file"], None), (min(lines), max(lines))))
    return out


def _located(entry: dict) -> bool:
    return bool(sites(entry))


def _in_file(entry: dict, file: str) -> bool:
    return any(_same_file(file, f) for f, _ in sites(entry))


def _overlaps(entry: dict, file: str, rng: tuple[int, int]) -> bool:
    return any(_same_file(file, f) and a <= rng[1] and rng[0] <= b
               for f, (a, b) in sites(entry))


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


def _ask(finding: dict, candidates: list[dict], match_finding: MatchFinding,
         tried: list[set[str]]) -> str | None:
    """``match_finding`` over ``candidates``, skipping a candidate set already asked."""
    ids = {c["id"] for c in candidates}
    if not ids or ids in tried:
        return None
    tried.append(ids)
    kid = match_finding(finding, candidates)
    return kid if kid in ids else None


def match(finding: dict, known: list[dict], workspace: Path | None,
          match_finding: MatchFinding, unmatched: set[str] | None = None) -> str | None:
    """The id of the known issue ``finding`` describes, or None (see module doc)."""
    unmatched = {e["id"] for e in known} if unmatched is None else unmatched
    open_entries = [e for e in known if e["id"] in unmatched]
    file = _norm(str(finding.get("file") or ""), workspace)
    rng = _finding_range(finding)
    tried: list[set[str]] = []
    kid = None
    if file and rng is not None:
        overlap = [e for e in known if _overlaps(e, file, rng)]
        if len(overlap) == 1 and not overlap[0].get("decoy"):
            return overlap[0]["id"]
        if len(overlap) == 1:  # only a decoy's line: is it really about the decoy?
            decoy = overlap[0]
            kid = _ask(finding, [decoy, *(e for e in open_entries if e is not decoy)],
                       match_finding, tried)
        elif overlap:
            kid = _ask(finding, overlap, match_finding, tried)
    elif rng is None:
        if not file:
            candidates = known
        else:
            candidates = [e for e in known if not _located(e) or _in_file(e, file)]
        kid = _ask(finding, candidates, match_finding, tried)
    if kid is None:
        kid = _ask(finding, open_entries, match_finding, tried)
    return kid


def code_context(workspace: Path | None, finding: dict) -> str:
    """The code a finding cites, as it was at bench-base (the agent may have edited the
    tree): the cited range +/- CODE_CONTEXT_LINES, numbered; "" when there's no file."""
    file = _norm(str(finding.get("file") or ""), workspace)
    if workspace is None or not file or file.startswith("/") or ".." in PurePosixPath(file).parts:
        return ""
    try:  # agent-controlled repo: hardened, sandboxed git (R22)
        proc = untrusted.git(workspace, "show", f"{BASE_TAG}:{file}", write=False,
                             check=False, text=True)
    except untrusted.UnsafePath:
        return ""
    if proc.returncode != 0:
        return ""
    lines = proc.stdout.splitlines()
    rng = _finding_range(finding)
    a, b = (1, len(lines)) if rng is None else (max(1, rng[0] - CODE_CONTEXT_LINES),
                                                  min(len(lines), rng[1] + CODE_CONTEXT_LINES))
    text = "\n".join(f"{n:>5}  {lines[n - 1]}" for n in range(a, b + 1))
    return f"{file}:\n{text}"[:MAX_CODE_CHARS]


def _ratio(n: int, d: int) -> float:
    return n / d if d else 0.0


def grade(task: Task, run_dir: Path, *, extract_findings: ExtractFindings,
          match_finding: MatchFinding, classify_finding: ClassifyFinding) -> dict:
    if task.category != "audit":
        return not_applicable(run_dir, "audit", f"category {task.category}")
    if task.known_issues is None or not task.known_issues.is_file():
        return not_applicable(run_dir, "audit", "no known_issues.json")
    known = json.loads(task.known_issues.read_text())
    by_id = {e["id"]: e for e in known}
    workspace = workspace_of(run_dir)
    findings = extract_findings(final_text(run_dir), report_files(run_dir, workspace))

    found: dict[str, dict] = {}  # known id -> first finding matching it
    unmatched = set(by_id)
    valid_unlisted: list[str] = []
    incorrect: list[str] = []
    for f in findings:
        kid = match(f, known, workspace, match_finding, unmatched)
        if kid in by_id:
            if kid not in found:
                found[kid] = f
                unmatched.discard(kid)
            continue
        verdict = classify_finding(f, code_context(workspace, f))
        if verdict not in VERDICTS:
            raise ValueError(f"classify_finding returned {verdict!r}")
        (valid_unlisted if verdict == "valid_unlisted" else incorrect).append(
            str(f.get("summary") or ""))

    hits = [k for k in found if not by_id[k].get("decoy")]
    decoys = [k for k in found if by_id[k].get("decoy")]
    real = [e for e in known if not e.get("decoy")]
    tp, fn = len(hits), len(real) - len(hits)
    wrong = len(incorrect) + len(decoys)
    precision, recall = _ratio(tp, tp + wrong), _ratio(tp, tp + fn)
    f1 = _ratio(2 * precision * recall, precision + recall)
    sev_ok = sum(str(found[k].get("severity") or "").lower() == str(by_id[k].get("severity")).lower()
                 for k in hits)
    return write_grade(run_dir, "audit", {
        "applicable": True, "findings": len(findings),
        "tp": tp, "fp": wrong, "fn": fn, "decoys_flagged": len(decoys),
        "incorrect": len(incorrect), "valid_unlisted": len(valid_unlisted),
        "precision": precision, "recall": recall, "f1": f1,
        "severity_accuracy": sev_ok / tp if tp else None,
        "matched": sorted(hits), "missed": sorted(e["id"] for e in real if e["id"] not in found),
        "decoys": sorted(decoys), "valid_unlisted_findings": valid_unlisted,
        "incorrect_findings": incorrect,
    })
