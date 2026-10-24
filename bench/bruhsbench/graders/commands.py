"""Run the task's checks against the agent's final state (Ruling R16).

Everything runs in disposable copies of the workspace (APFS clone via ``cp -cR``, else
``copytree``) in a scratch dir under ``<work_root>/_scratch`` (outside every run root),
never in the agent's workspace:

* agent copy: every check except ``hidden`` (build, typecheck, lint, test, ...) -> bool by
  exit code; then the task's ``hidden/`` contents are copied in at the same relative
  paths and ``checks["hidden"]`` runs -> pass/total (hidden/ without checks.hidden is
  a task error).
* base copy (reset to ``bench-base``): ``checks["test"]`` again; a test passing at base
  and not passing after is a regression.

Per-test results come from a report file or stdout. Each command gets
``$BRUHSBENCH_REPORT`` (a path in a scratch dir) to point its reporter at, e.g.
``pytest --junitxml=$BRUHSBENCH_REPORT`` or
``vitest run --reporter=json --outputFile=$BRUHSBENCH_REPORT``. Recognised: jest/vitest
JSON (file or stdout), JUnit XML (file), cargo test lines (stdout), and a pytest summary
line (counts only). With nothing parseable the exit code decides: 1/1 or 0/1, and a
regression is reported under the check's name when base passed and after failed; when
only the base run names tests and the agent's run fails, every base-passing test counts.

If bench-base can't be restored (no .git / no tag) ``regressions`` is None and ``error``
says why; the other checks still run. Checks get the harness environment minus
credentials and agent-CLI configuration, with ``HOME`` in the scratch dir
(:func:`sandboxed_env`) and ``TMPDIR`` in it, under the OS sandbox (``sandbox.wrap``):
agent-written code can't touch the real home or any run root and writes only inside the
scratch dir. Git on the copies, the report file and the hidden-test overlay go through
``untrusted`` (R22).
"""

from __future__ import annotations

import json
import os
import re
import shutil
import signal
import subprocess
import tempfile
import xml.etree.ElementTree as ET
from dataclasses import dataclass
from pathlib import Path

from .. import untrusted
from ..sandbox import private_tmp, real_home, wrap
from ..types import Task
from ..workspace import BASE_TAG
from . import not_applicable, run_meta, workspace_of, write_grade

CHECK_TIMEOUT_S = 15 * 60
REPORT_ENV = "BRUHSBENCH_REPORT"
LOG_TAIL = 4000


@dataclass(frozen=True)
class SuiteResult:
    passed: int
    total: int
    tests: dict[str, bool] | None  # per-test outcome, when the output names tests


@dataclass(frozen=True)
class CheckResult:
    ok: bool
    timed_out: bool
    tests: SuiteResult | None


# --------------------------------------------------------------------------- parsing


def _rel(path: str, root: Path | None) -> str:
    """A test file path relative to the copy it ran in, so copies at different roots agree."""
    if root is None or not path.startswith("/"):
        return path
    for form in dict.fromkeys((str(root), str(root.resolve()))):
        prefix = form.rstrip("/") + "/"
        for candidate in dict.fromkeys((path, str(Path(path).resolve()))):
            if candidate.startswith(prefix):
                return candidate[len(prefix):]
    return path


def _from_tests(tests: dict[str, bool]) -> SuiteResult:
    return SuiteResult(sum(tests.values()), len(tests), tests)


def _parse_jest(data: object, root: Path | None = None) -> SuiteResult | None:
    if not isinstance(data, dict) or not isinstance(data.get("testResults"), list):
        return None
    tests: dict[str, bool] = {}
    for suite in data["testResults"]:
        if not isinstance(suite, dict):
            continue
        name = _rel(suite.get("name") or suite.get("testFilePath") or "", root)
        for a in suite.get("assertionResults") or []:
            status = a.get("status")
            if status not in ("passed", "failed"):
                continue  # pending / skipped / todo
            title = a.get("fullName") or " ".join([*a.get("ancestorTitles", []), a.get("title", "")])
            tests[f"{name}::{title}"] = status == "passed"
    return _from_tests(tests)


