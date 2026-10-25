from __future__ import annotations

import json
from types import SimpleNamespace

import pytest

from results_fixture import make_run, make_task, make_verdict

from bruhsbench import cli
from bruhsbench.graders import grade_all
from bruhsbench.tasks import load_task


@pytest.fixture(autouse=True)
def roomy_disk(tmp_path, monkeypatch):
    """Plenty of free disk (the guard has its own tests), work root under tmp_path."""
    monkeypatch.setenv("BRUHSBENCH_MIN_FREE_GB", "0")
    monkeypatch.setenv("BRUHSBENCH_WORK", str(tmp_path / "work"))


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
    judge = SimpleNamespace(extract_findings=None, match_finding=None, classify_finding=None,
                            extract_claims=None, claimed_items=None)
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


# --------------------------------------------------------------------------- disk + cleanup


def _all_graded(d):
    (d / "grades").mkdir(exist_ok=True)
    for n in cli.GRADE_FILES:
        (d / "grades" / f"{n}.json").write_text(json.dumps({"applicable": False}))


def test_grade_stops_on_low_disk(tmp_path, monkeypatch, capsys):
    t = make_task(tmp_path, "t-audit", "audit")
    root = tmp_path / "res"
    make_run(root, t, "claude", "bare", 1)
    monkeypatch.setattr(cli, "_task_index", lambda heldout: {t.id: t})
    monkeypatch.setenv("BRUHSBENCH_MIN_FREE_GB", "40")
    monkeypatch.setattr("bruhsbench.runner.free_gb", lambda p: 3.0)
    monkeypatch.setattr(cli, "_grade_run", lambda d, task: pytest.fail("graded on a full disk"))
    assert cli.cmd_grade(_args(root)) == cli.DISK_LOW_EXIT
    assert "3.0 GB free" in capsys.readouterr().err


def test_grade_never_regrades_a_deleted_workspace(tmp_path, monkeypatch, capsys):
    t = make_task(tmp_path, "t-audit", "audit")
    root = tmp_path / "res"
    d = make_run(root, t, "claude", "bare", 1)
    meta = json.loads((d / "result.json").read_text())
    (d / "result.json").write_text(json.dumps({**meta, "workspace_deleted": True}))
    _all_graded(d)
    monkeypatch.setattr(cli, "_task_index", lambda heldout: {t.id: t})
    monkeypatch.setattr(cli, "_grade_run", lambda d, task: pytest.fail("regraded"))
    cli.cmd_grade(_args(root, force=True))
    assert "workspace was deleted" in capsys.readouterr().err


def _work_dir(root, d, precious):
    """A run's work dir with symlinks an agent could plant: to a precious dir outside,
    to the results dir and to the task dir."""
    from bruhsbench.runner import default_work_root

    ws = default_work_root(root) / d.name / "workspace"
    (ws / "node_modules" / "pkg").mkdir(parents=True)
    (ws / "node_modules" / "pkg" / "index.js").write_text("x")
    (ws / "to_precious").symlink_to(precious)
    (ws / "to_results").symlink_to(root)
    (ws / "to_file").symlink_to(precious / "keep.txt")
    return ws


def _clean_fixture(tmp_path):
    precious = tmp_path / "precious"
    precious.mkdir()
    (precious / "keep.txt").write_text("keep")
    audit = make_task(tmp_path, "t-audit", "audit")
    ui = make_task(tmp_path, "t-ui", "ui", pages=["/"])
    root = tmp_path / "res"
    runs = {
        "graded": make_run(root, audit, "claude", "bare", 1),
        "ungraded": make_run(root, audit, "claude", "bruhs", 1),
        "errored": make_run(root, audit, "codex", "bare", 1, status="error"),
        "ui_uncaptured": make_run(root, ui, "claude", "bare", 1),
        "ui_done": make_run(root, ui, "claude", "bruhs", 1, screens=True),
        "ui_capture_error": make_run(root, ui, "codex", "bare", 1),
        "ui_page_errors": make_run(root, ui, "codex", "bruhs", 1),
    }
    for k, rec in (("ui_capture_error", {"applicable": True, "error": "server never ready"}),
                   ("ui_page_errors", {"applicable": True, "page_errors": {"/": "500"}})):
        _all_graded(runs[k])
        (runs[k] / "grades" / "capture.json").write_text(json.dumps(rec))
    _all_graded(runs["graded"])
    _all_graded(runs["ui_uncaptured"])
    _all_graded(runs["ui_done"])
    (runs["ui_done"] / "grades" / "capture.json").write_text(json.dumps({"applicable": True}))
    work = {k: _work_dir(root, d, precious) for k, d in runs.items()}
    return root, runs, work, precious, {audit.id: audit, ui.id: ui}


