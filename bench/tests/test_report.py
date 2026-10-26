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


def test_method_states_the_tmp_write_limitation(tmp_path, summary):
    """R39: the literal /tmp is not writable (only the private TMPDIR), in both arms."""
    for private in (True, False):
        html, md = render(summary, tmp_path / str(private), private=private)
        for text in (html.read_text(), md.read_text()):
            assert "/tmp" in text and "TMPDIR" in text and "both arms" in text


@pytest.mark.parametrize("legacy", (False, True))
def test_header_names_the_pinned_bruhs(tmp_path, summary, legacy):
    """R41 matrices pin the bruhs content hash; the header shows it and the harness
    commit(s) of the starts. Older matrices still show their pinned bruhs commit."""
    import dataclasses

    if legacy:
        matrix = {"bruhs_commit": "c0ffee" * 7, "starts": [{}]}
    else:
        matrix = {"bruhs_content": "abc123" * 10,
                  "starts": [{"harness_commit": "1111aaaa" * 5},
                             {"harness_commit": "2222bbbb" * 5},
                             {"harness_commit": "1111aaaa" * 5}]}
    html, md = render(dataclasses.replace(summary, matrix=matrix), tmp_path / "o",
                      private=True)
    for text in (html.read_text(), md.read_text()):
        if legacy:
            assert "bruhs commit" in text and "c0ffeec0ffee" in text
        else:
            assert "bruhs commit" not in text and "bruhs content" in text
            assert "abc123abc123" in text
            assert "1111aaaa1111" in text and "2222bbbb2222" in text
            assert text.count("1111aaaa1111") == 1  # each harness commit once
