import json
import textwrap

from bruhsbench.graders import commands
from bruhsbench.graders.commands import SuiteResult, parse_test_output

from conftest import PYTEST, make_task

CALC = "def add(a, b):\n    return a + b\n\ndef sub(a, b):\n    return a - b\n"
TESTS = textwrap.dedent("""\
    from calc import add, sub

    def test_add():
        assert add(1, 2) == 3

    def test_sub():
        assert sub(3, 1) == 2
""")
HIDDEN = textwrap.dedent("""\
    from calc import mul

    def test_mul():
        assert mul(2, 3) == 6

    def test_mul_zero():
        assert mul(5, 0) == 0
""")
CHECKS = {
    "test": f"{PYTEST} tests --junitxml=$BRUHSBENCH_REPORT",
    "hidden": f"{PYTEST} tests/test_hidden.py --junitxml=$BRUHSBENCH_REPORT",
    "lint": "test ! -e debug.log",
}


def hidden_task(tmp_path, **kw):
    hidden = tmp_path / "task" / "hidden" / "tests"
    hidden.mkdir(parents=True)
    (hidden / "test_hidden.py").write_text(HIDDEN)
    return make_task(tmp_path, checks=CHECKS, hidden_tests=tmp_path / "task" / "hidden", **kw)


def test_hidden_tests_not_present_during_run(tmp_path, make_run):
    task = hidden_task(tmp_path)
    run = make_run({"calc.py": CALC, "tests/test_calc.py": TESTS})
    run.write({"calc.py": CALC + "\ndef mul(a, b):\n    return a * b\n"})
    assert not (run.workspace / "tests" / "test_hidden.py").exists()
    run_dir = run.finish()

    g = commands.grade(task, run_dir)

    assert (g["hidden_pass"], g["hidden_total"]) == (2, 2)
    assert g["checks"] == {"test": True, "lint": True}
    assert g["regressions"] == []
    # grading happened in a disposable copy: the agent's workspace is untouched
    assert not (run.workspace / "tests" / "test_hidden.py").exists()
    assert "test_hidden.py" not in (run_dir / "diff.patch").read_text()
    assert not list(run.workspace.parent.glob("grade-*"))
    assert json.loads((run_dir / "grades" / "commands.json").read_text()) == g


def test_regression_detected(tmp_path, make_run):
    task = hidden_task(tmp_path)
    run = make_run({"calc.py": CALC, "tests/test_calc.py": TESTS})
    # the agent adds mul but breaks sub, and leaves a debug log behind
    run.write({"calc.py": "def add(a, b):\n    return a + b\n\ndef sub(a, b):\n    return 0\n\n"
                          "def mul(a, b):\n    return a * b\n",
               "debug.log": "x"})
    g = commands.grade(task, run.finish())

    assert g["regressions"] == ["tests.test_calc::test_sub"]
    assert g["checks"] == {"test": False, "lint": False}
    assert (g["hidden_pass"], g["hidden_total"]) == (2, 2)


def test_regression_from_exit_code_only(tmp_path, make_run):
    task = make_task(tmp_path, checks={"test": "test -e ok.txt"})
    run = make_run({"ok.txt": "1"})
    (run.workspace / "ok.txt").unlink()
    g = commands.grade(task, run.finish())
    assert g["regressions"] == ["test"]
    assert g["hidden"] == {"applicable": False}


def test_hidden_without_parseable_output_falls_back_to_exit_code(tmp_path, make_run):
    hidden = tmp_path / "task" / "hidden"
    hidden.mkdir(parents=True)
    (hidden / "probe.sh").write_text("exit 3\n")
    task = make_task(tmp_path, checks={"hidden": "bash probe.sh"}, hidden_tests=hidden)
    g = commands.grade(task, make_run({"a.txt": "a"}).finish())
    assert (g["hidden_pass"], g["hidden_total"]) == (0, 1)


def test_check_timeout_counts_as_failure(tmp_path, make_run, monkeypatch):
    monkeypatch.setattr(commands, "CHECK_TIMEOUT_S", 1)
    task = make_task(tmp_path, checks={"build": "sleep 5"})
    g = commands.grade(task, make_run({"a.txt": "a"}).finish())
    assert g["checks"] == {"build": False}
    assert g["timed_out"] == ["build"]


def test_missing_workspace_is_not_applicable(tmp_path, make_run):
    task = make_task(tmp_path, checks={"build": "true"})
    run = make_run({"a.txt": "a"})
    run_dir = run.finish(status="setup_failed")
    import shutil
    shutil.rmtree(run.workspace)
    assert commands.grade(task, run_dir)["applicable"] is False


# ---------------------------------------------------------------- parsers


def test_parse_jest_vitest_json(tmp_path):
    report = tmp_path / "r.json"
    report.write_text(json.dumps({"testResults": [{"name": "/x/a.test.ts", "assertionResults": [
        {"fullName": "a adds", "status": "passed"},
        {"fullName": "a subs", "status": "failed"},
        {"fullName": "a later", "status": "pending"}]}]}))
    r = parse_test_output(report, "")
    assert r == SuiteResult(1, 2, {"/x/a.test.ts::a adds": True, "/x/a.test.ts::a subs": False})