def test_clean_removes_only_finished_runs_and_never_follows_links(tmp_path, monkeypatch,
                                                                   capsys):
    root, runs, work, precious, tasks = _clean_fixture(tmp_path)
    monkeypatch.setattr(cli, "_task_index", lambda heldout: tasks)
    before = sorted(p.relative_to(root) for p in root.rglob("*"))
    assert cli.cmd_clean(_args(root, all=False)) == 0
    err = capsys.readouterr().err
    assert "capture failed" in err and runs["ui_capture_error"].name in err

    gone = {"graded", "errored", "ui_done", "ui_page_errors"}
    for k, ws in work.items():
        assert ws.parent.exists() == (k not in gone), k
        meta = json.loads((runs[k] / "result.json").read_text())
        assert meta.get("workspace_deleted", False) == (k in gone), k
    assert (precious / "keep.txt").read_text() == "keep"
    assert sorted(p.relative_to(root) for p in root.rglob("*")) == before  # results intact
    assert all(t.dir.is_dir() and (t.dir / "task.toml").is_file() for t in tasks.values())


def test_clean_all_removes_the_work_root_only(tmp_path, monkeypatch):
    from bruhsbench.runner import default_work_root

    root, runs, work, precious, tasks = _clean_fixture(tmp_path)
    monkeypatch.setattr(cli, "_task_index", lambda heldout: tasks)
    (default_work_root(root) / "_scratch" / "grade-1").mkdir(parents=True)
    other = default_work_root(tmp_path / "other-results")
    other.mkdir(parents=True)  # another results id's work root stays
    assert cli.cmd_clean(_args(root, all=True)) == 0
    assert not default_work_root(root).exists() and other.is_dir()
    assert (precious / "keep.txt").read_text() == "keep"
    assert all((d / "result.json").is_file() and (d / "diff.patch").is_file()
               for d in runs.values())
    assert all(json.loads((d / "result.json").read_text())["workspace_deleted"]
               for d in runs.values())


def test_parser_has_pipeline_and_clean():
    p = cli.build_parser()
    a = p.parse_args(["pipeline", "--tasks", "x"])
    assert a.fn is cli.cmd_pipeline and a.cleanup is True
    assert p.parse_args(["pipeline", "--no-cleanup"]).cleanup is False
    a = p.parse_args(["clean", "--all"])
    assert a.fn is cli.cmd_clean and a.all is True
    assert p.parse_args(["pipeline"]).post_parallel == 2
    assert p.parse_args(["pipeline", "--post-parallel", "1"]).post_parallel == 1


@pytest.fixture
def fake_agents(tmp_path, monkeypatch):
    """runner's hermetic setup (test_runner.hermetic): fake homes, fake CLI, sandboxed."""
    import os

    from bruhsbench import runner, sandbox

    def fake_build_home(cli_, arm, run_dir, bruhs_src, **kw):
        home = run_dir / "home"
        home.mkdir(parents=True)
        return {"PATH": os.environ["PATH"], "HOME": str(home)}

    monkeypatch.setattr(runner, "build_home", fake_build_home)
    monkeypatch.setattr(runner, "claude_auth", lambda: {})
    monkeypatch.setattr(runner, "cli_version", lambda c: f"{c} 0.0-test")
    side = tmp_path / "side"
    side.mkdir(exist_ok=True)
    monkeypatch.setattr(runner, "wrap", lambda argv, *, writable, **kw: sandbox.wrap(
        argv, writable=[*writable, side], **kw))


