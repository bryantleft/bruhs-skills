"""``bruhsbench digest``: the review file for the real tasks' checklists."""

from __future__ import annotations

import json

from results_fixture import make_task

from bruhsbench import digest as D
from bruhsbench.tasks import load_task

PROMPT = "fix the ```grade``` page\n\nkeep it `short`\n"


def real_task(tmp_path):
    t = make_task(tmp_path, "real-ui", "ui", private=True, repo="/x/mints", prompt=PROMPT)
    (t.dir / "checklist.json").write_text(json.dumps({"items": [
        {"id": "starts-with-photos", "check": "script", "text": "Opens on the photos."},
        {"id": "plain-copy", "check": "judge", "text": "Copy is plain."},
        {"id": "orphan", "check": "judge", "text": "No source anywhere."},
    ]}))
    (t.dir / "checklist_src.py").write_text(
        'PROBE = "x"\nITEMS = [\n'
        ' {"id": "starts-with-photos", "check": "script", "text": "t", "probe": PROBE,\n'
        '  "source": "thread c5d1: remove the intro", "flag_for_user": "from a later audit"},\n'
        ' {"id": "removed-item", "check": "judge", "text": "t", "source": "s"},\n]\n')
    (t.dir / "NOTES.md").write_text("| id | check | source |\n|---|---|---|\n"
                                    "| plain-copy | judge | follow-up 21:04Z 'cut jargon' |\n")
    return load_task(t.dir)


def audit_task(tmp_path):
    t = make_task(tmp_path, "real-audit", "audit", private=True, repo="/x/r")
    (t.dir / "known_issues.json").write_text(json.dumps([
        {"id": "ki-xss", "file": "a.rs", "lines": [3, 9], "severity": "critical",
         "decoy": False, "summary": "XSS via inner_html."}]))
    (t.dir / "known_issues_src.py").write_text(
        "import json\nI = [dict(id='ki-xss', audit_ref='C1', fix='2d8c04d')]\n"
        "if __name__ == '__main__':\n    print(json.dumps(I))\n")
    return load_task(t.dir)


def test_digest_lists_real_tasks_with_sources_and_flags(tmp_path, capsys):
    real, audit = real_task(tmp_path), audit_task(tmp_path)
    sealed = make_task(tmp_path, "real-sealed", "ui", private=True, repo="/x/r")
    (sealed.dir / "task.toml").write_text(sealed.dir.joinpath("task.toml").read_text()
                                          + "heldout = true\n")
    seed = make_task(tmp_path, "seed-x", "feature", prompt="add a settle up section\nmore\n")
    (seed.dir / "hidden").mkdir()
    seed = load_task(seed.dir)
    md = D.render([real, audit, load_task(sealed.dir), seed])
    assert capsys.readouterr().out == ""  # *_src.py never run as __main__
    assert "real-sealed" not in md
    assert "## Real tasks (2)" in md and "## Seeded tasks (1)" in md
    assert "````text\n" + PROMPT.rstrip("\n") + "\n````" in md  # verbatim, fenced safely
    assert "- Category: ui" in md
    assert ("1. `starts-with-photos` (script): Opens on the photos.\n"
            "   - Source: thread c5d1: remove the intro\n"
            "   - **Flag for user:** from a later audit") in md
    assert "   - Source: NOTES.md: judge | follow-up 21:04Z 'cut jargon'" in md
    assert "`orphan` (judge): No source anywhere.\n   - Source: **none found**" in md
    assert "not in the graded JSON (rebuild it?): removed-item" in md
    assert ("1. `ki-xss` [critical] a.rs:3-9: XSS via inner_html.\n"
            "   - Source: audit_ref: C1; fix: 2d8c04d") in md
    assert "- `seed-x` (feature): add a settle up section [hidden tests]" in md


def test_write_digest(tmp_path):
    out = D.write_digest([real_task(tmp_path)], tmp_path / "sub" / "_digest.md")
    assert out.read_text().startswith("# bruhsbench task digest")


def test_broken_source_file_is_reported_not_fatal(tmp_path):
    t = real_task(tmp_path)
    (t.dir / "checklist_src.py").write_text("raise RuntimeError('boom')\n")
    md = D.render([t])
    assert "> could not load checklist_src.py: RuntimeError: boom" in md
