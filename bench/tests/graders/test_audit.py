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


def no_classify(finding, code):
    raise AssertionError(f"classify should not be needed: {finding}")


def by_summary(table):
    """match_finding stub: the id ``table`` gives the finding's summary (if a candidate),
    recording each call's candidate ids."""
    calls = []

    def match(finding, candidates):
        calls.append((finding["summary"], sorted(c["id"] for c in candidates)))
        kid = table.get(finding["summary"])
        return kid if kid in {c["id"] for c in candidates} else None
    return match, calls


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

    match, calls = by_summary({"eval!": "decoy-eval"})
    g = audit.grade(task, run_dir, extract_findings=extract, match_finding=match,
                    classify_finding=no_classify)

    assert seen == {"final_text": "see AUDIT.md", "files": {"AUDIT.md": "# Findings\n"}}
    # a decoy-only overlap is arbitrated against the decoy and the other unmatched issues
    assert calls == [("eval!", ["decoy-eval", "n+1"])]
    assert (g["tp"], g["fp"], g["fn"], g["decoys_flagged"]) == (2, 1, 1, 1)
    assert g["precision"] == pytest.approx(2 / 3)
    assert g["recall"] == pytest.approx(2 / 3)
    assert g["f1"] == pytest.approx(2 / 3)
    assert g["severity_accuracy"] == pytest.approx(0.5)
    assert g["decoys"] == ["decoy-eval"]
    assert (run_dir / "grades" / "audit.json").is_file()


def test_finding_on_a_decoy_line_about_another_issue_is_not_a_decoy_hit(tmp_path, make_run):
    task = audit_task(tmp_path)
    run_dir = make_run({"a": "a"}).finish()
    match, _ = by_summary({"query in a loop (seen from sandbox.ts)": "n+1"})
    g = audit.grade(task, run_dir, match_finding=match, classify_finding=no_classify,
                    extract_findings=lambda *a: [{"file": "src/sandbox.ts", "line": 3,
                        "summary": "query in a loop (seen from sandbox.ts)", "severity": "medium"}])
    assert g["matched"] == ["n+1"] and g["decoys_flagged"] == 0 and g["precision"] == 1.0


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
    match, calls = by_summary({"overlap": "b", "unlocated": "c", "dup": "b"})

    def extract(final_text, files):
        return [
            {"file": "x.py", "line": 11, "summary": "overlap", "severity": "low"},
            {"file": None, "line": None, "summary": "unlocated", "severity": "medium"},
            {"file": "x.py", "line": 11, "summary": "dup", "severity": "low"},
            {"file": "y.py", "line": 1, "summary": "noise", "severity": "low"},
        ]

    classified = []

    def classify(finding, code):
        classified.append(finding["summary"])
        return "incorrect"

    g = audit.grade(task, run_dir, extract_findings=extract, match_finding=match,
                    classify_finding=classify)
    assert calls == [("overlap", ["a", "b"]), ("unlocated", ["a", "b", "c"]),
                     ("dup", ["a", "b"]),
                     ("noise", ["a"])]  # overlaps nothing: every still-unmatched issue
    # a duplicate of an already-found issue is neither a hit nor a false positive
    assert (g["tp"], g["fp"], g["fn"]) == (2, 1, 1)
    assert classified == ["noise"] and g["incorrect"] == 1
    assert g["severity_accuracy"] == 1.0


def test_valid_unlisted_findings_do_not_lower_precision(tmp_path, make_run):
    task = audit_task(tmp_path)
    run = make_run({"src/db.ts": "".join(f"line {n}\n" for n in range(1, 61)),
                    "src/other.ts": "ok\n"})
    run.write({"src/db.ts": "agent edited\n"})  # classify sees bench-base, not this
    run_dir = run.finish()
    seen = []

    def classify(finding, code):
        seen.append((finding["summary"], code))
        return "valid_unlisted" if finding["summary"] == "real but unplanted" else "incorrect"

    findings = [
        {"file": "src/db.ts", "line": 12, "summary": "sqli", "severity": "critical"},
        {"file": "src/db.ts", "line": 50, "summary": "real but unplanted", "severity": "low"},
        {"file": None, "line": None, "summary": "nonsense", "severity": "low"},
    ]
    match, _ = by_summary({})
    g = audit.grade(task, run_dir, extract_findings=lambda *a: findings, match_finding=match,
                    classify_finding=classify)
    assert (g["tp"], g["valid_unlisted"], g["incorrect"], g["fp"]) == (1, 1, 1, 1)
    assert g["precision"] == pytest.approx(1 / 2)  # tp / (tp + incorrect + decoys)
    assert g["valid_unlisted_findings"] == ["real but unplanted"]
    code = dict(seen)["real but unplanted"]
    assert code.startswith("src/db.ts:") and "   50  line 50" in code
    assert "   20  line 20" in code and "   19  line 19" not in code  # +/- 30 lines
    assert "agent edited" not in code
    assert dict(seen)["nonsense"].startswith("Files in the repository:\nsrc/db.ts\nsrc/other.ts")