def test_pipeline_captures_grades_then_cleans_each_run(tmp_path, monkeypatch, fake_agents):
    from test_runner import CLAUDE, EDIT_AND_REPLY, fake_agent, override

    from bruhsbench.runner import default_work_root, run_matrix

    ui = make_task(tmp_path, "t-ui", "ui", pages=["/"])
    feat = make_task(tmp_path, "t-feat", "feature")
    for t in (ui, feat):
        (t.dir / "fixture").mkdir()
        (t.dir / "fixture" / "app.txt").write_text("hello\n")
    root = tmp_path / "res"
    events = []

    def fake_capture(d, task, ws):
        assert ws.is_dir()
        events.append(("capture", d.name))
        (d / "grades").mkdir(exist_ok=True)
        (d / "grades" / "capture.json").write_text(json.dumps({"applicable": True}))

    def fake_grade(d, task):
        assert (default_work_root(root) / d.name / "workspace").is_dir()
        events.append(("grade", d.name))
        _all_graded(d)

    monkeypatch.setattr(cli, "_capture_run", fake_capture)
    monkeypatch.setattr(cli, "_grade_run", fake_grade)
    monkeypatch.setattr("bruhsbench.capture.capture_before", lambda *a, **k: [])
    post = cli._post_processor(root, cli._disk_guard(root), cleanup=True)
    ov = override(fake_agent(tmp_path, EDIT_AND_REPLY))
    results = run_matrix([ui, feat], [CLAUDE], ["bare", "bruhs"], 1, root, parallel=2,
                         command_override=ov, post_run=post)
    assert len(results) == 4
    for r in results:
        assert not (default_work_root(root) / r.run_id).exists()
        meta = json.loads((root / r.run_id / "result.json").read_text())
        assert meta["workspace_deleted"] is True
        steps = [e for e, rid in events if rid == r.run_id]
        assert steps == (["capture", "grade"] if r.run_id.startswith("t-ui") else ["grade"])
    events.clear()
    run_matrix([ui, feat], [CLAUDE], ["bare", "bruhs"], 1, root, parallel=2,
               command_override=ov, post_run=post)  # resume: nothing left to do
    assert events == []


def test_pipeline_keeps_workspace_when_grading_is_incomplete(tmp_path, monkeypatch,
                                                             fake_agents):
    from test_runner import CLAUDE, EDIT_AND_REPLY, fake_agent, override

    from bruhsbench.runner import default_work_root, run_matrix

    feat = make_task(tmp_path, "t-feat", "feature")
    (feat.dir / "fixture").mkdir()
    (feat.dir / "fixture" / "app.txt").write_text("hello\n")
    root = tmp_path / "res"
    monkeypatch.setattr(cli, "_grade_run", lambda d, task: None)  # e.g. a judge failure
    run_matrix([feat], [CLAUDE], ["bare"], 1, root, command_override=override(
        fake_agent(tmp_path, EDIT_AND_REPLY)), post_run=cli._post_processor(root, cli._disk_guard(root), cleanup=True))
    rid = "t-feat__claude__bare__r1"
    assert (default_work_root(root) / rid / "workspace").is_dir()
    assert not json.loads((root / rid / "result.json").read_text())["workspace_deleted"]


def test_pipeline_post_run_waits_on_the_matrix_guard(tmp_path, monkeypatch):
    import threading

    from bruhsbench.runner import DiskGuard, DiskLow
    from bruhsbench.types import ModelSpec, RunSpec

    t = make_task(tmp_path, "t-audit", "audit")
    root = tmp_path / "res"
    make_run(root, t, "claude", "bare", 1)
    monkeypatch.setattr(cli, "_grade_run", lambda d, task: pytest.fail("graded on a full disk"))
    slept = []
    guard = DiskGuard([tmp_path], min_gb=40, free_fn=lambda p: 5.0, poll_s=0.1, wait_s=0.3,
                      sleep=slept.append)
    held, release = threading.Event(), threading.Event()

    def other_run():  # another run of the matrix is live, so its cleanup may free space
        with guard.job():
            held.set()
            release.wait(10)

    th = threading.Thread(target=other_run)
    th.start()
    held.wait(10)
    try:
        post = cli._post_processor(root, guard, cleanup=True)
        with guard.job(), pytest.raises(DiskLow):
            post(RunSpec(t, ModelSpec("claude", "m", "high"), "bare", 1), None)
    finally:
        release.set()
        th.join()
    assert slept  # it waited for the other run before giving up


