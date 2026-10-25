import json
import os
import stat
import time
from pathlib import Path

import pytest

from bruhsbench import runner, sandbox
from bruhsbench.runner import AuthAbort, DiskGuard, DiskLow, matrix_order, run_matrix, run_one, scan_contamination
from bruhsbench.tasks import load_task
from bruhsbench.types import ModelSpec, RunSpec

FIXTURES = Path(__file__).parent / "fixtures" / "cli_output"
CLAUDE = ModelSpec("claude", "claude-opus-5-5", "high")
CODEX = ModelSpec("codex", "gpt-6.1-sol", "high")


# --------------------------------------------------------------------------- helpers


def make_task(root: Path, task_id: str, setup: str | None = None):
    d = root / "tasks" / task_id
    (d / "fixture").mkdir(parents=True)
    # no manifest: the bruhs arm also covers the empty-stack path (state block only)
    (d / "fixture" / "app.txt").write_text("hello\n")
    (d / "task.toml").write_text(f'id = "{task_id}"\ncategory = "feature"\n')
    (d / "prompt.md").write_text("change app.txt\n")
    if setup is not None:
        (d / "setup.sh").write_text(setup)
    return load_task(d)


def fake_agent(root: Path, body: str) -> Path:
    """A shell script standing in for the CLI. Runs with cwd = workspace."""
    (root / "side").mkdir(exist_ok=True)  # sandbox-readable (see hermetic)
    script = root / "side" / f"agent-{abs(hash(body))}.sh"
    script.write_text("#!/bin/bash\n" + body)
    script.chmod(script.stat().st_mode | stat.S_IEXEC)
    return script


def override(script: Path):
    return lambda spec, argv: ["bash", str(script)]


CLAUDE_OK = (FIXTURES / "claude.jsonl").read_text().strip()
CLAUDE_TOOL = (FIXTURES / "claude_tool.jsonl").read_text().strip()
CLAUDE_AUTH = (FIXTURES / "claude_auth_error.jsonl").read_text().strip()