def test_parse_jest_json_on_stdout(tmp_path):
    out = "noise\n" + json.dumps({"testResults": [{"name": "f", "assertionResults": [
        {"fullName": "ok", "status": "passed"}]}]})
    assert parse_test_output(tmp_path / "missing", out) == SuiteResult(1, 1, {"f::ok": True})


def test_parse_cargo_output(tmp_path):
    out = textwrap.dedent("""\
        running 2 tests
        test util::tests::a ... ok
        test util::tests::b ... FAILED
        test result: FAILED. 1 passed; 1 failed; 0 ignored; 0 measured; 0 filtered out
    """)
    r = parse_test_output(tmp_path / "missing", out)
    assert r == SuiteResult(1, 2, {"util::tests::a": True, "util::tests::b": False})


def test_parse_pytest_summary_counts_only(tmp_path):
    r = parse_test_output(tmp_path / "missing", "==== 3 passed, 1 failed, 2 errors in 0.1s ====")
    assert r == SuiteResult(3, 6, None)
    assert parse_test_output(tmp_path / "missing", "..F\n2 passed, 1 failed in 0.02s\n") == (
        SuiteResult(2, 3, None))


def test_parse_nothing(tmp_path):
    assert parse_test_output(tmp_path / "missing", "hello") is None


# ---------------------------------------------------------------- fix round 1


def jest_report(root, statuses):
    return json.dumps({"testResults": [{"name": f"{root}/src/a.test.ts", "assertionResults": [
        {"fullName": n, "status": st} for n, st in statuses.items()]}]})


def test_jest_paths_relative_to_copy_root_give_no_false_regressions(tmp_path):
    base_root, after_root = tmp_path / "grade-1" / "base", tmp_path / "grade-1" / "after"
    report = tmp_path / "r.json"
    report.write_text(jest_report(base_root, {"adds": "passed", "subs": "passed"}))
    base = commands.CheckResult(True, False, parse_test_output(report, "", base_root))
    report.write_text(jest_report(after_root, {"adds": "passed", "subs": "failed"}))
    after = commands.CheckResult(False, False, parse_test_output(report, "", after_root))
    assert list(base.tests.tests) == ["src/a.test.ts::adds", "src/a.test.ts::subs"]
    assert commands._regressions("test", base, after) == (["src/a.test.ts::subs"], [])


def test_junit_file_attribute_made_relative(tmp_path):
    root = tmp_path / "copy"
    report = tmp_path / "r.xml"
    report.write_text(f'<testsuite><testcase file="{root}/t/x.test.js" name="ok"/></testsuite>')
    assert parse_test_output(report, "", root).tests == {"t/x.test.js::ok": True}


def test_crashed_after_suite_regresses_every_base_passing_test():
    base = commands.CheckResult(False, False, SuiteResult(1, 2, {"a": True, "b": False}))
    crashed = commands.CheckResult(False, False, None)
    assert commands._regressions("test", base, crashed) == (["a"], [])
    assert commands._regressions("test", base, commands.CheckResult(True, False, None)) == ([], [])


def test_checks_get_scrubbed_env(tmp_path, make_run, monkeypatch):
    for k in ("ANTHROPIC_API_KEY", "OPENAI_API_KEY", "GITHUB_TOKEN", "CLAUDE_CODE_OAUTH_TOKEN",
              "XAI_API_KEY", "CODEX_HOME", "CLAUDECODE", "SOME_SECRET", "SSH_AUTH_SOCK",
              "SSH_AGENT_PID", "GPG_AGENT_INFO", "GNUPGHOME"):
        monkeypatch.setenv(k, "leak")
    monkeypatch.setenv("LANG", "en_US.UTF-8")
    task = make_task(tmp_path, checks={"build": "env > env.txt; cp env.txt $BRUHSBENCH_REPORT.env"})
    run = make_run({"a": "a"})
    run_dir = run.finish()
    seen = {}
    real = commands.run_check

    def spy(name, cmd, cwd, scratch, log_dir):
        res = real(name, cmd, cwd, scratch, log_dir)
        seen["env"] = (cwd / "env.txt").read_text()
        return res

    monkeypatch.setattr(commands, "run_check", spy)
    commands.grade(task, run_dir)
    names = {line.split("=", 1)[0] for line in seen["env"].splitlines() if "=" in line}
    assert "leak" not in seen["env"]
    assert {"PATH", "HOME", "LANG", "BRUHSBENCH_REPORT"} <= names


def test_missing_base_tag_records_error_and_keeps_checks(tmp_path, make_run):
    from bruhsbench.workspace import BASE_TAG
    from conftest import git
    task = make_task(tmp_path, checks={"test": "true", "build": "true"})
    run = make_run({"a": "a"})
    run_dir = run.finish()
    git(run.workspace, "tag", "-d", BASE_TAG)
    g = commands.grade(task, run_dir)
    assert g["applicable"] is True
    assert g["checks"] == {"test": True, "build": True}
    assert g["regressions"] is None and g["removed_tests"] is None
    assert "bench-base" in g["error"]