def test_clean_reports_leftovers(tmp_path, monkeypatch, capsys):
    root, runs, work, precious, tasks = _clean_fixture(tmp_path)
    monkeypatch.setattr(cli, "_task_index", lambda heldout: tasks)
    monkeypatch.setattr("bruhsbench.runner.cleanup_run",
                        lambda out, wr, rid: [f"{wr}/{rid}/workspace/stuck"])
    assert cli.cmd_clean(_args(root, all=False)) == 1
    assert "could not fully delete" in capsys.readouterr().err


def test_clean_all_refuses_while_a_run_is_active(tmp_path, monkeypatch):
    from bruhsbench.runner import default_work_root, hold_active

    root, runs, work, precious, tasks = _clean_fixture(tmp_path)
    monkeypatch.setattr(cli, "_task_index", lambda heldout: tasks)
    with hold_active(default_work_root(root)):
        with pytest.raises(cli.CliError, match="--force"):
            cli.cmd_clean(_args(root, all=True))
        assert default_work_root(root).is_dir()
        assert cli.cmd_clean(_args(root, all=True, force=True)) == 0
    assert not default_work_root(root).exists()


def test_bad_min_free_gb_is_a_cli_error(tmp_path, monkeypatch, capsys):
    t = make_task(tmp_path, "t-audit", "audit")
    root = tmp_path / "res"
    make_run(root, t, "claude", "bare", 1)
    monkeypatch.setattr(cli, "_task_index", lambda heldout: {t.id: t})
    monkeypatch.setenv("BRUHSBENCH_MIN_FREE_GB", "lots")
    assert cli.main(["grade", "--results", str(root)]) == 2
    assert "BRUHSBENCH_MIN_FREE_GB" in capsys.readouterr().err


def test_pipeline_keeps_workspace_after_capture_harness_error(tmp_path, monkeypatch,
                                                             fake_agents, caplog):
    from test_runner import CLAUDE, EDIT_AND_REPLY, fake_agent, override

    from bruhsbench.runner import default_work_root, run_matrix

    ui = make_task(tmp_path, "t-ui", "ui", pages=["/"])
    (ui.dir / "fixture").mkdir()
    (ui.dir / "fixture" / "app.txt").write_text("hello\n")
    root = tmp_path / "res"
    attempts = []

    def failing_capture(d, task, ws):
        attempts.append(d.name)
        (d / "grades").mkdir(exist_ok=True)
        (d / "grades" / "capture.json").write_text(json.dumps(
            {"applicable": True, "error": "dev server never became ready"}))

    monkeypatch.setattr(cli, "_capture_run", failing_capture)
    monkeypatch.setattr(cli, "_grade_run", lambda d, task: _all_graded(d))
    monkeypatch.setattr("bruhsbench.capture.capture_before", lambda *a, **k: [])
    post = cli._post_processor(root, cli._disk_guard(root), cleanup=True)
    ov = override(fake_agent(tmp_path, EDIT_AND_REPLY))
    run_matrix([ui], [CLAUDE], ["bare"], 1, root, command_override=ov, post_run=post)
    rid = "t-ui__claude__bare__r1"
    assert attempts == [rid, rid]  # retried once
    assert (default_work_root(root) / rid / "workspace").is_dir()
    assert "capture failed" in caplog.text
    run_matrix([ui], [CLAUDE], ["bare"], 1, root, command_override=ov, post_run=post)
    assert len(attempts) == 4  # a later pipeline call retries it


