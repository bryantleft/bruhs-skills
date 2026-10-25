from __future__ import annotations

import pytest

from results_fixture import (
    audit_grades,
    feature_grades,
    make_run,
    make_task,
    make_verdict,
    ship_grades,
)

from bruhsbench.score import (
    activated,
    bare_leak,
    bootstrap_ci,
    decide,
    primary_metric,
    summarize,
)


@pytest.fixture
def tasks(tmp_path):
    return {c: make_task(tmp_path, f"t-{c}", c) for c in
            ("feature", "debug", "audit", "ui", "copy", "pr-review", "ship")}


# --------------------------------------------------------------------------- decide


@pytest.mark.parametrize("category", ["feature", "debug", "pr-review"])
def test_decide_margins_repeat_categories(tasks, category):
    t = tasks[category]
    # at the margin: 1 of 3 repeats better -> tie (float noise must not tip it)
    assert decide(t, [1, 0, 0], [1, 1, 0], None) == "tie"
    assert decide(t, [1, 1, 0], [1, 0, 0], None) == "tie"
    # just under: equal
    assert decide(t, [1, 0, 0], [0, 1, 0], None) == "tie"
    # just over: 2 of 3 repeats, or 1 of 2 surviving repeats
    assert decide(t, [0, 0, 0], [1, 1, 0], None) == "win"
    assert decide(t, [1, 1, 1], [1, 0, 0], None) == "loss"
    assert decide(t, [0, 0], [1, 0], None) == "win"


def test_decide_margins_audit(tasks):
    t = tasks["audit"]
    assert decide(t, [0.50], [0.55], None) == "tie"   # at
    assert decide(t, [0.50], [0.54], None) == "tie"   # under
    assert decide(t, [0.50], [0.56], None) == "win"   # over
    assert decide(t, [0.56], [0.50], None) == "loss"
    assert decide(t, [0.6, 0.4], [0.65, 0.45], None) == "tie"  # means differ by 0.05


def test_decide_margins_ship(tasks):
    t = tasks["ship"]
    assert decide(t, [0.6], [0.7], None) == "tie"     # at 10 points
    assert decide(t, [0.6], [0.69], None) == "tie"
    assert decide(t, [0.6], [0.71], None) == "win"
    assert decide(t, [0.71], [0.6], None) == "loss"


@pytest.mark.parametrize("category", ["ui", "copy"])
def test_decide_margins_pairwise(tasks, category):
    t = tasks[category]
    # 11 of 20 verdicts for bruhs -> 0.55: win (R23 b, inclusive)
    assert decide(t, [], [], ["bruhs"] * 11 + ["bare"] * 9) == "win"
    assert decide(t, [], [], ["bruhs"] * 9 + ["bare"] * 9 + ["tie"] * 2) == "tie"  # 0.5
    assert decide(t, [], [], ["bruhs"] * 12 + ["bare"] * 8) == "win"   # 0.6
    # 0.54: tie, 0.45: loss, 0.46: tie
    assert decide(t, [], [], ["bruhs"] * 27 + ["bare"] * 23) == "tie"
    assert decide(t, [], [], ["bruhs"] * 9 + ["bare"] * 11) == "loss"
    assert decide(t, [], [], ["bruhs"] * 23 + ["bare"] * 27) == "tie"
    with pytest.raises(ValueError):
        decide(t, [], [], [])


def test_decide_needs_data(tasks):
    with pytest.raises(ValueError):
        decide(tasks["audit"], [], [0.5], None)


# --------------------------------------------------------------------------- primary metric


def test_primary_metric_feature_requires_all_three(tasks):
    t = tasks["feature"]
    assert primary_metric(t, feature_grades(True)) == 1.0
    assert primary_metric(t, feature_grades(False)) == 0.0
    g = feature_grades(True)
    g["honesty"]["honest_done"] = False
    assert primary_metric(t, g) == 0.0
    g = feature_grades(True)
    g["commands"]["regressions"] = ["test_a"]
    assert primary_metric(t, g) == 0.0
    g = feature_grades(True)
    g["commands"]["regressions"] = None  # R23 c: not computed = not clean
    assert primary_metric(t, g) == 0.0
    g = feature_grades(True)
    g["honesty"] = {"applicable": True, "error": "Traceback"}
    assert primary_metric(t, g) is None
    g = feature_grades(True)
    g["commands"] = {"applicable": True, "error": "Traceback"}
    assert primary_metric(t, g) is None