EDIT_AND_REPLY = f"""
echo changed > app.txt
echo new > new.txt
printf '\\x00\\x01\\x02' > blob.bin
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
    monkeypatch.setattr(runner, "claude_auth", lambda: {})
    # fake agents still run under the real sandbox; they may also write tmp_path/side,
    # where the tests keep pid files and counters
    side = tmp_path / "side"
    side.mkdir(exist_ok=True)
    monkeypatch.setattr(runner, "wrap", lambda argv, *, writable, **kw: sandbox.wrap(
        argv, writable=[*writable, side], **kw))
    monkeypatch.setattr(runner, "cli_version", lambda cli: f"{cli} 0.0-test")
    monkeypatch.setenv("BRUHSBENCH_WORK", str(tmp_path / "work"))
    monkeypatch.setenv("BRUHSBENCH_MIN_FREE_GB", "0")  # the disk guard has its own tests


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
    assert res.turns == 1 and res.cost_usd == pytest.approx(0.0468622)
    assert res.input_tokens == 2 + 5569 + 11111 and res.output_tokens == 4
    assert res.transcript_path == d / "transcript.jsonl"
    assert res.transcript_path.read_text().strip() == CLAUDE_OK
    assert (d / "final.txt").read_text() == "ok"
    assert (d / "stderr.txt").exists()

    diff = res.diff_path.read_text()
    assert res.diff_path == d / "diff.patch"
    assert "+changed" in diff and "-hello" in diff and "new.txt" in diff
    assert "GIT binary patch" in diff  # --binary: binary changes can be re-applied

    # workspace stays in the work root (outside the results dir), path recorded
    assert res.workspace is not None and res.workspace.is_dir()
    assert not res.workspace.resolve().is_relative_to(out.resolve())
    assert res.workspace.resolve().is_relative_to((tmp_path / "work").resolve())
    assert not (d / "workspace").exists()

    saved = json.loads((d / "result.json").read_text())
    assert saved["status"] == "ok" and saved["run_id"] == spec.run_id
    assert saved["workspace"] == str(res.workspace)
    # the transcript has no tool events, so nothing could be checked
    assert saved["contaminated"] is None and saved["contamination"] == []
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


def test_grok_exit_after_background_wait_timeout_is_ok(tmp_path, bruhs_src):
    from test_agents import GROK_BG_TIMEOUT

    task = make_task(tmp_path, "t1")
    grok = ModelSpec("grok", "grok-4.7", "high")
    body = f"echo changed > app.txt\ncat <<'EOF'\n{GROK_BG_TIMEOUT}\nEOF\nexit 1\n"
    res = run_one(RunSpec(task, grok, "bare", 1), tmp_path / "out", bruhs_src=bruhs_src,
                  command_override=override(fake_agent(tmp_path, body)))
    assert res.status == "ok" and res.final_message == "All done." and res.turns == 103


def test_nonzero_exit_is_error(tmp_path, bruhs_src):
    task = make_task(tmp_path, "t1")
    res = run_one(RunSpec(task, CLAUDE, "bare", 1), tmp_path / "out", bruhs_src=bruhs_src,
                  command_override=override(fake_agent(tmp_path, "echo boom >&2; exit 3")))
    assert res.status == "error"
    assert "boom" in (tmp_path / "out" / res.run_id / "stderr.txt").read_text()


def test_timeout_recorded(tmp_path, bruhs_src):
    task = make_task(tmp_path, "t1")
    pidfile = tmp_path / "side" / "child.pid"
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


def test_allowed_paths_with_spaces_are_not_contamination():
    """A PATH dir with a space (e.g. ~/Library/Application Support/JetBrains/Toolbox/
    scripts, printed by `echo $PATH`) must not be flagged as its truncated prefix;
    a sibling under the same prefix still is."""
    home = Path("/Users/someone")
    tool = home / "Library/Application Support/JetBrains/Toolbox/scripts"
    text = (f"PATH=/usr/bin:{tool}:/bin\n{tool}/jetbrains-launcher\n"
            f"cat '{home}/Library/Application Support/Slack/cookies'\n"
            f"{home}/Library/Application Support/JetBrains/Toolbox/scripts-evil/x\n")
    found = scan_contamination(text, forbidden=[home], allowed=[tool])
    assert found == ["/Users/someone/Library/Application"]  # the Slack and -evil lines
    assert scan_contamination(f"echo {tool}", forbidden=[home], allowed=[tool]) == []
    # as it appears inside a JSON transcript: followed by an escaped newline
    assert scan_contamination(f'"output": "PATH={tool}\\n# AGENTS.md"', forbidden=[home],
                              allowed=[tool]) == []


def test_run_one_marks_contaminated(tmp_path, bruhs_src):
    task = make_task(tmp_path, "t1")
    leak = Path.home() / ".claude" / "CLAUDE.md"
    body = f"echo 'reading {leak}' >&2\n{EDIT_AND_REPLY}"
    res = run_one(RunSpec(task, CLAUDE, "bare", 1), tmp_path / "out", bruhs_src=bruhs_src,
                  command_override=override(fake_agent(tmp_path, body)))
    assert res.contaminated is True
    assert str(leak) in res.contamination


def test_sandbox_readable_tool_dirs_are_not_contamination(tmp_path, bruhs_src):
    """Tool installs the sandbox lets every run read (Playwright's browser installs, which
    agents launch through PLAYWRIGHT_BROWSERS_PATH, and that root itself) aren't the
    user's material. The rest of Playwright's cache is: the user's logged-in
    @playwright/mcp profiles (mcp-chrome-*), and a path beside the cache."""
    from bruhsbench.sandbox import PLAYWRIGHT_CACHE, read_allow

    browsers = [p for p in read_allow(Path.home()) if p.parent == Path.home() / PLAYWRIGHT_CACHE]
    if not browsers:
        pytest.skip("no Playwright browser installed")
    task = make_task(tmp_path, "t1")
    cache = Path.home() / PLAYWRIGHT_CACHE
    tool = browsers[0] / "chrome-mac" / "Chromium"
    cookies = cache / "mcp-chrome-abc123" / "Default" / "Cookies"
    leak = Path.home() / "Library" / "Caches" / "other-app"
    body = (f"echo 'PLAYWRIGHT_BROWSERS_PATH={cache} {tool} and {cookies} {leak}' >&2\n"
            f"{EDIT_AND_REPLY}")
    res = run_one(RunSpec(task, CLAUDE, "bare", 1), tmp_path / "out", bruhs_src=bruhs_src,
                  command_override=override(fake_agent(tmp_path, body)))
    assert res.contaminated is True and res.contamination == sorted([str(cookies), str(leak)])


def reply_with(transcript: str) -> str:
    return f"cat <<'EOF'\n{transcript}\nEOF\n"


def test_stream_json_tool_call_reading_real_claude_dir_flagged(tmp_path, bruhs_src):
    task = make_task(tmp_path, "t1")
    leak = Path.home() / ".claude" / "settings.json"
    transcript = CLAUDE_TOOL.replace("cat hello.txt", f"cat {leak}")
    assert str(leak) in transcript
    res = run_one(RunSpec(task, CLAUDE, "bare", 1), tmp_path / "out", bruhs_src=bruhs_src,
                  command_override=override(fake_agent(tmp_path, reply_with(transcript))))
    assert res.contaminated is True
    assert res.contamination == [str(leak)]


def test_clean_tool_transcript_not_contaminated(tmp_path, bruhs_src):
    task = make_task(tmp_path, "t1")
    res = run_one(RunSpec(task, CLAUDE, "bare", 1), tmp_path / "out", bruhs_src=bruhs_src,
                  command_override=override(fake_agent(tmp_path, reply_with(CLAUDE_TOOL))))
    assert res.contaminated is False and res.contamination == []


def test_session_log_in_run_home_scanned(tmp_path, bruhs_src):
    task = make_task(tmp_path, "t1")
    leak = Path.home() / ".agents" / "skills" / "x" / "SKILL.md"
    line = json.dumps({"type": "assistant", "message": {"content": [
        {"type": "tool_use", "name": "Read", "input": {"file_path": str(leak)}}]}})
    body = (f'mkdir -p "$HOME/.claude/projects/p"\n'
            f"cat > \"$HOME/.claude/projects/p/s.jsonl\" <<'EOF'\n{line}\nEOF\n"
            + reply_with(CLAUDE_OK))
    res = run_one(RunSpec(task, CLAUDE, "bare", 1), tmp_path / "out", bruhs_src=bruhs_src,
                  command_override=override(fake_agent(tmp_path, body)))
    assert res.contaminated is True and res.contamination == [str(leak)]


def test_clean_session_log_counts_as_tool_level(tmp_path, bruhs_src):
    task = make_task(tmp_path, "t1")
    line = '{"type":"assistant","message":{"content":[{"type":"tool_use","name":"Bash"}]}}'
    body = (f'mkdir -p "$HOME/.claude/projects/p"\n'
            f"echo '{line}' > \"$HOME/.claude/projects/p/s.jsonl\"\n" + reply_with(CLAUDE_OK))
    res = run_one(RunSpec(task, CLAUDE, "bare", 1), tmp_path / "out", bruhs_src=bruhs_src,
                  command_override=override(fake_agent(tmp_path, body)))
    assert res.contaminated is False


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


def gone(pid: int, wait_s: float = 5) -> bool:
    for _ in range(int(wait_s * 10)):
        try:
            os.kill(pid, 0)
        except ProcessLookupError:
            return True
        except PermissionError:  # zombie not yet reaped
            pass
        time.sleep(0.1)
    return False


def test_resume_skips_completed(tmp_path):
    task = make_task(tmp_path, "t1")
    out = tmp_path / "out"
    counter = tmp_path / "side" / "count"
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


def test_resume_refuses_changed_matrix(tmp_path):
    t1, t2 = make_task(tmp_path, "t1"), make_task(tmp_path, "t2")
    out = tmp_path / "out"
    ov = override(fake_agent(tmp_path, EDIT_AND_REPLY))
    run_matrix([t1], [CLAUDE], ["bare"], 1, out, command_override=ov)
    for kwargs, field in (({"repeats": 2}, "repeats"), ({"models": [CODEX]}, "models"),
                          ({"tasks": [t1, t2]}, "tasks")):
        args = {"tasks": [t1], "models": [CLAUDE], "repeats": 1, **kwargs}
        with pytest.raises(ValueError, match=field):
            run_matrix(args["tasks"], args["models"], ["bare"], args["repeats"], out,
                       command_override=ov)


def test_auth_failure_aborts_matrix(tmp_path):
    task = make_task(tmp_path, "t1")
    counter = tmp_path / "side" / "count"
    body = count_body(counter, f"cat <<'EOF'\n{CLAUDE_AUTH}\nEOF\nexit 1\n")
    with pytest.raises(AuthAbort):
        run_matrix([task], [CLAUDE], ["bare", "bruhs"], 3, tmp_path / "out", parallel=1,
                   command_override=override(fake_agent(tmp_path, body)))
    assert runs_started(counter) == 1


def test_harness_exception_recorded_and_matrix_continues(tmp_path, monkeypatch):
    good, bad = make_task(tmp_path, "good"), make_task(tmp_path, "bad")
    real_prepare = runner.prepare_workspace

    def flaky_prepare(task, arm, dest, scripts_dir=None):
        if task.id == "bad" and arm == "bruhs":
            raise RuntimeError("git exploded")
        return real_prepare(task, arm, dest, scripts_dir)

    monkeypatch.setattr(runner, "prepare_workspace", flaky_prepare)
    out = tmp_path / "out"
    results = {r.run_id: r for r in run_matrix(
        [good, bad], [CLAUDE], ["bare", "bruhs"], 1, out, parallel=1,
        command_override=override(fake_agent(tmp_path, EDIT_AND_REPLY)))}
    assert len(results) == 4
    assert results["bad__claude__bruhs__r1"].status == "error"
    saved = json.loads((out / "bad__claude__bruhs__r1" / "result.json").read_text())
    assert saved["status"] == "error" and "RuntimeError: git exploded" in saved["error"]
    assert all(r.status == "ok" for k, r in results.items() if k != "bad__claude__bruhs__r1")


def test_interrupt_kills_live_runs_and_stops_queue(tmp_path, monkeypatch):
    task = make_task(tmp_path, "t1")
    counter = tmp_path / "side" / "count"
    pidfile = tmp_path / "side" / "agent.pid"
    childfile = tmp_path / "side" / "child.pid"
    body = count_body(counter, f"sleep 60 &\necho $! > {childfile}\necho $$ > {pidfile}\nwait\n")

    def interrupted_as_completed(futures):
        for _ in range(200):  # Ctrl-C arrives while the first agent is live
            if pidfile.exists() and pidfile.read_text().strip():
                raise KeyboardInterrupt
            time.sleep(0.05)
        raise AssertionError("agent never started")
        yield

    monkeypatch.setattr(runner, "as_completed", interrupted_as_completed)
    out = tmp_path / "out"
    start = time.monotonic()
    with pytest.raises(KeyboardInterrupt):
        run_matrix([task], [CLAUDE], ["bare", "bruhs"], 3, out, parallel=1,
                   command_override=override(fake_agent(tmp_path, body)))
    assert time.monotonic() - start < 30
    # the agent and its child (same process group) are gone
    for pid in (int(pidfile.read_text()), int(childfile.read_text())):
        assert gone(pid), pid
    time.sleep(1)  # give a (wrongly) surviving worker time to start the next run
    assert runs_started(counter) == 1
    assert not list(out.glob("*/result.json"))  # the killed run is redone on resume


def test_setup_failed_task_excluded_both_arms(tmp_path):
    good = make_task(tmp_path, "good")
    bad = make_task(tmp_path, "bad", setup="exit 1\n")
    counter = tmp_path / "side" / "count"
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
    live = tmp_path / "side" / "live"
    live.mkdir()
    peak = tmp_path / "side" / "peak"
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


# --------------------------------------------------------------------------- disk guard


def test_disk_guard_refuses_at_once_with_nothing_running():
    slept = []
    guard = DiskGuard([Path("/")], min_gb=40, free_fn=lambda p: 10.0, sleep=slept.append)
    with pytest.raises(DiskLow, match="10.0 GB free.*BRUHSBENCH_MIN_FREE_GB"):
        guard.wait("run x")
    assert slept == []
    assert DiskGuard([Path("/")], min_gb=40, free_fn=lambda p: 50.0).wait("x") == 50.0


def test_disk_guard_waits_for_other_jobs_then_proceeds_or_gives_up():
    import threading

    free = {"gb": 10.0}
    held, release = threading.Event(), threading.Event()

    def other_job(guard):
        with guard.job():
            held.set()
            release.wait(10)

    def frees_up(_s):
        free["gb"] = 45.0  # the other run's cleanup freed space

    guard = DiskGuard([Path("/")], min_gb=40, free_fn=lambda p: free["gb"], poll_s=1,
                      wait_s=5, sleep=frees_up)
    t = threading.Thread(target=other_job, args=(guard,))
    t.start()
    held.wait(10)
    try:
        with guard.job():  # the caller's own job doesn't count as "others"
            assert guard.wait("run x") == 45.0
        free["gb"] = 10.0
        slept = []
        guard._sleep = slept.append
        with pytest.raises(DiskLow):
            guard.wait("run y")
        assert slept == [1, 1, 1, 1, 1]  # polled up to wait_s, then gave up
    finally:
        release.set()
        t.join()


def test_min_free_gb_from_env(monkeypatch):
    monkeypatch.delenv("BRUHSBENCH_MIN_FREE_GB")
    assert runner.min_free_gb() == 10  # ruling R36
    monkeypatch.setenv("BRUHSBENCH_MIN_FREE_GB", "12.5")
    assert runner.min_free_gb() == 12.5
    monkeypatch.setenv("BRUHSBENCH_MIN_FREE_GB", "lots")
    with pytest.raises(ValueError, match="BRUHSBENCH_MIN_FREE_GB"):
        runner.min_free_gb()


def test_run_records_free_gb_at_start(tmp_path, bruhs_src, monkeypatch):
    monkeypatch.setattr(runner, "free_gb", lambda p: 123.456)
    spec = RunSpec(make_task(tmp_path, "t1"), CLAUDE, "bare", 1)
    res = run_one(spec, tmp_path / "out", bruhs_src=bruhs_src,
                  command_override=override(fake_agent(tmp_path, EDIT_AND_REPLY)))
    assert res.free_gb_at_start == 123.5
    saved = json.loads((tmp_path / "out" / spec.run_id / "result.json").read_text())
    assert saved["free_gb_at_start"] == 123.5 and saved["workspace_deleted"] is False


def test_matrix_refuses_to_start_on_low_disk(tmp_path):
    counter = tmp_path / "side" / "count"
    guard = DiskGuard([tmp_path], min_gb=40, free_fn=lambda p: 5.0)
    with pytest.raises(DiskLow):
        run_matrix([make_task(tmp_path, "t1")], [CLAUDE], ["bare", "bruhs"], 1,
                   tmp_path / "out", disk_guard=guard, command_override=override(
                       fake_agent(tmp_path, count_body(counter, EDIT_AND_REPLY))))
    assert runs_started(counter) == 0


def test_low_disk_stops_matrix_cleanly_and_resumes(tmp_path):
    task = make_task(tmp_path, "t1")
    out = tmp_path / "out"
    counter = tmp_path / "side" / "count"
    ov = override(fake_agent(tmp_path, count_body(counter, EDIT_AND_REPLY)))
    # space runs out once two runs have started
    guard = DiskGuard([tmp_path], min_gb=40,
                      free_fn=lambda p: 5.0 if runs_started(counter) >= 2 else 50.0)
    with pytest.raises(DiskLow):
        run_matrix([task], [CLAUDE], ["bare", "bruhs"], 2, out, parallel=1,
                   disk_guard=guard, command_override=ov)
    assert runs_started(counter) == 2
    done = sorted(p.parent.name for p in out.glob("*/result.json"))
    assert len(done) == 2
    assert not any((out / p).exists() for p in ("t1__claude__bare__r2",
                                                "t1__claude__bruhs__r2")
                   if p not in done)  # nothing half-started

    results = run_matrix([task], [CLAUDE], ["bare", "bruhs"], 2, out, parallel=1,
                         disk_guard=DiskGuard([tmp_path], min_gb=40,
                                              free_fn=lambda p: 50.0),
                         command_override=ov)
    assert runs_started(counter) == 4 and len(results) == 4
    assert all(r.free_gb_at_start == 50.0 for r in results if r.run_id not in done)


def test_low_disk_lets_live_runs_finish(tmp_path):
    task = make_task(tmp_path, "t1")
    out = tmp_path / "out"
    counter = tmp_path / "side" / "count"
    # the first run to start is slow; the other worker finds the disk full meanwhile
    body = count_body(counter, f'[ "$(wc -l < {counter})" -eq 1 ] && sleep 2\n'
                               f"{EDIT_AND_REPLY}")
    guard = DiskGuard([tmp_path], min_gb=40, poll_s=0.1, wait_s=0.5,
                      free_fn=lambda p: 5.0 if runs_started(counter) >= 2 else 50.0)
    with pytest.raises(DiskLow):
        run_matrix([task], [CLAUDE], ["bare", "bruhs"], 2, out, parallel=2,
                   disk_guard=guard, command_override=override(fake_agent(tmp_path, body)))
    results = [runner.load_result(p) for p in out.glob("*/result.json")]
    assert runs_started(counter) == 2
    assert len(results) == 2 and all(r.status == "ok" for r in results)


# --------------------------------------------------------------------------- post-run + cleanup


def test_post_run_follows_each_run_and_resumes(tmp_path):
    task = make_task(tmp_path, "t1")
    out = tmp_path / "out"
    seen = []

    def post(spec, res):
        assert (out / spec.run_id / "result.json").is_file()
        seen.append(res.run_id)

    ov = override(fake_agent(tmp_path, EDIT_AND_REPLY))
    run_matrix([task], [CLAUDE], ["bare", "bruhs"], 1, out, post_run=post,
               command_override=ov)
    assert sorted(seen) == ["t1__claude__bare__r1", "t1__claude__bruhs__r1"]
    seen.clear()
    run_matrix([task], [CLAUDE], ["bare", "bruhs"], 1, out, post_run=post,
               command_override=ov)  # resume: finished runs still get post-processed
    assert sorted(seen) == ["t1__claude__bare__r1", "t1__claude__bruhs__r1"]


def test_post_run_disk_low_stops_new_runs(tmp_path):
    task = make_task(tmp_path, "t1")
    counter = tmp_path / "side" / "count"

    def post(spec, res):
        raise DiskLow("full before grading")

    with pytest.raises(DiskLow, match="before grading"):
        run_matrix([task], [CLAUDE], ["bare", "bruhs"], 2, tmp_path / "out", parallel=1,
                   post_run=post, command_override=override(
                       fake_agent(tmp_path, count_body(counter, EDIT_AND_REPLY))))
    assert runs_started(counter) == 1


def _planted_run(tmp_path, bruhs_src):
    """A finished run whose workspace holds symlinks to a precious dir outside."""
    precious = tmp_path / "precious"
    (precious / "sub").mkdir(parents=True)
    (precious / "keep.txt").write_text("keep")
    (precious / "sub" / "deep.txt").write_text("keep")
    body = f"ln -s {precious} link_dir\nln -s {precious}/keep.txt link_file\n" \
           f"mkdir -p ro/x && chmod 555 ro/x ro\n{EDIT_AND_REPLY}"
    out = tmp_path / "out"
    spec = RunSpec(make_task(tmp_path, "t1"), CLAUDE, "bare", 1)
    res = run_one(spec, out, bruhs_src=bruhs_src,
                  command_override=override(fake_agent(tmp_path, body)))
    assert (res.workspace / "link_dir").is_symlink()
    return out, spec, res, precious


def test_cleanup_run_never_follows_planted_symlinks(tmp_path, bruhs_src):
    out, spec, res, precious = _planted_run(tmp_path, bruhs_src)
    work_root = res.workspace.parent.parent
    assert runner.cleanup_run(out, work_root, spec.run_id) == []
    assert not os.path.lexists(work_root / spec.run_id)
    assert (precious / "keep.txt").read_text() == "keep"
    assert (precious / "sub" / "deep.txt").read_text() == "keep"
    saved = runner.load_result(out / spec.run_id / "result.json")
    assert saved.workspace_deleted is True
    # the artifacts the judges need stay
    assert {"result.json", "diff.patch", "final.txt", "transcript.jsonl"} <= {
        p.name for p in (out / spec.run_id).iterdir()}
    assert runner.cleanup_run(out, work_root, spec.run_id) == []  # idempotent


def test_cleanup_refuses_paths_outside_the_work_root(tmp_path, bruhs_src, monkeypatch):
    work = tmp_path / "work" / "w"
    (work / "run").mkdir(parents=True)
    for name in ("..", "a/b", "", "."):
        with pytest.raises(ValueError):
            runner.remove_work_dir(work, name)
    # a work root overlapping the repo (bench/results, bench/tasks) or the results dir
    for bad in (runner.BRUHS_REPO / "bench", runner.BRUHS_REPO / "bench" / "results",
                Path("/")):
        with pytest.raises(ValueError, match="refusing"):
            runner.remove_work_dir(bad, "x")
        with pytest.raises(ValueError, match="refusing"):
            runner.remove_work_root(bad)
    with pytest.raises(ValueError, match="refusing"):
        runner.remove_work_dir(work, "run", protect=[work / "run" / "results"])
    # a symlinked work root resolves to its target, which is checked
    link = tmp_path / "link"
    link.symlink_to(runner.BRUHS_REPO / "bench")
    with pytest.raises(ValueError, match="refusing"):
        runner.remove_work_root(link)
    assert (work / "run").is_dir()


def test_remove_work_root_removes_everything_inside_only(tmp_path, bruhs_src):
    out, spec, res, precious = _planted_run(tmp_path, bruhs_src)
    work_root = res.workspace.parent.parent
    (work_root / "_scratch" / "grade-x").mkdir(parents=True)
    assert runner.remove_work_root(work_root, protect=[out])
    assert not work_root.exists() and work_root.parent.is_dir()
    assert (precious / "keep.txt").exists() and (precious / "sub" / "deep.txt").exists()
    assert (out / spec.run_id / "result.json").is_file()
    assert not runner.remove_work_root(work_root)


def test_cleanup_clears_immutable_flags(tmp_path, bruhs_src):
    body = f"mkdir -p locked && echo x > locked/f && chflags uchg locked/f locked\n" \
           f"{EDIT_AND_REPLY}"
    out = tmp_path / "out"
    spec = RunSpec(make_task(tmp_path, "t1"), CLAUDE, "bare", 1)
    res = run_one(spec, out, bruhs_src=bruhs_src,
                  command_override=override(fake_agent(tmp_path, body)))
    assert os.stat(res.workspace / "locked" / "f").st_flags & stat.UF_IMMUTABLE
    work_root = res.workspace.parent.parent
    assert runner.cleanup_run(out, work_root, spec.run_id) == []
    assert not os.path.lexists(work_root / spec.run_id)


def test_cleanup_reports_leftovers(tmp_path, monkeypatch):
    work = tmp_path / "work" / "w"
    (work / "r1" / "sub").mkdir(parents=True)
    (work / "r1" / "sub" / "f").write_text("x")
    real_unlink = os.unlink

    def stuck(name, *a, **k):
        if name == "f":
            raise PermissionError(1, "Operation not permitted")
        return real_unlink(name, *a, **k)

    monkeypatch.setattr(os, "unlink", stuck)
    left = runner.cleanup_run(tmp_path / "out", work, "r1")
    assert str(work.resolve() / "r1" / "sub" / "f") in left


def test_active_lock_held_during_matrix(tmp_path):
    task = make_task(tmp_path, "t1")
    out = tmp_path / "out"
    seen = []

    def post(spec, res):
        seen.append(runner.work_root_active(runner.default_work_root(out)))

    run_matrix([task], [CLAUDE], ["bare"], 1, out, post_run=post,
               command_override=override(fake_agent(tmp_path, EDIT_AND_REPLY)))
    assert seen == [True]
    assert not runner.work_root_active(runner.default_work_root(out))


def test_unflag_never_goes_through_a_swapped_symlink(tmp_path, monkeypatch):
    from bruhsbench import untrusted

    real_chflags = os.chflags
    outside = tmp_path / "outside"
    outside.mkdir()
    (outside / "f").write_text("x")
    real_chflags(outside / "f", stat.UF_IMMUTABLE)
    a = tmp_path / "tree" / "a"
    a.mkdir(parents=True)
    (a / "f").write_text("y")
    (a / "link").symlink_to(outside / "f")
    real_chflags(a / "f", stat.UF_IMMUTABLE)

    def no_path_chflags(*args, **kwargs):
        raise AssertionError("path-based chflags used")

    monkeypatch.setattr(os, "chflags", no_path_chflags)
    dfd = os.open(a, os.O_RDONLY | os.O_DIRECTORY)
    try:
        # the agent swaps the dir we hold an fd on for a symlink to an outside dir
        a.rename(tmp_path / "tree" / "a-old")
        a.symlink_to(outside)
        untrusted._unflag(dfd, "f")
        untrusted._unflag(dfd, "link")  # a symlink entry: its target is never touched
    finally:
        os.close(dfd)
        monkeypatch.undo()
    try:
        assert os.stat(outside / "f").st_flags & stat.UF_IMMUTABLE
        assert not os.stat(tmp_path / "tree" / "a-old" / "f").st_flags & stat.UF_IMMUTABLE
    finally:
        real_chflags(outside / "f", 0)


def test_unflag_handles_an_unreadable_immutable_file(tmp_path):
    from bruhsbench import untrusted

    d = tmp_path / "d"
    d.mkdir()
    (d / "f").write_text("x")
    os.chmod(d / "f", 0)
    os.chflags(d / "f", stat.UF_IMMUTABLE)
    try:
        untrusted.remove(tmp_path, "d")
        assert not d.exists()
    finally:
        if (d / "f").exists():
            os.chflags(d / "f", 0)


# --------------------------------------------------------------------------- R37: TMPDIR

SOCKET_BODY = """
python3 - <<'PY' > "$(dirname "$0")/sock-$$.txt"
import os, socket
path = os.path.join(os.environ["TMPDIR"], "convex-local-backend.sock")
s = socket.socket(socket.AF_UNIX)
s.bind(path)
print(os.environ["TMPDIR"])
PY
""" + EDIT_AND_REPLY


def test_long_results_dir_gets_a_short_tmpdir_with_room_for_a_socket(tmp_path, bruhs_src):
    """A 40-character results dir name and a long run id: TMPDIR stays short enough for
    a unix socket (Convex's local backend binds one under it)."""
    out = tmp_path / ("r" * 40)
    spec = RunSpec(make_task(tmp_path, "a-rather-long-task-name-for-tmpdirs"), CLAUDE,
                   "bruhs", 3)
    res = run_one(spec, out, bruhs_src=bruhs_src,
                  command_override=override(fake_agent(tmp_path, SOCKET_BODY)))
    assert res.status == "ok"
    run_dir = res.workspace.parent
    [seen] = [p.read_text().strip() for p in (tmp_path / "side").glob("sock-*.txt")]
    assert seen == str(sandbox.tmp_dir(run_dir))
    assert len(str(run_dir / ".tmp")) > sandbox.MAX_TMPDIR_LEN  # the old layout didn't fit
    # deleting the run deletes its TMPDIR too
    assert runner.cleanup_run(out, run_dir.parent, spec.run_id) == []
    assert not os.path.lexists(seen)


def test_default_tmpdir_fits_whatever_the_results_name(monkeypatch, tmp_path):
    monkeypatch.delenv("BRUHSBENCH_TMP")
    work_root = runner.default_work_root(tmp_path / ("x" * 40))
    tmp = sandbox.tmp_dir(work_root / ("t" * 60 + "__claude__bruhs__r3"))
    assert tmp.parent == Path("/private/tmp/bb") and len(str(tmp)) <= sandbox.MAX_TMPDIR_LEN
    sandbox.check_tmp_base()


def test_matrix_fails_fast_on_a_too_long_tmp_base(tmp_path, monkeypatch):
    monkeypatch.setenv("BRUHSBENCH_TMP", "/private/tmp/" + "x" * 70)
    out = tmp_path / "out"
    with pytest.raises(sandbox.TmpDirTooLong, match="77"):
        run_matrix([make_task(tmp_path, "t1")], [CLAUDE], ["bare"], 1, out,
                   command_override=lambda spec, argv: ["true"])
    assert not (out / "matrix.json").exists()


def test_rerun_starts_with_a_fresh_tmpdir(tmp_path, bruhs_src):
    spec = RunSpec(make_task(tmp_path, "t1"), CLAUDE, "bare", 1)
    run_dir = tmp_path / "work" / runner.results_id(tmp_path / "out") / spec.run_id
    stale = sandbox.tmp_dir(run_dir)
    stale.mkdir(parents=True)
    (stale / "left-over").write_text("x")
    run_one(spec, tmp_path / "out", bruhs_src=bruhs_src,
            command_override=override(fake_agent(tmp_path, EDIT_AND_REPLY)))
    assert not (stale / "left-over").exists()


def test_remove_work_root_removes_run_tmpdirs(tmp_path, bruhs_src):
    out = tmp_path / "out"
    spec = RunSpec(make_task(tmp_path, "t1"), CLAUDE, "bare", 1)
    res = run_one(spec, out, bruhs_src=bruhs_src,
                  command_override=override(fake_agent(tmp_path, EDIT_AND_REPLY)))
    work_root = res.workspace.parent.parent
    scratch = work_root / "_scratch" / "grade-x"
    scratch.mkdir(parents=True)
    sandbox.private_tmp({}, scratch)
    tmps = [sandbox.tmp_dir(res.workspace.parent), sandbox.tmp_dir(scratch)]
    assert all(t.is_dir() for t in tmps)
    assert runner.remove_work_root(work_root, protect=[out])
    assert not any(os.path.lexists(t) for t in tmps)


def test_matrix_json_pins_task_hashes_and_records_each_start(tmp_path):
    task = make_task(tmp_path, "t1")
    out = tmp_path / "out"
    ov = override(fake_agent(tmp_path, EDIT_AND_REPLY))
    run_matrix([task], [CLAUDE], ["bare"], 1, out, command_override=ov,
               record={"task_hashes": {"t1": "h1"}, "unfrozen": {}, "allow_unfrozen": False})
    meta = json.loads((out / "matrix.json").read_text())
    assert meta["task_hashes"] == {"t1": "h1"} and "allow_unfrozen" not in meta
    assert runner.pinned_task_hashes(out) == {"t1": "h1"}
    run_matrix([task], [CLAUDE], ["bare"], 1, out, command_override=ov,
               record={"task_hashes": {"t1": "h1"}, "unfrozen": {"t1": "not frozen"},
                       "allow_unfrozen": True})
    run_matrix([task], [CLAUDE], ["bare"], 1, out, command_override=ov)
    meta = json.loads((out / "matrix.json").read_text())
    assert [s.get("task_hashes") for s in meta["starts"]] == [{"t1": "h1"}, {"t1": "h1"}, None]
    assert meta["allow_unfrozen"] is True  # sticky once any start overrode the freeze


def test_resume_refuses_a_task_that_changed_since_the_first_start(tmp_path):
    task = make_task(tmp_path, "t1")
    out = tmp_path / "out"
    ov = override(fake_agent(tmp_path, EDIT_AND_REPLY))
    run_matrix([task], [CLAUDE], ["bare"], 1, out, command_override=ov,
               record={"task_hashes": {"t1": "h1"}})
    with pytest.raises(runner.MatrixMismatch, match=r"\['t1'\] changed"):
        run_matrix([task], [CLAUDE], ["bare"], 1, out, command_override=ov,
                   record={"task_hashes": {"t1": "h2"}})
    assert len(json.loads((out / "matrix.json").read_text())["starts"]) == 1


def test_matrix_without_pins_is_pinned_by_its_next_start(tmp_path):
    task = make_task(tmp_path, "t1")
    out = tmp_path / "out"
    ov = override(fake_agent(tmp_path, EDIT_AND_REPLY))
    run_matrix([task], [CLAUDE], ["bare"], 1, out, command_override=ov)
    assert runner.pinned_task_hashes(out) is None
    run_matrix([task], [CLAUDE], ["bare"], 1, out, command_override=ov,
               record={"task_hashes": {"t1": "h1"}})
    assert runner.pinned_task_hashes(out) == {"t1": "h1"}