def _parse_junit(text: str, cwd: Path | None = None) -> SuiteResult | None:
    try:
        root = ET.fromstring(text)
    except ET.ParseError:
        return None
    if root.tag not in ("testsuites", "testsuite"):
        return None
    tests: dict[str, bool] = {}
    for case in root.iter("testcase"):
        if case.find("skipped") is not None:
            continue
        cls = _rel(case.get("classname") or case.get("file") or "", cwd)
        name = f"{cls}::{case.get('name', '')}" if cls else case.get("name", "")
        tests[name] = case.find("failure") is None and case.find("error") is None
    return _from_tests(tests)


def _json_in(text: str) -> object | None:
    text = text.strip()
    candidates = [text] + [line for line in text.splitlines() if line.startswith("{")]
    for c in candidates:
        try:
            return json.loads(c)
        except ValueError:
            continue
    start = text.find("{")
    if start > 0:
        try:
            return json.loads(text[start:])
        except ValueError:
            pass
    return None


_CARGO_TEST_RE = re.compile(r"^test (\S+) \.\.\. (ok|FAILED)\s*$", re.MULTILINE)
_CARGO_SUMMARY_RE = re.compile(r"^test result: \w+\. (\d+) passed; (\d+) failed", re.MULTILINE)
_PYTEST_SUMMARY_RE = re.compile(
    r"^(?:=+ )?(.*\d+ (?:passed|failed|errors?).*) in [\d.]+s", re.MULTILINE)


def _parse_cargo(out: str) -> SuiteResult | None:
    tests = {m[1]: m[2] == "ok" for m in _CARGO_TEST_RE.finditer(out)}
    if tests:
        return _from_tests(tests)
    sums = _CARGO_SUMMARY_RE.findall(out)
    if sums:
        passed = sum(int(p) for p, _ in sums)
        return SuiteResult(passed, passed + sum(int(f) for _, f in sums), None)
    return None


def _parse_pytest_summary(out: str) -> SuiteResult | None:
    m = _PYTEST_SUMMARY_RE.findall(out)
    if not m:
        return None
    counts = dict((k.rstrip("s"), int(n)) for n, k in re.findall(r"(\d+) (\w+)", m[-1]))
    passed = counts.get("passed", 0)
    return SuiteResult(passed, passed + counts.get("failed", 0) + counts.get("error", 0), None)


def parse_test_output(report: Path, stdout: str, root: Path | None = None) -> SuiteResult | None:
    """Per-test results from the reporter file, else from stdout; None if unrecognised.

    Absolute test file paths under ``root`` (the directory the check ran in) are made
    relative to it, so the same test has the same name in the base and the agent copy.
    """
    try:  # written by the sandboxed check: read without following symlinks (R22)
        text = untrusted.read_text(report.parent, report.name)
    except untrusted.UnsafePath:
        text = None
    if text is not None:
        parsed = (_parse_junit(text, root) if text.lstrip().startswith("<")
                  else _parse_jest(_json_in(text), root))
        if parsed is not None:
            return parsed
    return (_parse_jest(_json_in(stdout), root) or _parse_cargo(stdout)
            or _parse_pytest_summary(stdout))


# --------------------------------------------------------------------------- running


_SECRET_ENV_RE = re.compile(
    r"(?:_API_KEY|_KEY|_TOKEN|_SECRET|_PASSWORD|_CREDENTIALS?|_AUTH)$"
    r"|^(?:CLAUDE|ANTHROPIC|OPENAI|XAI|GROK|CODEX|GEMINI|GOOGLE|AWS|AZURE|GH|GITHUB|LINEAR"
    r"|HF|HUGGING_FACE|VERCEL|BRUHSBENCH)(?:_|$)|^CLAUDECODE$|_AUTH_TOKEN|_AUTHTOKEN"
    # agent sockets (ssh/gpg signing and auth)
    r"|^SSH_AUTH_SOCK$|^SSH_AGENT_PID$|^GPG_AGENT_INFO$|^GNUPGHOME$|_AGENT_SOCK$")