def test_pipeline_caps_concurrent_post_processing(tmp_path, monkeypatch, fake_agents):
    import threading
    import time

    from test_runner import CLAUDE, EDIT_AND_REPLY, fake_agent, override

    from bruhsbench.runner import run_matrix

    feat = make_task(tmp_path, "t-feat", "feature")
    (feat.dir / "fixture").mkdir()
    (feat.dir / "fixture" / "app.txt").write_text("hello\n")
    root = tmp_path / "res"
    lock, live, peak = threading.Lock(), [0], [0]

    def slow_grade(d, task):
        with lock:
            live[0] += 1
            peak[0] = max(peak[0], live[0])
        time.sleep(0.3)
        with lock:
            live[0] -= 1
        _all_graded(d)

    monkeypatch.setattr(cli, "_grade_run", slow_grade)
    post = cli._post_processor(root, cli._disk_guard(root), cleanup=True, post_parallel=1)
    run_matrix([feat], [CLAUDE], ["bare", "bruhs"], 2, root, parallel=4,
               command_override=override(fake_agent(tmp_path, EDIT_AND_REPLY)), post_run=post)
    assert peak[0] == 1


# --------------------------------------------------------------------------- fix round 2


def _spec(task, cli_="claude", arm="bare", rep=1):
    from bruhsbench.types import ModelSpec, RunSpec

    return RunSpec(task, ModelSpec(cli_, "m", "high"), arm, rep)


def test_cleanup_only_runs_never_wait_or_take_a_slot(tmp_path, monkeypatch):
    import threading

    from bruhsbench.runner import DiskGuard, default_work_root

    t = make_task(tmp_path, "t-audit", "audit")
    root = tmp_path / "res"
    busy = make_run(root, t, "claude", "bare", 1)       # still has grading to do
    done = make_run(root, t, "claude", "bruhs", 1)      # graded: only cleanup left
    _all_graded(done)
    for d in (busy, done):
        (default_work_root(root) / d.name / "workspace").mkdir(parents=True)
    in_grade, release = threading.Event(), threading.Event()

    def blocking_grade(d, task):
        in_grade.set()
        release.wait(10)
        _all_graded(d)

    monkeypatch.setattr(cli, "_grade_run", blocking_grade)
    free = {"gb": 50.0}
    guard = DiskGuard([tmp_path], min_gb=40, free_fn=lambda p: free["gb"], wait_s=0)
    post = cli._post_processor(root, guard, cleanup=True, post_parallel=1)
    th = threading.Thread(target=post, args=(_spec(t, arm="bare"), None))
    th.start()
    try:
        assert in_grade.wait(10)  # the only slot is taken by a slow grade
        free["gb"] = 1.0          # and the disk is full: cleanup must still go through
        post(_spec(t, arm="bruhs"), None)
        assert not (default_work_root(root) / done.name).exists()
    finally:
        release.set()
        th.join()


def test_disk_wait_happens_outside_the_slot(tmp_path, monkeypatch):
    import threading

    from bruhsbench.runner import DiskGuard

    t = make_task(tmp_path, "t-audit", "audit")
    root = tmp_path / "res"
    a = make_run(root, t, "claude", "bare", 1)
    b = make_run(root, t, "claude", "bruhs", 1)
    graded = []
    monkeypatch.setattr(cli, "_grade_run", lambda d, task: graded.append(d.name) or
                        _all_graded(d))
    free = {"gb": 1.0}
    waiting, go = threading.Event(), threading.Event()

    def sleep(_s):
        waiting.set()
        go.wait(10)
        free["gb"] = 50.0

    guard = DiskGuard([tmp_path], min_gb=40, free_fn=lambda p: free["gb"], poll_s=1,
                      wait_s=60, sleep=sleep)
    post = cli._post_processor(root, guard, cleanup=False, post_parallel=1)
    held, release = threading.Event(), threading.Event()

    def other_job():  # a live agent run, so waiting for space makes sense
        with guard.job():
            held.set()
            release.wait(10)

    other = threading.Thread(target=other_job)
    other.start()
    held.wait(10)
    th = threading.Thread(target=post, args=(_spec(t, arm="bare"), None))
    th.start()
    try:
        assert waiting.wait(10)  # run a waits for disk...
        guard._free_fn = lambda p: 50.0
        post(_spec(t, arm="bruhs"), None)  # ...without holding the only slot
        assert graded == [b.name]
    finally:
        go.set()
        th.join()
        release.set()
        other.join()
    assert graded == [b.name, a.name]


