from pathlib import Path

import pytest

from bruhsbench.agents import (
    PREAMBLE,
    ParsedRun,
    build_command,
    full_prompt,
    is_auth_failure,
    parse_output,
    tool_event_count,
)
from bruhsbench.homes import claude_args
from bruhsbench.types import MODELS

FIXTURES = Path(__file__).parent / "fixtures" / "cli_output"
SPECS = {m.cli: m for m in MODELS}
WORK = Path("/private/tmp/bruhsbench/r/work")
HOME = Path("/private/tmp/bruhsbench/r/home")
RUN_DIR = Path("/private/tmp/bruhsbench/r")


def fixture(name: str) -> str:
    return (FIXTURES / name).read_text()


def cmd(cli: str, arm: str, prompt: str = "do the thing") -> list[str]:
    return build_command(SPECS[cli], arm, prompt, WORK, HOME, RUN_DIR)


# --------------------------------------------------------------------- commands


def test_preamble_text_is_exact():
    assert PREAMBLE == (
        "You are working unattended: no human will answer questions. Make reasonable "
        "decisions yourself instead of asking. Do not push, open PRs, or contact external "
        "services. When you believe the task is complete, stop and summarize what you did "
        "and how you verified it.\n\nTask:\n"
    )


@pytest.mark.parametrize("cli", ["claude", "codex", "grok"])
@pytest.mark.parametrize("arm", ["bare", "bruhs"])
def test_preamble_prepended(cli, arm):
    argv = cmd(cli, arm, "Fix the bug.")
    prompt = full_prompt("Fix the bug.")
    assert prompt == PREAMBLE + "Fix the bug."
    assert argv.count(prompt) == 1
    assert "Fix the bug." not in argv  # only ever sent with the preamble


def _remove_once(argv: list[str], part: list[str]) -> list[str]:
    for i in range(len(argv) - len(part) + 1):
        if argv[i:i + len(part)] == part:
            return argv[:i] + argv[i + len(part):]
    raise AssertionError(f"{part} not a contiguous slice of {argv}")


def test_build_command_identical_across_arms_except_bruhs_flags():
    for cli in ("codex", "grok"):
        assert cmd(cli, "bare") == cmd(cli, "bruhs")
    # claude: the only difference is what homes.claude_args() contributes
    bare = _remove_once(cmd("claude", "bare"), claude_args("bare", HOME))
    bruhs = _remove_once(cmd("claude", "bruhs"), claude_args("bruhs", HOME))
    assert bare == bruhs
    assert cmd("claude", "bare") != cmd("claude", "bruhs")


def test_claude_command():
    argv = cmd("claude", "bruhs")
    assert argv[:3] == ["claude", "-p", full_prompt("do the thing")]
    for pair in (["--model", "claude-opus-5-5"], ["--effort", "high"],
                 ["--output-format", "stream-json"],
                 ["--disallowed-tools", "WebSearch,WebFetch"]):
        _remove_once(argv, pair)
    assert "--dangerously-skip-permissions" in argv
    assert "--verbose" in argv  # stream-json requires it with -p
    _remove_once(argv, claude_args("bruhs", HOME))


def test_codex_command():
    argv = cmd("codex", "bare")
    assert argv[:3] == ["codex", "exec", "--json"]
    assert argv[-1] == full_prompt("do the thing")
    for pair in (["-m", "gpt-6.1-sol"], ["-c", 'model_reasoning_effort="high"'],
                 ["-c", 'web_search="disabled"'], ["-C", str(WORK)],
                 ["-o", str(RUN_DIR / "final.txt")]):
        _remove_once(argv, pair)
    assert "--dangerously-bypass-approvals-and-sandbox" in argv
    assert "--skip-git-repo-check" in argv


def test_grok_command():
    argv = cmd("grok", "bare")
    assert argv[:3] == ["grok", "-p", full_prompt("do the thing")]
    for pair in (["-m", "grok-4.7"], ["--reasoning-effort", "high"],
                 ["--output-format", "streaming-json"], ["--cwd", str(WORK)]):
        _remove_once(argv, pair)
    assert "--always-approve" in argv
    assert "--disable-web-search" in argv


# --------------------------------------------------------------------- parsing


def test_parse_output_claude():
    run = parse_output("claude", fixture("claude.jsonl"))
    assert run == ParsedRun(final_message="ok", turns=1,
                            input_tokens=2 + 5569 + 11111, output_tokens=4,
                            cost_usd=pytest.approx(0.0468622))


def test_parse_output_claude_with_tool_call():
    run = parse_output("claude", fixture("claude_tool.jsonl"))
    assert run == ParsedRun(final_message="ok", turns=2,
                            input_tokens=4 + 5618 + 27727, output_tokens=86,
                            cost_usd=pytest.approx(0.0522254))


