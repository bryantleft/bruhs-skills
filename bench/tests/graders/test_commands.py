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