def test_clean_all_holds_the_exclusive_lock_while_removing(tmp_path, monkeypatch):
    from bruhsbench import runner

    root, runs, work, precious, tasks = _clean_fixture(tmp_path)
    work_root = runner.default_work_root(root)
    real = runner.remove_work_root
    seen = []

    def spy(wr, **kw):
        seen.append(runner.work_root_active(wr))  # anyone else trying now is refused
        return real(wr, **kw)

    monkeypatch.setattr(runner, "remove_work_root", spy)
    assert cli.cmd_clean(_args(root, all=True)) == 0
    assert seen == [True] and not work_root.exists()


def test_capture_and_grade_hold_the_active_lock(tmp_path, monkeypatch):
    from bruhsbench.runner import default_work_root, work_root_active

    t = make_task(tmp_path, "t-ui", "ui", pages=["/"])
    root = tmp_path / "res"
    d = make_run(root, t, "claude", "bare", 1)
    ws = default_work_root(root) / d.name / "workspace"
    ws.mkdir(parents=True)
    meta = json.loads((d / "result.json").read_text())
    (d / "result.json").write_text(json.dumps({**meta, "workspace": str(ws)}))
    monkeypatch.setattr(cli, "_task_index", lambda heldout: {t.id: t})
    monkeypatch.setattr("bruhsbench.capture.capture_before", lambda *a, **k: [])
    seen = []
    monkeypatch.setattr(cli, "_capture_run",
                        lambda d, task, ws: seen.append(("capture", work_root_active(
                            default_work_root(root)))))
    monkeypatch.setattr(cli, "_grade_run",
                        lambda d, task: seen.append(("grade", work_root_active(
                            default_work_root(root)))))
    cli.cmd_capture(_args(root))
    cli.cmd_grade(_args(root))
    assert seen == [("capture", True), ("grade", True)]
    assert not work_root_active(default_work_root(root))


def test_hold_active_blocks_for_the_whole_clean_all(tmp_path, monkeypatch):
    import threading
    import time

    from bruhsbench import runner, untrusted

    wr = tmp_path / "work" / "w"
    (wr / "run" / "workspace").mkdir(parents=True)
    assert not runner.active_lock_path(wr).is_relative_to(wr)  # outside the deleted tree
    deleted, resume = threading.Event(), threading.Event()
    real_remove = untrusted.remove

    def paused_remove(root, name):
        real_remove(root, name)  # everything under the work root is gone...
        deleted.set()
        resume.wait(10)          # ...but the removal hasn't returned yet

    monkeypatch.setattr(untrusted, "remove", paused_remove)
    entered = threading.Event()

    def clean_all():
        with runner.exclusive_work_root(wr):
            runner.remove_work_root(wr)

    def later_run():
        with runner.hold_active(wr):
            entered.set()

    cleaner = threading.Thread(target=clean_all)
    cleaner.start()
    assert deleted.wait(10)
    run = threading.Thread(target=later_run)
    run.start()
    time.sleep(0.3)
    assert not entered.is_set()  # blocked mid-removal
    resume.set()
    cleaner.join()
    assert entered.wait(10)
    run.join()


