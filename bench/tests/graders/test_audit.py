import json

import pytest

from bruhsbench.graders import audit

from conftest import make_task

KNOWN = [
    {"id": "sqli", "file": "src/db.ts", "lines": [10, 14], "severity": "critical",
     "decoy": False, "summary": "SQL built by string concatenation"},
    {"id": "leak", "file": "src/server.ts", "lines": [30, 32], "severity": "high",
     "decoy": False, "summary": "listener never removed"},
    {"id": "n+1", "file": "src/api.ts", "lines": [5, 9], "severity": "medium",
     "decoy": False, "summary": "query inside loop"},
    {"id": "decoy-eval", "file": "src/sandbox.ts", "lines": [3, 3], "severity": "low",
     "decoy": True, "summary": "eval on a constant string (safe)"},
]


def audit_task(tmp_path, known=KNOWN):
    p = tmp_path / "known_issues.json"
    p.write_text(json.dumps(known))
    return make_task(tmp_path, category="audit", known_issues=p)


def no_judge_match(finding, candidates):
    raise AssertionError(f"judge should not be needed: {finding} {candidates}")


def test_audit_f1_with_decoy(tmp_path, make_run):
    task = audit_task(tmp_path)
    run = make_run({"src/db.ts": "x\n"})
    run.write({"AUDIT.md": "# Findings\n"})
    run_dir = run.finish(final="see AUDIT.md")
    seen = {}

    def extract(final_text, files):
        seen.update(final_text=final_text, files=files)
        return [
            {"file": "src/db.ts", "line": 12, "summary": "sqli", "severity": "critical"},
            {"file": "./src/server.ts", "line": 31, "summary": "leak", "severity": "low"},
            {"file": "src/sandbox.ts", "line": 3, "summary": "eval!", "severity": "high"},
        ]

    g = audit.grade(task, run_dir, extract_findings=extract, match_finding=no_judge_match)

    assert seen == {"final_text": "see AUDIT.md", "files": {"AUDIT.md": "# Findings\n"}}
    assert (g["tp"], g["fp"], g["fn"], g["decoys_flagged"]) == (2, 1, 1, 1)
    assert g["precision"] == pytest.approx(2 / 3)
    assert g["recall"] == pytest.approx(2 / 3)
    assert g["f1"] == pytest.approx(2 / 3)
    assert g["severity_accuracy"] == pytest.approx(0.5)
    assert (run_dir / "grades" / "audit.json").is_file()


def test_audit_ambiguous_and_unlocated_go_to_judge(tmp_path, make_run):
    known = [
        {"id": "a", "file": "x.py", "lines": [1, 20], "severity": "high", "decoy": False,
         "summary": "a"},
        {"id": "b", "file": "x.py", "lines": [10, 12], "severity": "low", "decoy": False,
         "summary": "b"},
        {"id": "c", "severity": "medium", "decoy": False, "summary": "no tests for auth"},
    ]
    task = audit_task(tmp_path, known)
    run_dir = make_run({"x.py": "x\n"}).finish()
    calls = []

    def match(finding, candidates):
        calls.append((finding["summary"], sorted(c["id"] for c in candidates)))
        return {"overlap": "b", "unlocated": "c", "dup": "b"}.get(finding["summary"])

    def extract(final_text, files):
        return [
            {"file": "x.py", "line": 11, "summary": "overlap", "severity": "low"},
            {"file": None, "line": None, "summary": "unlocated", "severity": "medium"},
            {"file": "x.py", "line": 11, "summary": "dup", "severity": "low"},
            {"file": "y.py", "line": 1, "summary": "noise", "severity": "low"},
        ]

    g = audit.grade(task, run_dir, extract_findings=extract, match_finding=match)
    assert calls == [("overlap", ["a", "b"]), ("unlocated", ["a", "b", "c"]),
                     ("dup", ["a", "b"]), ("noise", ["c"])]
    # a duplicate of an already-found issue is neither a hit nor a false positive
    assert (g["tp"], g["fp"], g["fn"]) == (2, 1, 1)
    assert g["severity_accuracy"] == 1.0


def test_audit_not_applicable_outside_audit_category(tmp_path, make_run):
    task = make_task(tmp_path, category="feature")
    g = audit.grade(task, make_run({"a": "a"}).finish(),
                    extract_findings=lambda *a: [], match_finding=no_judge_match)
    assert g["applicable"] is False