def test_primary_metric_other_categories(tasks):
    assert primary_metric(tasks["audit"], audit_grades(0.42)) == 0.42
    assert primary_metric(tasks["ship"], ship_grades(0.8)) == 0.8
    assert primary_metric(tasks["ship"], ship_grades(None)) is None  # R23 c
    pr = {**feature_grades(True), **ship_grades(1.0)}
    assert primary_metric(tasks["pr-review"], pr) == 1.0
    pr = {**feature_grades(True), **ship_grades(0.75)}
    assert primary_metric(tasks["pr-review"], pr) == 0.0
    pr = {**feature_grades(True), **ship_grades(1.0)}
    pr["commands"]["checks"]["lint"] = False
    assert primary_metric(tasks["pr-review"], pr) == 0.0
    with pytest.raises(ValueError):
        primary_metric(tasks["ui"], {})


# --------------------------------------------------------------------------- cost


def test_cost_does_not_affect_decision(tmp_path, tasks):
    t = tasks["audit"]
    cheap, dear = tmp_path / "cheap", tmp_path / "dear"
    for root, bruhs_cost in ((cheap, 0.01), (dear, 500.0)):
        for r in (1, 2, 3):
            make_run(root, t, "codex", "bare", r, grades=audit_grades(0.4), cost=1.0)
            make_run(root, t, "codex", "bruhs", r, grades=audit_grades(0.6), cost=bruhs_cost,
                     wall_s=99999, turns=999)
    a, b = summarize(cheap, tasks=[t]), summarize(dear, tasks=[t])
    assert [o.decision for o in a.tasks] == [o.decision for o in b.tasks] == ["win"]
    assert a.models["codex"].arms["bruhs"]["cost_usd"] != b.models["codex"].arms["bruhs"]["cost_usd"]
    # decide takes no cost at all
    assert decide(t, [0.4], [0.6], None) == "win"


# --------------------------------------------------------------------------- bootstrap


def test_bootstrap_ci_contains_point_estimate():
    values = [1, 1, 0.5, 0, 1, 0.5, 1, 0, 1, 1]
    point = sum(values) / len(values)
    lo, hi = bootstrap_ci(values, resamples=10_000, seed=0)
    assert lo <= point <= hi
    assert 0 <= lo < hi <= 1
    assert bootstrap_ci([1, 1, 1]) == (1.0, 1.0)
    assert bootstrap_ci([]) is None
    assert bootstrap_ci(values, seed=3) == bootstrap_ci(values, seed=3)


# --------------------------------------------------------------------------- summarize


def test_summarize_excludes_bad_pairs_from_both_arms(tmp_path, tasks):
    t = tasks["audit"]
    root = tmp_path / "res"
    # r1 valid: bruhs better; r2 contaminated bruhs; r3 bare error; r4 bare timeout no diff
    make_run(root, t, "claude", "bare", 1, grades=audit_grades(0.2))
    make_run(root, t, "claude", "bruhs", 1, grades=audit_grades(0.9))
    make_run(root, t, "claude", "bare", 2, grades=audit_grades(0.9))
    make_run(root, t, "claude", "bruhs", 2, grades=audit_grades(0.0), contaminated=True)
    make_run(root, t, "claude", "bare", 3, grades=audit_grades(0.9), status="error")
    make_run(root, t, "claude", "bruhs", 3, grades=audit_grades(0.0))
    make_run(root, t, "claude", "bare", 4, grades=audit_grades(0.9), status="timeout", diff="")
    make_run(root, t, "claude", "bruhs", 4, grades=audit_grades(0.0))
    # r5: timeout with a diff is graded normally; contaminated None counted, not excluded
    make_run(root, t, "claude", "bare", 5, grades=audit_grades(0.2), status="timeout")
    make_run(root, t, "claude", "bruhs", 5, grades=audit_grades(0.9), contaminated=None)
    s = summarize(root, tasks=[t])
    (o,) = s.tasks
    assert o.bare == [0.2, 0.2] and o.bruhs == [0.9, 0.9]
    assert sorted(o.excluded) == [2, 3, 4]
    assert o.decision == "win"
    c = s.counts
    assert c["bruhs"]["contaminated"] == 1 and c["bruhs"]["contaminated_unknown"] == 1
    assert c["bare"]["error"] == 1 and c["bare"]["timeout"] == 2
    assert c["bare"]["timeout_no_diff"] == 1
    # arm means only over runs in valid pairs
    assert s.models["claude"].arms["bare"]["runs"] == 2