def test_recapture_regrades_checklist_and_honesty(tmp_path, monkeypatch):
    from results_fixture import PNG

    from bruhsbench.graders import checklist, honesty

    t = make_task(tmp_path, "t-ui", "ui", pages=["/"])
    root = tmp_path / "res"
    d = make_run(root, t, "claude", "bare", 1)
    _all_graded(d)
    (d / "grades" / "checklist.json").write_text(json.dumps(
        {"applicable": True, "score": 0.5, "items": [], "screens": 0}))
    calls = []

    def good_capture(d, task, ws):
        (d / "screens").mkdir(exist_ok=True)
        (d / "screens" / "root__desktop__light.png").write_bytes(PNG)
        (d / "grades" / "capture.json").write_text(json.dumps({"applicable": True}))

    def fake_checklist(task, run_dir, judges):
        calls.append("checklist")
        (run_dir / "grades" / "checklist.json").write_text(json.dumps(
            {"applicable": True, "score": 1.0, "items": [], "screens": 1}))

    monkeypatch.setattr(cli, "_capture_run", good_capture)
    monkeypatch.setattr(checklist, "grade", fake_checklist)
    monkeypatch.setattr(honesty, "grade", lambda *a, **k: calls.append("honesty"))
    monkeypatch.setattr("bruhsbench.judge.make_judge", lambda c: SimpleNamespace(
        extract_claims=None, claimed_items=None))
    cli._capture_and_refresh(d, t, tmp_path)
    assert calls == ["checklist", "honesty"]
    old = json.loads((d / "grades" / "checklist.superseded.json").read_text())
    assert old["superseded"] is True and old["score"] == 0.5
    calls.clear()
    cli._capture_and_refresh(d, t, tmp_path)  # graded with screenshots: nothing to redo
    assert calls == []


def test_recapture_with_page_errors_regrades_before_cleanup(tmp_path, monkeypatch,
                                                           fake_agents):
    from results_fixture import PNG
    from test_runner import CLAUDE, EDIT_AND_REPLY, fake_agent, override

    from bruhsbench.runner import default_work_root, run_matrix

    ui = make_task(tmp_path, "t-ui", "ui", pages=["/"])
    (ui.dir / "fixture").mkdir()
    (ui.dir / "fixture" / "app.txt").write_text("hello\n")
    root = tmp_path / "res"
    rid = "t-ui__claude__bare__r1"
    outcome = {"capture": {"applicable": True, "error": "dev server never became ready"}}
    events = []

    def capture(d, task, ws):
        (d / "grades").mkdir(exist_ok=True)
        rec = outcome["capture"]
        if "page_errors" in rec:  # a finished capture still writes PNGs
            (d / "screens").mkdir(exist_ok=True)
            (d / "screens" / "root__desktop__light.png").write_bytes(PNG)
        (d / "grades" / "capture.json").write_text(json.dumps(rec))

    def grade(d, task):
        _all_graded(d)
        n = len(list((d / "screens").glob("*.png")))
        (d / "grades" / "checklist.json").write_text(json.dumps(
            {"applicable": True, "score": 0.5, "items": [], "screens": n}))

    def regrade(d, task):
        events.append(("regrade", (default_work_root(root) / rid / "workspace").is_dir()))
        (d / "grades" / "checklist.json").write_text(json.dumps(
            {"applicable": True, "score": 1.0, "items": [], "screens": 1}))

    monkeypatch.setattr(cli, "_capture_run", capture)
    monkeypatch.setattr(cli, "_grade_run", grade)
    monkeypatch.setattr(cli, "_regrade_after_capture", regrade)
    monkeypatch.setattr("bruhsbench.capture.capture_before", lambda *a, **k: [])
    post = cli._post_processor(root, cli._disk_guard(root), cleanup=True)
    ov = override(fake_agent(tmp_path, EDIT_AND_REPLY))
    run_matrix([ui], [CLAUDE], ["bare"], 1, root, command_override=ov, post_run=post)
    assert (default_work_root(root) / rid / "workspace").is_dir()  # harness error: kept
    assert events == []

    outcome["capture"] = {"applicable": True, "page_errors": {"/": "500"}}
    run_matrix([ui], [CLAUDE], ["bare"], 1, root, command_override=ov, post_run=post)
    assert events == [("regrade", True)]  # regraded while the workspace still existed
    assert not (default_work_root(root) / rid).exists()  # then cleaned


# --------------------------------------------------------------------------- freeze


def _run_args(root, **kw):
    base = dict(results=str(root), pilot=False, heldout=False, force=False, parallel=1,
                tasks=None, models=["claude"], repeats=1, timeout=1, allow_unfrozen=False)
    return type("A", (), {**base, **kw})()


