from __future__ import annotations

import json
import threading
import urllib.request

import pytest

from results_fixture import make_run, make_task, make_verdict

from bruhsbench import spotcheck
from bruhsbench.score import summarize


@pytest.fixture
def root(tmp_path):
    root = tmp_path / "res"
    t = make_task(tmp_path, "t-ui", "ui", pages=("/",))
    for r in (1, 2, 3, 4):
        make_run(root, t, "claude", "bare", r, screens=True)
        make_run(root, t, "claude", "bruhs", r, screens=True)
        make_verdict(root, t, "claude", r, "codex", "bruhs")
        make_verdict(root, t, "claude", r, "grok", "bruhs" if r < 4 else None)
    return root, t


def _pick_arm(root, unit, arm):
    """Pick ``arm`` for ``unit`` through the blind left/right interface."""
    state = json.loads((root / "spotcheck.json").read_text())
    pair = next(p for p in state["pairs"] if p["unit"] == unit)
    side = "left" if pair["left"].split("__")[-2] == arm else "right"
    spotcheck.record_pick(root, unit, side)


def test_spotcheck_agreement(root):
    root, t = root
    assert spotcheck.agreement(root) is None  # nothing picked yet
    pairs = spotcheck.select_pairs(root, n=20, seed=1)
    assert len(pairs) == 4  # only 4 pairs exist
    assert spotcheck.select_pairs(root, n=20, seed=99) == pairs  # resumable, stable
    for r in (1, 2, 3):
        _pick_arm(root, f"t-ui__claude__r{r}", "bruhs")
    _pick_arm(root, "t-ui__claude__r4", "bare")
    # verdicts: r1-r3 both judges bruhs (6 agree), r4 codex bruhs (disagree), grok error
    assert spotcheck.agreement(root) == pytest.approx(6 / 7)


def test_low_agreement_switches_ui_to_user_picks(root):
    root, t = root
    spotcheck.select_pairs(root, n=20, seed=1)
    for r in (1, 2, 3, 4):
        _pick_arm(root, f"t-ui__claude__r{r}", "bare")
    assert spotcheck.agreement(root) == 0.0
    s = summarize(root, tasks=[t])
    assert s.ui_source == "user"
    (o,) = s.tasks
    assert o.prefs == ["bare"] * 4 and o.decision == "loss"


def test_pairs_page_is_blind(root):
    root, t = root
    spotcheck.select_pairs(root, n=2, seed=0)
    page = spotcheck.render_page(root)
    assert "bruhs" not in page.replace("bruhsbench", "") and "bare" not in page


def test_serve_records_picks(root):
    root, t = root
    server = spotcheck.make_server(root, n=20, seed=0, port=0)
    thread = threading.Thread(target=server.serve_forever, daemon=True)
    thread.start()
    try:
        base = f"http://127.0.0.1:{server.server_address[1]}"
        assert b"Pair 1" in urllib.request.urlopen(base + "/").read()
        unit = json.loads((root / "spotcheck.json").read_text())["pairs"][0]["unit"]
        req = urllib.request.Request(base + "/pick", data=json.dumps(
            {"unit": unit, "choice": "tie"}).encode(), method="POST")
        assert urllib.request.urlopen(req).status == 200
    finally:
        server.shutdown()
    picks = json.loads((root / "spotcheck.json").read_text())["picks"]
    assert picks[unit]["arm"] == "tie"
