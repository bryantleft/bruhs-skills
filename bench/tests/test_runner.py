import json
import os
import stat
import time
from pathlib import Path

import pytest

from bruhsbench import runner
from bruhsbench.runner import AuthAbort, matrix_order, run_matrix, run_one, scan_contamination
from bruhsbench.tasks import load_task
from bruhsbench.types import ModelSpec, RunSpec

FIXTURES = Path(__file__).parent / "fixtures" / "cli_output"
CLAUDE = ModelSpec("claude", "claude-opus-5-5", "high")
CODEX = ModelSpec("codex", "gpt-6.1-sol", "high")


# --------------------------------------------------------------------------- helpers


def make_task(root: Path, task_id: str, setup: str | None = None):
    d = root / "tasks" / task_id
    (d / "fixture").mkdir(parents=True)
    (d / "fixture" / "app.txt").write_text("hello\n")
    # a detectable stack: the bruhs arm's rules block is empty otherwise
    (d / "fixture" / "package.json").write_text(
        '{"name":"x","dependencies":{"next":"15.0.0","react":"19.0.0"}}\n')
    (d / "task.toml").write_text(f'id = "{task_id}"\ncategory = "feature"\n')
    (d / "prompt.md").write_text("change app.txt\n")
    if setup is not None:
        (d / "setup.sh").write_text(setup)
    return load_task(d)


def fake_agent(root: Path, body: str) -> Path:
    """A shell script standing in for the CLI. Runs with cwd = workspace."""
    script = root / f"agent-{abs(hash(body))}.sh"
    script.write_text("#!/bin/bash\n" + body)
    script.chmod(script.stat().st_mode | stat.S_IEXEC)
    return script


def override(script: Path):
    return lambda spec, argv: ["bash", str(script)]


CLAUDE_OK = (FIXTURES / "claude.json").read_text().strip()
CLAUDE_AUTH = (FIXTURES / "claude_auth_error.json").read_text().strip()

EDIT_AND_REPLY = f"""
echo changed > app.txt
echo new > new.txt
cat <<'EOF'
{CLAUDE_OK}
EOF
"""


@pytest.fixture(autouse=True)
def hermetic(tmp_path, monkeypatch):
    """No real homes, no real CLIs: build_home just makes an empty home dir."""

    def fake_build_home(cli, arm, run_dir, bruhs_src, **kw):
        home = run_dir / "home"
        home.mkdir(parents=True)
        return {"PATH": os.environ["PATH"], "HOME": str(home)}

    monkeypatch.setattr(runner, "build_home", fake_build_home)
    monkeypatch.setattr(runner, "cli_version", lambda cli: f"{cli} 0.0-test")
    monkeypatch.setenv("BRUHSBENCH_WORK", str(tmp_path / "work"))


@pytest.fixture(scope="session")
def bruhs_src(tmp_path_factory):
    dest = tmp_path_factory.mktemp("export") / "bruhs"
    return runner.export_bruhs(runner.BRUHS_REPO, "HEAD", dest)


# --------------------------------------------------------------------------- run_one


def test_run_one_writes_artifacts(tmp_path, bruhs_src):
    task = make_task(tmp_path, "t1")
    out = tmp_path / "results"
    spec = RunSpec(task, CLAUDE, "bare", 1)
    res = run_one(spec, out, bruhs_src=bruhs_src,
                  command_override=override(fake_agent(tmp_path, EDIT_AND_REPLY)))

    d = out / spec.run_id
    assert res.status == "ok"
    assert res.final_message == "ok"
    assert res.turns == 1 and res.cost_usd == pytest.approx(0.0476062)
    assert res.input_tokens == 2 + 5662 + 11111 and res.output_tokens == 4
    assert res.transcript_path == d / "transcript.json"
    assert json.loads(res.transcript_path.read_text())["result"] == "ok"
    assert (d / "final.txt").read_text() == "ok"
    assert (d / "stderr.txt").exists()

    diff = res.diff_path.read_text()
    assert res.diff_path == d / "diff.patch"
    assert "+changed" in diff and "-hello" in diff and "new.txt" in diff

    # workspace stays in the work root (outside the results dir), path recorded
    assert res.workspace is not None and res.workspace.is_dir()
    assert not res.workspace.resolve().is_relative_to(out.resolve())
    assert res.workspace.resolve().is_relative_to((tmp_path / "work").resolve())
    assert not (d / "workspace").exists()

    saved = json.loads((d / "result.json").read_text())
    assert saved["status"] == "ok" and saved["run_id"] == spec.run_id
    assert saved["workspace"] == str(res.workspace)
    assert saved["contaminated"] is False and saved["contamination"] == []
    assert runner.load_result(d / "result.json") == res