def test_file_less_findings_get_project_context(tmp_path, make_run):
    task = audit_task(tmp_path)
    run = make_run({"README.md": "# shop api\nAuth middleware in src/auth.ts\n",
                    "package.json": '{"name": "shop", "scripts": {"test": "vitest"}}\n',
                    "src/auth.ts": "export function requireUser() {}\n",
                    "test/orders.test.ts": "it('orders', () => {})\n"})
    run.write({"README.md": "agent rewrote this\n"})
    run_dir = run.finish()
    seen = {}

    def classify(finding, code):
        seen[finding["summary"]] = code
        return "valid_unlisted"

    findings = [
        {"file": None, "line": None, "summary": "no tests cover the auth middleware",
         "severity": "medium"},
        {"file": "src/missing.ts", "line": 3, "summary": "cites a file that isn't there",
         "severity": "low"},
    ]
    match, _ = by_summary({})
    g = audit.grade(task, run_dir, extract_findings=lambda *a: findings, match_finding=match,
                    classify_finding=classify)
    assert g["valid_unlisted"] == 2 and g["incorrect"] == 0
    for code in seen.values():
        assert "Files in the repository:" in code
        assert "src/auth.ts" in code and "test/orders.test.ts" in code
        assert "README.md:\n# shop api" in code and "agent rewrote" not in code
        assert 'package.json:\n{"name": "shop"' in code


def test_alternate_locations_match(tmp_path, make_run):
    known = [{"id": "neg-qty", "file": "src/validate.ts", "lines": [26, 37],
              "locations": [{"file": "src/orders.ts", "lines": [73, 80]}],
              "severity": "high", "decoy": False, "summary": "quantities unvalidated"},
             {"id": "other", "file": "src/orders.ts", "lines": [10, 12], "severity": "low",
              "decoy": False, "summary": "o"}]
    task = audit_task(tmp_path, known)
    run_dir = make_run({"a": "a"}).finish()
    g = audit.grade(task, run_dir, match_finding=no_judge_match, classify_finding=no_classify,
                    extract_findings=lambda *a: [{"file": "src/orders.ts", "lines": [75, 77],
                                                  "summary": "negative qty", "severity": "high"}])
    assert g["matched"] == ["neg-qty"]


def test_located_finding_off_every_site_falls_back_to_judge(tmp_path, make_run):
    task = audit_task(tmp_path)
    run_dir = make_run({"a": "a"}).finish()
    match, calls = by_summary({"sql injection, cited at the caller": "sqli"})
    g = audit.grade(task, run_dir, match_finding=match, classify_finding=no_classify,
                    extract_findings=lambda *a: [{"file": "src/routes.ts", "line": 40,
                        "summary": "sql injection, cited at the caller", "severity": "critical"}])
    assert calls == [("sql injection, cited at the caller", ["decoy-eval", "leak", "n+1", "sqli"])]
    assert g["matched"] == ["sqli"] and g["fp"] == 0


def test_decoys_only_scores_zero(tmp_path, make_run):
    task = audit_task(tmp_path)
    run_dir = make_run({"a": "a"}).finish()
    match, _ = by_summary({"eval": "decoy-eval"})
    g = audit.grade(task, run_dir, match_finding=match, classify_finding=no_classify,
                    extract_findings=lambda *a: [{"file": "src/sandbox.ts", "line": 3,
                                                  "summary": "eval", "severity": "high"}])
    assert (g["tp"], g["decoys_flagged"], g["f1"], g["precision"]) == (0, 1, 0.0, 0.0)


def test_bad_classify_verdict_raises(tmp_path, make_run):
    task = audit_task(tmp_path)
    run_dir = make_run({"a": "a"}).finish()
    match, _ = by_summary({})
    with pytest.raises(ValueError, match="classify_finding"):
        audit.grade(task, run_dir, match_finding=match, classify_finding=lambda f, c: "maybe",
                    extract_findings=lambda *a: [{"file": None, "line": None, "summary": "x",
                                                  "severity": None}])


def test_audit_not_applicable_outside_audit_category(tmp_path, make_run):
    task = make_task(tmp_path, category="feature")
    g = audit.grade(task, make_run({"a": "a"}).finish(), extract_findings=lambda *a: [],
                    match_finding=no_judge_match, classify_finding=no_classify)
    assert g["applicable"] is False