def test_parse_output_claude_killed_before_result():
    lines = [l for l in fixture("claude_tool.jsonl").splitlines() if '"type":"result"' not in l]
    assert parse_output("claude", "\n".join(lines)) == ParsedRun("ok", None, None, None, None)


def test_parse_output_codex():
    run = parse_output("codex", fixture("codex.jsonl"))
    assert run.final_message == "ok"
    assert run.input_tokens == 11232  # codex input_tokens already include cached
    assert run.output_tokens == 5
    assert run.turns is None
    assert run.cost_usd is None  # gpt-6.1-sol price unverified -> PRICES entry is None


def test_parse_output_codex_sums_turns_and_takes_last_message():
    stdout = "\n".join([
        '{"type":"item.completed","item":{"type":"agent_message","text":"first"}}',
        '{"type":"turn.completed","usage":{"input_tokens":10,"output_tokens":2}}',
        "not json noise",
        '{"type":"item.completed","item":{"type":"agent_message","text":"done"}}',
        '{"type":"turn.completed","usage":{"input_tokens":5,"output_tokens":3}}',
    ])
    run = parse_output("codex", stdout)
    assert (run.final_message, run.input_tokens, run.output_tokens) == ("done", 15, 5)


def test_parse_output_grok():
    run = parse_output("grok", fixture("grok.jsonl"))
    assert run == ParsedRun(final_message="ok", turns=1, input_tokens=4141 + 9600 + 0,
                            output_tokens=36, cost_usd=pytest.approx(0.013298))


def test_parse_output_grok_with_tool_call():
    run = parse_output("grok", fixture("grok_tool.jsonl"))
    assert run == ParsedRun(final_message="ok", turns=2, input_tokens=15015 + 17024,
                            output_tokens=65, cost_usd=pytest.approx(0.038932))


def test_parse_output_grok_final_is_text_after_last_tool():
    stdout = "\n".join([
        '{"type":"text","data":"Let me look. "}',
        '{"type":"tool_call","toolName":"read_file"}',
        '{"type":"text","data":"All "}',
        '{"type":"text","data":"done."}',
    ])
    assert parse_output("grok", stdout) == ParsedRun("All done.", None, None, None, None)


def test_tool_event_count():
    assert tool_event_count("claude", fixture("claude_tool.jsonl")) == 2  # use + result
    assert tool_event_count("claude", fixture("claude.jsonl")) == 0
    assert tool_event_count("grok", fixture("grok_tool.jsonl")) > 0
    assert tool_event_count("grok", fixture("grok.jsonl")) == 0
    assert tool_event_count("codex", fixture("codex.jsonl")) == 0
    assert tool_event_count("codex", '{"type":"item.completed","item":'
                                     '{"type":"command_execution","command":"ls"}}') == 1


@pytest.mark.parametrize("cli", ["claude", "codex", "grok"])
def test_parse_output_garbage_is_empty(cli):
    assert parse_output(cli, "") == ParsedRun("", None, None, None, None)
    assert parse_output(cli, "Traceback: boom") == ParsedRun("", None, None, None, None)


# --------------------------------------------------------------------- auth


def test_is_auth_failure_claude():
    assert is_auth_failure("claude", fixture("claude_auth_error.jsonl"), "", 1)
    assert not is_auth_failure("claude", fixture("claude.jsonl"), "", 0)
    # an agent that merely talks about logins is not an auth failure
    assert not is_auth_failure(
        "claude", fixture("claude.jsonl").replace('"result":"ok"',
                                                  '"result":"Not logged in page fixed"'), "", 0)


def test_is_auth_failure_codex():
    assert is_auth_failure("codex", fixture("codex_auth_error.jsonl"), "", 1)
    assert not is_auth_failure("codex", fixture("codex.jsonl"), "", 0)
    # 401 text inside command output from the agent's own work is not an auth failure
    tool_out = ('{"type":"item.completed","item":{"type":"command_execution",'
                '"aggregated_output":"401 Unauthorized"}}\n'
                '{"type":"turn.failed","error":{"message":"stream disconnected"}}')
    assert not is_auth_failure("codex", tool_out, "", 1)


def test_is_auth_failure_grok():
    assert is_auth_failure("grok", fixture("grok_auth_error.jsonl"),
                           fixture("grok_auth_error.stderr"), 1)
    assert is_auth_failure("grok", "", fixture("grok_auth_error.stderr"), 1)
    assert not is_auth_failure("grok", fixture("grok.jsonl"), "", 0)
    assert not is_auth_failure("grok", '{"type":"error","message":"rate limited"}', "", 1)