def test_run_one_codex_final_from_output_file(tmp_path, bruhs_src):
    task = make_task(tmp_path, "t1")
    codex_out = (FIXTURES / "codex.jsonl").read_text()
    # codex writes its final message with -o <run_dir>/final.txt; the fake does the same
    body = f"cat <<'EOF'\n{codex_out}EOF\necho -n 'from file' > \"$FINAL\"\n"

    def ov(spec, argv):
        final = argv[argv.index("-o") + 1]
        return ["env", f"FINAL={final}", "bash", str(fake_agent(tmp_path, body))]

    res = run_one(RunSpec(task, CODEX, "bare", 1), tmp_path / "out", bruhs_src=bruhs_src,
                  command_override=ov)
    assert res.status == "ok"
    assert res.final_message == "from file"
    assert res.transcript_path.name == "transcript.jsonl"


def test_nonzero_exit_is_error(tmp_path, bruhs_src):
    task = make_task(tmp_path, "t1")
    res = run_one(RunSpec(task, CLAUDE, "bare", 1), tmp_path / "out", bruhs_src=bruhs_src,
                  command_override=override(fake_agent(tmp_path, "echo boom >&2; exit 3")))
    assert res.status == "error"
    assert "boom" in (tmp_path / "out" / res.run_id / "stderr.txt").read_text()


def test_timeout_recorded(tmp_path, bruhs_src):
    task = make_task(tmp_path, "t1")
    pidfile = tmp_path / "child.pid"
    body = f"""
echo partial > app.txt
sleep 60 &
echo $! > {pidfile}
sleep 60
"""
    start = time.monotonic()
    res = run_one(RunSpec(task, CLAUDE, "bare", 1), tmp_path / "out", timeout_s=2,
                  bruhs_src=bruhs_src, command_override=override(fake_agent(tmp_path, body)))
    assert time.monotonic() - start < 30
    assert res.status == "timeout"
    assert "+partial" in res.diff_path.read_text()
    assert json.loads((tmp_path / "out" / res.run_id / "result.json").read_text())[
        "status"] == "timeout"
    # the whole process group was killed, including the agent's background child
    child = int(pidfile.read_text())
    with pytest.raises(ProcessLookupError):
        for _ in range(50):
            os.kill(child, 0)
            time.sleep(0.1)


def test_auth_failure_raises_without_result(tmp_path, bruhs_src):
    task = make_task(tmp_path, "t1")
    body = f"cat <<'EOF'\n{CLAUDE_AUTH}\nEOF\nexit 1\n"
    spec = RunSpec(task, CLAUDE, "bare", 1)
    with pytest.raises(AuthAbort):
        run_one(spec, tmp_path / "out", bruhs_src=bruhs_src,
                command_override=override(fake_agent(tmp_path, body)))
    assert not (tmp_path / "out" / spec.run_id / "result.json").exists()


def test_setup_failure_in_run_recorded(tmp_path, bruhs_src):
    task = make_task(tmp_path, "t1", setup="exit 4\n")
    res = run_one(RunSpec(task, CLAUDE, "bare", 1), tmp_path / "out", bruhs_src=bruhs_src,
                  command_override=override(fake_agent(tmp_path, "exit 0")))
    assert res.status == "setup_failed"


# --------------------------------------------------------------------------- contamination


def test_scan_contamination_flags_real_home_and_repos(tmp_path):
    home = Path("/Users/someone")
    repo = Path("/opt/src/myrepo")
    work = Path("/private/tmp/bruhsbench/r/run")
    text = (
        'cat /Users/someone/.claude/settings.json\n'
        '{"cmd": "ls /Users/someone/Documents/x"}\n'
        "grep foo /opt/src/myrepo/app.ts\n"
        "/opt/src/myrepo-other/file is a different dir\n"
        "/private/tmp/bruhsbench/r/run/workspace/app.txt\n"
        "/Users/someone/.bun/bin/bun install\n"
        "/Users/someoneelse/file\n"
        '"path":"\\/Users\\/someone\\/.codex\\/auth.json"\n'
    )
    found = scan_contamination(text, forbidden=[home, repo], allowed=[work, home / ".bun/bin"])
    assert found == sorted({
        "/Users/someone/.claude/settings.json",
        "/Users/someone/Documents/x",
        "/opt/src/myrepo/app.ts",
        "/Users/someone/.codex/auth.json",
    })
    assert scan_contamination("/private/tmp/bruhsbench/r/run/home/.claude/x",
                              forbidden=[home], allowed=[work]) == []


def test_run_one_marks_contaminated(tmp_path, bruhs_src):
    task = make_task(tmp_path, "t1")
    leak = Path.home() / ".claude" / "CLAUDE.md"
    body = f"echo 'reading {leak}' >&2\n{EDIT_AND_REPLY}"
    res = run_one(RunSpec(task, CLAUDE, "bare", 1), tmp_path / "out", bruhs_src=bruhs_src,
                  command_override=override(fake_agent(tmp_path, body)))
    assert res.contaminated is True
    assert str(leak) in res.contamination


# --------------------------------------------------------------------------- matrix