def check_env() -> dict[str, str]:
    """The harness environment minus credentials and agent/CLI configuration."""
    return {k: v for k, v in os.environ.items() if not _SECRET_ENV_RE.search(k.upper())}


# Toolchain locations that stay at their real (sandbox read-only) place when HOME moves
_TOOL_HOMES = {"CARGO_HOME": ".cargo", "RUSTUP_HOME": ".rustup",
               "PLAYWRIGHT_BROWSERS_PATH": "Library/Caches/ms-playwright"}


def sandboxed_env(scratch: Path) -> dict[str, str]:
    """:func:`check_env` with ``HOME`` at ``scratch/home`` for agent-written code run
    under the sandbox: the real home is unreadable and unwritable there, so caches
    (npm, uv, ...) go to the scratch home; cargo/rustup/playwright keep their real
    toolchains (read-only)."""
    env = check_env()
    home = Path(scratch) / "home"
    home.mkdir(parents=True, exist_ok=True)
    for var, rel in _TOOL_HOMES.items():
        if var not in env and (real_home() / rel).exists():
            env[var] = str(real_home() / rel)
    env["HOME"] = str(home)
    return env


def scratch_root(workspace: Path) -> Path:
    """``<work_root>/_scratch``: grading copies live next to the run roots, never inside
    one, so nothing the agent left running can reach them (R21)."""
    root = Path(workspace).parent.parent / "_scratch"
    root.mkdir(parents=True, exist_ok=True)
    return root


def sandboxed_check(cmd: str, scratch: Path) -> list[str]:
    """argv running ``bash -c cmd`` under the sandbox: writes only in ``scratch``, and no
    reads of any run root next to it (R19/R21)."""
    return wrap(["bash", "-c", cmd], writable=[scratch], denied=[Path(scratch).parent.parent])


def clone_tree(src: Path, dest: Path) -> None:
    """Copy-on-write clone where the filesystem allows it, else a plain copy. Symlinks are
    copied as links; a ``src`` that resolves into the real home is refused (R22)."""
    untrusted.check_outside_home(src)
    try:
        proc = subprocess.run(["cp", "-cR", str(src), str(dest)], capture_output=True)
        if proc.returncode == 0:
            return
    except OSError:
        pass
    shutil.rmtree(dest, ignore_errors=True)
    shutil.copytree(src, dest, symlinks=True)
    if dest.is_symlink() or not dest.is_dir():
        raise untrusted.UnsafePath(f"clone of {src} is not a real directory")


def run_check(name: str, cmd: str, cwd: Path, scratch: Path, log_dir: Path) -> CheckResult:
    report = scratch / f"{name}-{cwd.name}.report"
    report.unlink(missing_ok=True)
    env = {**private_tmp(sandboxed_env(scratch), scratch), REPORT_ENV: str(report)}
    argv = sandboxed_check(cmd, scratch)  # agent-written code (R19)
    proc = subprocess.Popen(argv, cwd=cwd, env=env, stdin=subprocess.DEVNULL,
                            stdout=subprocess.PIPE, stderr=subprocess.STDOUT,
                            start_new_session=True)
    timed_out = False
    try:
        out, _ = proc.communicate(timeout=CHECK_TIMEOUT_S)
    except subprocess.TimeoutExpired:
        timed_out = True
        os.killpg(proc.pid, signal.SIGKILL)
        out, _ = proc.communicate()
    finally:
        try:  # anything the check left running (watchers, servers)
            os.killpg(proc.pid, signal.SIGKILL)
        except (ProcessLookupError, PermissionError):
            pass
    text = out.decode(errors="replace")
    log_dir.mkdir(parents=True, exist_ok=True)
    (log_dir / f"{name}-{cwd.name}.log").write_text(
        f"$ {cmd}\n# exit {proc.returncode}{' (timed out)' if timed_out else ''}\n"
        f"{text[-LOG_TAIL:]}")
    ok = proc.returncode == 0 and not timed_out
    return CheckResult(ok, timed_out,
                       None if timed_out else parse_test_output(report, text, cwd))