@pytest.fixture
def frozen_env(tmp_path, monkeypatch):
    """Two tasks, frozen files under tmp_path, run_matrix stubbed to record its call."""
    from bruhsbench import freeze, runner

    monkeypatch.setattr(freeze, "FROZEN_PUBLIC", tmp_path / "frozen.sha256")
    monkeypatch.setattr(freeze, "FROZEN_PRIVATE", tmp_path / "_frozen.sha256")
    tasks = [make_task(tmp_path, "t-a", "feature"), make_task(tmp_path, "t-b", "audit")]
    monkeypatch.setattr(cli, "load_all_tasks", lambda: tasks)
    monkeypatch.setattr(cli, "pilot_task_ids", lambda: ["t-a"])
    calls = []
    monkeypatch.setattr(runner, "run_matrix", lambda *a, **k: calls.append(k) or [])
    return tasks, calls


def test_run_refuses_unfrozen_tasks(tmp_path, frozen_env):
    from bruhsbench import freeze

    tasks, calls = frozen_env
    with pytest.raises(cli.CliError, match="t-a: not frozen"):
        cli.cmd_run(_run_args(tmp_path / "res"))
    freeze.freeze(tasks)
    (tasks[1].dir / "prompt.md").write_text("changed\n")
    with pytest.raises(cli.CliError, match=r"t-b: changed since the freeze: changed task/prompt"):
        cli.cmd_run(_run_args(tmp_path / "res"))
    assert calls == []
    assert cli.cmd_run(_run_args(tmp_path / "res", tasks=["t-a"])) == 0
    rec = calls[-1]["record"]
    assert rec == {"task_hashes": {"t-a": freeze.task_hash(tasks[0])}, "unfrozen": {},
                   "allow_unfrozen": False}


def test_allow_unfrozen_runs_and_is_recorded(tmp_path, frozen_env, capsys):
    tasks, calls = frozen_env
    assert cli.cmd_run(_run_args(tmp_path / "res", allow_unfrozen=True)) == 0
    rec = calls[-1]["record"]
    assert rec["allow_unfrozen"] is True and set(rec["unfrozen"]) == {"t-a", "t-b"}
    assert "unfrozen" in capsys.readouterr().err


def test_pilot_runs_unfrozen_and_records_hashes(tmp_path, frozen_env):
    from bruhsbench import freeze

    tasks, calls = frozen_env
    assert cli.cmd_run(_run_args(tmp_path / "res", pilot=True)) == 0
    rec = calls[-1]["record"]
    assert rec["task_hashes"] == {"t-a": freeze.task_hash(tasks[0])}
    assert rec["allow_unfrozen"] is False and "t-a" in rec["unfrozen"]


def test_too_long_tmpdir_is_a_cli_error(tmp_path, frozen_env, monkeypatch, capsys):
    from bruhsbench import runner, sandbox

    def boom(*a, **k):
        sandbox.check_tmp_base()

    monkeypatch.setattr(runner, "run_matrix", boom)
    monkeypatch.setenv("BRUHSBENCH_TMP", "/private/tmp/" + "x" * 70)
    assert cli.main(["run", "--results", str(tmp_path / "res"), "--allow-unfrozen",
                     "--models", "claude"]) == 2
    assert "BRUHSBENCH_TMP" in capsys.readouterr().err


def test_freeze_and_digest_commands(tmp_path, frozen_env, capsys, monkeypatch):
    from bruhsbench import freeze

    tasks, _ = frozen_env
    assert cli.main(["freeze"]) == 0
    assert "new 2: t-a t-b" in capsys.readouterr().out
    assert freeze.check(tasks).unfrozen == {}
    (tasks[0].dir / "prompt.md").write_text("changed\n")
    assert cli.main(["freeze", "--tasks", "t-a"]) == 0
    assert "changed 1: t-a" in capsys.readouterr().out
    assert cli.main(["freeze", "--tasks", "nope"]) == 2
    out = tmp_path / "digest.md"
    assert cli.main(["digest", "--out", str(out)]) == 0
    assert "`t-a` (feature)" in out.read_text()
    p = cli.build_parser()
    assert p.parse_args(["pipeline", "--allow-unfrozen"]).allow_unfrozen is True
    assert p.parse_args(["run"]).allow_unfrozen is False