def count_body(counter: Path, rest: str) -> str:
    return f"echo x >> {counter}\n{rest}"


def runs_started(counter: Path) -> int:
    return len(counter.read_text().splitlines()) if counter.exists() else 0


def test_matrix_interleaves_arms():
    tasks = [object(), object(), object()]
    order = matrix_order(tasks, [CLAUDE, CODEX], ["bare", "bruhs"], 3, seed=0)
    assert len(order) == 3 * 2 * 2 * 3
    assert order == matrix_order(tasks, [CLAUDE, CODEX], ["bare", "bruhs"], 3, seed=0)
    # the two arms of each (task, model, repeat) unit run back to back
    for i in range(0, len(order), 2):
        a, b = order[i], order[i + 1]
        assert (a.task, a.model, a.repeat) == (b.task, b.model, b.repeat)
        assert {a.arm, b.arm} == {"bare", "bruhs"}
    # shuffled: neither arm always goes first, units are not in nested-loop order
    firsts = [order[i].arm for i in range(0, len(order), 2)]
    assert "bare" in firsts and "bruhs" in firsts
    nested = [(t, m, r) for t in tasks for m in (CLAUDE, CODEX) for r in (1, 2, 3)]
    assert [(o.task, o.model, o.repeat) for o in order[::2]] != nested


def test_resume_skips_completed(tmp_path):
    task = make_task(tmp_path, "t1")
    out = tmp_path / "out"
    counter = tmp_path / "count"
    ov = override(fake_agent(tmp_path, count_body(counter, EDIT_AND_REPLY)))

    first = run_matrix([task], [CLAUDE], ["bare", "bruhs"], 2, out, parallel=2,
                       command_override=ov)
    assert runs_started(counter) == 4 and all(r.status == "ok" for r in first)

    # simulate an interrupted run: one has artifacts but no result.json
    partial = next(r for r in first if r.run_id.endswith("bruhs__r2"))
    (out / partial.run_id / "result.json").unlink()

    second = run_matrix([task], [CLAUDE], ["bare", "bruhs"], 2, out, parallel=2,
                        command_override=ov)
    assert runs_started(counter) == 5  # only the partial one was redone
    assert sorted(r.run_id for r in second) == sorted(r.run_id for r in first)

    meta = json.loads((out / "matrix.json").read_text())
    assert meta["bruhs_commit"] == runner.git_head(runner.BRUHS_REPO)
    assert meta["repeats"] == 2 and meta["seed"] == 0
    assert meta["models"][0]["model"] == "claude-opus-5-5"
    assert meta["cli_versions"] == {"claude": "claude 0.0-test"}
    assert len(meta["starts"]) == 2


def test_auth_failure_aborts_matrix(tmp_path):
    task = make_task(tmp_path, "t1")
    counter = tmp_path / "count"
    body = count_body(counter, f"cat <<'EOF'\n{CLAUDE_AUTH}\nEOF\nexit 1\n")
    with pytest.raises(AuthAbort):
        run_matrix([task], [CLAUDE], ["bare", "bruhs"], 3, tmp_path / "out", parallel=1,
                   command_override=override(fake_agent(tmp_path, body)))
    assert runs_started(counter) == 1


def test_setup_failed_task_excluded_both_arms(tmp_path):
    good = make_task(tmp_path, "good")
    bad = make_task(tmp_path, "bad", setup="exit 1\n")
    counter = tmp_path / "count"
    out = tmp_path / "out"
    results = run_matrix([good, bad], [CLAUDE], ["bare", "bruhs"], 1, out, parallel=2,
                         command_override=override(fake_agent(
                             tmp_path, count_body(counter, EDIT_AND_REPLY))))
    assert sorted(r.run_id for r in results) == [
        "good__claude__bare__r1", "good__claude__bruhs__r1"]
    assert runs_started(counter) == 2
    excluded = json.loads((out / "excluded.json").read_text())
    assert [e["task_id"] for e in excluded] == ["bad"]
    assert not any(p.name.startswith("bad__") for p in out.iterdir())


def test_claude_concurrency_capped(tmp_path):
    task = make_task(tmp_path, "t1")
    live = tmp_path / "live"
    live.mkdir()
    peak = tmp_path / "peak"
    body = f"""
touch {live}/$$
ls {live} | wc -l >> {peak}
sleep 0.5
rm {live}/$$
{EDIT_AND_REPLY}"""
    run_matrix([task], [CLAUDE], ["bare", "bruhs"], 3, tmp_path / "out", parallel=6,
               claude_parallel=2, command_override=override(fake_agent(tmp_path, body)))
    assert max(int(x) for x in peak.read_text().split()) <= 2


def test_work_root_inside_home_refused(tmp_path, monkeypatch):
    monkeypatch.setenv("BRUHSBENCH_WORK", str(Path.home() / "bruhsbench-work"))
    with pytest.raises(ValueError):
        runner.default_work_root(tmp_path / "out")
