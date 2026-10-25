from __future__ import annotations

import json
from types import SimpleNamespace

import pytest

from results_fixture import make_run, make_task, make_verdict

from bruhsbench import cli
from bruhsbench.graders import grade_all
from bruhsbench.tasks import load_task


def _heldout_task(tmp_path):
    d = tmp_path / "tasks-heldout" / "sealed"
    d.mkdir(parents=True)
    (d / "task.toml").write_text('id = "sealed"\ncategory = "feature"\n')
    (d / "prompt.md").write_text("x")
    return load_task(d)


def test_select_tasks_refuses_heldout(tmp_path):
    open_ = make_task(tmp_path, "open", "audit")
    sealed = _heldout_task(tmp_path)
    tasks = [open_, sealed]
    assert cli.select_tasks(tasks, None, heldout=False) == [open_]
    assert cli.select_tasks(tasks, ["open"], heldout=False) == [open_]
    with pytest.raises(cli.CliError, match="held-out"):
        cli.select_tasks(tasks, ["open", "sealed"], heldout=False)
    assert cli.select_tasks(tasks, ["sealed"], heldout=True) == [sealed]
    assert cli.select_tasks(tasks, None, heldout=True) == [sealed]
    with pytest.raises(cli.CliError, match="unknown"):
        cli.select_tasks(tasks, ["nope"], heldout=False)


def test_pilot_file(tmp_path):
    p = tmp_path / "pilot.toml"
    with pytest.raises(cli.CliError):
        cli.pilot_task_ids(p)
    p.write_text('tasks = ["a", "b"]\n')
    assert cli.pilot_task_ids(p) == ["a", "b"]


def test_select_models():
    assert [m.cli for m in cli.select_models(["codex", "grok-4.7"])] == ["codex", "grok"]
    with pytest.raises(cli.CliError):
        cli.select_models(["gpt-2"])


def test_grade_all_order(tmp_path, monkeypatch):
    from bruhsbench.graders import audit, checklist, commands, honesty, scope

    order = []
    for name, mod in (("commands", commands), ("scope", scope), ("checklist", checklist),
                      ("audit", audit), ("honesty", honesty)):
        monkeypatch.setattr(mod, "grade", lambda *a, _n=name, **k: order.append(_n) or {})
    task = make_task(tmp_path, "t", "feature")
    judge = SimpleNamespace(extract_findings=None, match_finding=None, extract_claims=None,
                            claimed_items=None)
    grade_all(task, tmp_path, judge=judge, checklist_judges=[])
    assert order == ["commands", "scope", "checklist", "audit", "honesty"]


def _args(root, **kw):
    base = dict(results=str(root), pilot=False, heldout=False, force=False, parallel=1)
    return type("A", (), {**base, **kw})()


def test_grade_is_resumable(tmp_path, monkeypatch):
    t = make_task(tmp_path, "t-audit", "audit")
    root = tmp_path / "res"
    make_run(root, t, "claude", "bare", 1)
    make_run(root, t, "claude", "bruhs", 1, status="error")  # never graded
    monkeypatch.setattr(cli, "_task_index", lambda heldout: {t.id: t})
    calls = []

    def fake_grade_all(task, run_dir, judge, *, checklist_judges):
        assert {j.cli for j in checklist_judges} == {"codex", "grok"}
        calls.append(run_dir.name)
        for n in cli.GRADE_FILES:
            (run_dir / "grades" / f"{n}.json").write_text(json.dumps({"applicable": False}))
        return {}

    monkeypatch.setattr("bruhsbench.graders.grade_all", fake_grade_all)
    monkeypatch.setattr("bruhsbench.judge.make_judge", lambda c: object())
    cli.cmd_grade(_args(root))
    cli.cmd_grade(_args(root))
    assert calls == ["t-audit__claude__bare__r1"]
    cli.cmd_grade(_args(root, force=True))
    assert len(calls) == 2


def test_judge_skips_done_and_excluded_pairs(tmp_path, monkeypatch):
    t = make_task(tmp_path, "t-ui", "ui")
    root = tmp_path / "res"
    for r in (1, 2, 3):
        make_run(root, t, "codex", "bare", r, contaminated=(True if r == 3 else False))
        make_run(root, t, "codex", "bruhs", r)
    make_verdict(root, t, "codex", 1, "claude", "bruhs")  # done
    make_verdict(root, t, "codex", 1, "grok", None)       # judge error: retried
    monkeypatch.setattr(cli, "_task_index", lambda heldout: {t.id: t})
    seen = []

    def fake_pairwise(task, a, b, judge):
        seen.append((a.name, b.name, judge.cli))
        return {"winner": "A", "reasons": ""}

    monkeypatch.setattr("bruhsbench.judge.pairwise", fake_pairwise)
    cli.cmd_judge(_args(root))
    assert sorted(seen) == [
        ("t-ui__codex__bare__r1", "t-ui__codex__bruhs__r1", "grok"),
        ("t-ui__codex__bare__r2", "t-ui__codex__bruhs__r2", "claude"),
        ("t-ui__codex__bare__r2", "t-ui__codex__bruhs__r2", "grok"),
    ]


def test_pilot_with_tasks_is_refused(tmp_path):
    with pytest.raises(cli.CliError, match="--pilot"):
        cli.cmd_run(_args(tmp_path, pilot=True, tasks=["a"]))


def test_grade_warns_on_ui_runs_without_screens(tmp_path, monkeypatch, capsys):
    t = make_task(tmp_path, "t-ui", "ui")
    root = tmp_path / "res"
    make_run(root, t, "claude", "bare", 1, screens=True)
    make_run(root, t, "claude", "bruhs", 1)  # never captured
    make_run(root, t, "claude", "bare", 2, contaminated=True)  # excluded: not captured on purpose
    make_run(root, t, "claude", "bruhs", 2)
    monkeypatch.setattr(cli, "_task_index", lambda heldout: {t.id: t})
    monkeypatch.setattr("bruhsbench.graders.grade_all", lambda *a, **k: {})
    monkeypatch.setattr("bruhsbench.judge.make_judge", lambda c: object())
    cli.cmd_grade(_args(root))
    err = capsys.readouterr().err
    assert "capture" in err and "t-ui__claude__bruhs__r1" in err
    assert "t-ui__claude__bare__r1" not in err and "t-ui__claude__bare__r2" not in err