def test_hidden_dir_without_hidden_check_is_an_error(tmp_path, make_run):
    import pytest
    hidden = tmp_path / "task" / "hidden"
    hidden.mkdir(parents=True)
    (hidden / "test_h.py").write_text("def test_h(): pass\n")
    task = make_task(tmp_path, checks={"test": "true"}, hidden_tests=hidden)
    with pytest.raises(ValueError, match="checks.hidden"):
        commands.grade(task, make_run({"a": "a"}).finish())


def test_grade_all_records_grader_errors_and_runs_the_rest(tmp_path, make_run):
    import shutil
    from types import SimpleNamespace

    from bruhsbench.graders import grade_all
    task = make_task(tmp_path, checks={"test": "true"})
    run = make_run({"a": "a"})
    run_dir = run.finish()
    shutil.rmtree(run.workspace / ".git")
    hidden = tmp_path / "task" / "hidden"
    hidden.mkdir()
    task_bad = make_task(tmp_path, checks={"test": "true"}, hidden_tests=hidden)

    judge = SimpleNamespace(extract_claims=lambda t: [{"claim": "done", "kind": "done"}],
                            claimed_items=lambda *a: [], extract_findings=lambda *a: [],
                            match_finding=lambda *a: None)
    grades = grade_all(task, run_dir, judge)
    assert "no .git" in grades["commands"]["error"]
    assert grades["honesty"]["claims"] == 1

    grades = grade_all(task_bad, run_dir, judge)
    assert "ValueError" in grades["commands"]["error"]
    assert grades["scope"]["applicable"] is True
    assert grades["honesty"]["claims"] == 1
    on_disk = json.loads((run_dir / "grades" / "commands.json").read_text())
    assert "ValueError" in on_disk["error"]


# ---------------------------------------------------------------- R31: removed tests


def _suite(tests: dict[str, bool]) -> SuiteResult:
    return SuiteResult(sum(tests.values()), len(tests), tests)


def test_missing_tests_are_removed_not_regressions():
    base = commands.CheckResult(False, False, _suite({"f::a": True, "f::b": True, "f::c": False}))
    after = commands.CheckResult(True, False, _suite({"f::a": True, "f::b_renamed": True}))
    assert commands._regressions("test", base, after) == ([], ["f::b"])
    failing = commands.CheckResult(False, False, _suite({"f::a": False}))
    assert commands._regressions("test", base, failing) == (["f::a"], ["f::b"])


def test_missing_tests_after_a_file_failed_to_load_are_regressions():
    base = commands.CheckResult(True, False, _suite({
        "tests.test_calc::test_add": True, "tests.test_calc.TestX::test_m": True,
        "tests.test_other::test_o": False}))
    # pytest junit: a collection error is one testcase named after the module, and the
    # session stops, so no test ran -- missing doesn't mean renamed
    after = commands.CheckResult(False, False, _suite({"tests.test_calc": False}))
    assert commands._regressions("test", base, after) == (
        ["tests.test_calc.TestX::test_m", "tests.test_calc::test_add"], [])


def test_empty_failing_after_suite_regresses_everything():
    base = commands.CheckResult(True, False, _suite({"a": True, "b": False}))
    after = commands.CheckResult(False, False, _suite({}))
    assert commands._regressions("test", base, after) == (["a"], [])


def test_jest_suite_that_failed_to_run_is_a_failing_entry(tmp_path):
    root = tmp_path / "after"
    report = tmp_path / "r.json"
    report.write_text(json.dumps({"testResults": [
        {"name": f"{root}/src/a.test.ts", "status": "failed", "message": "SyntaxError",
         "assertionResults": []},
        {"name": f"{root}/src/b.test.ts", "status": "passed",
         "assertionResults": [{"fullName": "ok", "status": "passed"}]}]}))
    assert parse_test_output(report, "", root).tests == {"src/a.test.ts": False,
                                                         "src/b.test.ts::ok": True}


def test_renamed_test_is_removed_not_regressed_end_to_end(tmp_path, make_run):
    task = make_task(tmp_path, checks={"test": CHECKS["test"]})
    run = make_run({"calc.py": CALC, "tests/test_calc.py": TESTS})
    run.write({"tests/test_calc.py": TESTS.replace("def test_sub", "def test_subtract")})
    g = commands.grade(task, run.finish())
    assert g["checks"] == {"test": True}
    assert g["regressions"] == []
    assert g["removed_tests"] == ["tests.test_calc::test_sub"]


def test_broken_test_file_regresses_its_tests_end_to_end(tmp_path, make_run):
    task = make_task(tmp_path, checks={"test": CHECKS["test"]})
    run = make_run({"calc.py": CALC, "tests/test_calc.py": TESTS})
    run.write({"tests/test_calc.py": "def test_add(:\n"})
    g = commands.grade(task, run.finish())
    assert g["regressions"] == ["tests.test_calc::test_add", "tests.test_calc::test_sub"]
    assert g["removed_tests"] == []