def test_summarize_pairwise_and_judge_errors(tmp_path, tasks):
    t = tasks["ui"]
    root = tmp_path / "res"
    for r in (1, 2):
        make_run(root, t, "grok", "bare", r)
        make_run(root, t, "grok", "bruhs", r)
    make_verdict(root, t, "grok", 1, "claude", "bruhs", bruhs_shown_as="B")
    make_verdict(root, t, "grok", 1, "codex", "bruhs", bruhs_shown_as="A")
    make_verdict(root, t, "grok", 2, "claude", "tie")
    make_verdict(root, t, "grok", 2, "codex", None)  # judge error: excluded and counted
    s = summarize(root, tasks=[t])
    (o,) = s.tasks
    assert sorted(o.prefs) == ["bruhs", "bruhs", "tie"]
    assert o.decision == "win"
    assert o.judge_errors == 1
    assert s.models["grok"].judge_errors == 1


def test_summarize_win_rate_and_seeded_subset(tmp_path):
    root = tmp_path / "res"
    seeded = make_task(tmp_path, "seed-audit", "audit")
    real = make_task(tmp_path, "real-audit", "audit", private=True, repo="/x/secret")
    for t, bare, bruhs in ((seeded, 0.1, 0.9), (real, 0.9, 0.1)):
        make_run(root, t, "claude", "bare", 1, grades=audit_grades(bare))
        make_run(root, t, "claude", "bruhs", 1, grades=audit_grades(bruhs))
    s = summarize(root, tasks=[seeded, real])
    m = s.models["claude"]
    assert (m.overall.wins, m.overall.ties, m.overall.losses) == (1, 0, 1)
    assert m.overall.win_rate == 0.5
    assert m.seeded.wins == 1 and m.seeded.n == 1 and m.seeded.win_rate == 1.0
    assert m.per_category["audit"]["mean_delta"] == pytest.approx(0.0)


def test_activation_and_bare_leak():
    skill_read = ('{"type":"assistant","message":{"content":[{"type":"tool_use","name":"Read",'
                  '"input":{"file_path":"/w/home/plugins/bruhs/commands/cook.md"}}]}}\n')
    init_only = '{"type":"system","subtype":"init","skills":["bruhs:cook"],"plugins":[{"path":"/h/plugins/bruhs/"}]}\n'
    codex = '{"type":"item.completed","item":{"type":"command_execution","command":"cat /h/.agents/skills/bruhs/SKILL.md"}}\n'
    assert activated(skill_read) and activated(codex)
    assert not activated(init_only)
    assert bare_leak('{"text":"I will use bruhs:cook"}')
    assert not bare_leak('{"cwd":"/private/tmp/bruhsbench/res-1/x","p":"/_bruhs/abc"}')


def test_summarize_reports_activation(tmp_path, tasks):
    t = tasks["audit"]
    root = tmp_path / "res"
    make_run(root, t, "claude", "bare", 1, grades=audit_grades(0.5),
             transcript='{"type":"assistant","text":"no skill here"}\n')
    make_run(root, t, "claude", "bruhs", 1, grades=audit_grades(0.5),
             transcript='{"type":"assistant","x":"/h/plugins/bruhs/SKILL.md"}\n')
    make_run(root, t, "claude", "bare", 2, grades=audit_grades(0.5),
             transcript='{"type":"assistant","text":"loading bruhs"}\n')
    make_run(root, t, "claude", "bruhs", 2, grades=audit_grades(0.5), transcript="")
    s = summarize(root, tasks=[t])
    assert s.activation["claude"] == {"runs": 2, "activated": 1, "rate": 0.5}
    assert s.bare_leaks["claude"] == ["t-audit__claude__bare__r2"]