def _to_base(copy: Path) -> None:
    """Reset a copy to bench-base; ignored files (deps installed by setup) stay."""
    untrusted.git(copy, "reset", "--quiet", "--hard", BASE_TAG)
    untrusted.git(copy, "clean", "--quiet", "-fd")


def _overlay(src: Path, dest: Path) -> None:
    untrusted.overlay(src, dest)  # never writes through a symlink the agent planted


def _counts(res: CheckResult) -> tuple[int, int]:
    if res.tests is not None and res.tests.total > 0:
        return res.tests.passed, res.tests.total
    return int(res.ok), 1


def _regressions(name: str, base: CheckResult, after: CheckResult) -> list[str]:
    base_tests = base.tests.tests if base.tests else None
    after_tests = after.tests.tests if after.tests else None
    if base_tests is not None:
        if after_tests is not None:
            return sorted(t for t, ok in base_tests.items() if ok and not after_tests.get(t))
        if not after.ok:  # the suite crashed or timed out: nothing that passed is known to
            return sorted(t for t, ok in base_tests.items() if ok)
        return []
    return [name] if base.ok and not after.ok else []


def _base_problem(copy: Path, workspace: Path) -> str | None:
    """Why the bench-base state can't be restored (checked in ``copy``, a clone of the
    agent's ``workspace``), if it can't."""
    if not os.path.lexists(copy / ".git"):
        return f"no .git in {workspace}"
    proc = untrusted.git(copy, "rev-parse", "--verify", "--quiet", f"{BASE_TAG}^{{commit}}",
                         write=False, check=False)
    return None if proc.returncode == 0 else f"tag {BASE_TAG} missing in {workspace}"


def grade(task: Task, run_dir: Path) -> dict:
    workspace = workspace_of(run_dir)
    if workspace is None:
        return not_applicable(run_dir, "commands",
                              f"no workspace (status {run_meta(run_dir).get('status')})")
    log_dir = Path(run_dir) / "grades" / "logs"
    hidden_cmd = task.checks.get("hidden")
    has_hidden = task.hidden_tests is not None and task.hidden_tests.is_dir()
    if has_hidden and not hidden_cmd:
        raise ValueError(f"task {task.id}: has hidden tests ({task.hidden_tests}) but no "
                         "checks.hidden in task.toml to run them")

    checks: dict[str, bool] = {}
    timed_out: list[str] = []
    result: dict = {"applicable": True}
    scratch = Path(tempfile.mkdtemp(prefix="grade-", dir=scratch_root(workspace)))
    try:
        agent = scratch / "after"
        clone_tree(workspace, agent)
        after_results: dict[str, CheckResult] = {}
        for name, cmd in task.checks.items():
            if name == "hidden":
                continue
            res = after_results[name] = run_check(name, cmd, agent, scratch, log_dir)
            checks[name] = res.ok
            if res.timed_out:
                timed_out.append(name)

        regressions: list[str] | None = []
        problem = None
        if "test" in task.checks:
            base = scratch / "base"
            clone_tree(workspace, base)
            problem = _base_problem(base, workspace)
        if problem is not None:
            result["error"] = f"regressions not computed: {problem}"
            regressions = None
        elif "test" in task.checks:
            _to_base(base)
            base_res = run_check("test", task.checks["test"], base, scratch, log_dir)
            regressions = _regressions("test", base_res, after_results["test"])

        hidden_pass = hidden_total = 0
        if has_hidden:
            _overlay(task.hidden_tests, agent)
            res = run_check("hidden", hidden_cmd, agent, scratch, log_dir)
            if res.timed_out:
                timed_out.append("hidden")
            hidden_pass, hidden_total = _counts(res)
            result["hidden"] = {"applicable": True, "parsed": res.tests is not None,
                                "failed": sorted(t for t, ok in (res.tests.tests or {}).items()
                                                 if not ok) if res.tests else []}
        else:
            result["hidden"] = {"applicable": False}
    finally:
        shutil.rmtree(scratch, ignore_errors=True)

    result.update(checks=checks, hidden_pass=hidden_pass, hidden_total=hidden_total,
                  regressions=regressions, timed_out=timed_out)
    return write_grade(run_dir, "commands", result)
