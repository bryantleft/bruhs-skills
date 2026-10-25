from __future__ import annotations

import base64

import pytest

from results_fixture import (
    PNG,
    audit_grades,
    make_run,
    make_task,
    make_verdict,
)

from bruhsbench.report import render
from bruhsbench.score import summarize

SECRET_REPO = "/Users/someone/code/secret-mints-repo"
SECRET_PROMPT = "restyle the zorblax grade page so it stops looking generated"


@pytest.fixture
def summary(tmp_path):
    root = tmp_path / "results" / "full"
    private = make_task(tmp_path, "mints-grade-restyle", "ui", private=True,
                        repo=SECRET_REPO, prompt=SECRET_PROMPT, pages=("/grade",))
    seeded = make_task(tmp_path, "seed-audit-ts", "audit")
    for r in (1, 2):
        make_run(root, private, "claude", "bare", r, screens=True)
        make_run(root, private, "claude", "bruhs", r, screens=True)
        make_verdict(root, private, "claude", r, "codex", "bruhs")
        make_verdict(root, private, "claude", r, "grok", "bruhs")
        make_run(root, seeded, "claude", "bare", r, grades=audit_grades(0.3))
        make_run(root, seeded, "claude", "bruhs", r, grades=audit_grades(0.7))
    return summarize(root, tasks=[private, seeded])


def _outputs(out):
    return (out / "report.html").read_text(), (out / "report.md").read_text()


def test_public_report_has_no_private_paths(tmp_path, summary):
    out = tmp_path / "public"
    render(summary, out, private=False)
    png_b64 = base64.b64encode(PNG).decode()
    for text in _outputs(out):
        assert "tasks-private" not in text
        assert SECRET_REPO not in text and "secret-mints-repo" not in text
        assert "zorblax" not in text and SECRET_PROMPT not in text
        assert "mints-grade-restyle" not in text and "mints" not in text
        assert str(tmp_path) not in text
        assert png_b64 not in text  # the private task's screenshots
        assert "seed-audit-ts" in text  # public tasks keep their names
        assert "ui" in text  # private task still reported by category + score


def test_private_report_is_self_contained(tmp_path, summary):
    out = tmp_path / "private"
    render(summary, out, private=True)
    html, md = _outputs(out)
    assert "mints-grade-restyle" in html
    assert "data:image/png;base64," in html  # screenshots embedded
    assert "<link" not in html and 'src="http' not in html  # nothing fetched
    assert "<svg" in html  # per-model chart inline
    assert "Win rate" in md
