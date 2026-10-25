"""Headless invocations of the three agent CLIs, and parsing of what they print.

Formats (fixtures in ``tests/fixtures/cli_output/``, captured live from each CLI
answering "Reply with the word ok and nothing else." in an isolated home):

claude ``--output-format stream-json --verbose``
    JSONL events: ``system/init``, ``assistant`` messages (``tool_use`` blocks),
    ``user`` messages (``tool_result`` blocks), and a final ``result`` event with
    ``result`` (final message), ``num_turns``, ``usage``, ``total_cost_usd``.
codex ``exec --json``
    JSONL events. The final message is the last ``item.completed`` item of type
    ``agent_message`` (also written to ``<run_dir>/final.txt`` by ``-o``); tokens
    come from ``turn.completed.usage``; tool activity is ``item.*`` events of other
    item types (``command_execution``, ``file_change``, ...). No turn count and no
    cost are reported.
grok ``--output-format streaming-json``
    JSONL events: ``text`` deltas (``data``), ``tool_call`` / ``tool_call_update``
    (input, output, cwd), ``usage`` per model call, and a final ``end`` event with
    ``usage``, ``num_turns``, ``total_cost_usd``. The final message is the text
    streamed after the last tool event.

The streaming formats are used (not the single-object ``json`` ones) so the
transcript carries every tool call and result for the contamination scan.

Token counts are normalized to "all input the model read, cached or not": claude
and grok report ``input_tokens`` without cache reads/writes, so those are added;
codex's ``input_tokens`` already include ``cached_input_tokens``. Output tokens
include reasoning/thinking tokens in all three.

Web search/fetch is turned off in all three CLIs and both arms (the tasks are
offline and "no external services" is part of the preamble).
"""

from __future__ import annotations

import json
import re
from dataclasses import dataclass
from pathlib import Path

from .homes import claude_args
from .types import MODELS, Arm, Cli, ModelSpec

PREAMBLE = (
    "You are working unattended: no human will answer questions. Make reasonable "
    "decisions yourself instead of asking. Do not push, open PRs, or contact external "
    "services. When you believe the task is complete, stop and summarize what you did "
    "and how you verified it.\n\nTask:\n"
)


@dataclass(frozen=True)
class Price:
    """USD per million tokens."""

    input: float
    cached_input: float
    output: float


# Only needed for CLIs that don't report cost themselves (codex). None = not verified
# from a published source; cost is then reported as None rather than guessed.
PRICES: dict[str, Price | None] = {
    "gpt-6.1-sol": None,
}


@dataclass(frozen=True)
class ParsedRun:
    final_message: str
    turns: int | None
    input_tokens: int | None
    output_tokens: int | None
    cost_usd: float | None


EMPTY = ParsedRun("", None, None, None, None)


def full_prompt(prompt: str) -> str:
    return PREAMBLE + prompt


def build_command(spec: ModelSpec, arm: Arm, prompt: str, workdir: Path, home: Path,
                  run_dir: Path) -> list[str]:
    """argv for one headless run. claude must be started with cwd=workdir."""
    text = full_prompt(prompt)
    if spec.cli == "claude":
        return ["claude", "-p", text, "--model", spec.model, "--effort", spec.effort,
                "--output-format", "stream-json", "--verbose", "--dangerously-skip-permissions",
                "--disallowed-tools", "WebSearch,WebFetch", *claude_args(arm, home)]
    if spec.cli == "codex":
        return ["codex", "exec", "--json", "-m", spec.model,
                "-c", f'model_reasoning_effort="{spec.effort}"', "-c", 'web_search="disabled"',
                "--dangerously-bypass-approvals-and-sandbox", "--skip-git-repo-check",
                "-C", str(workdir), "-o", str(run_dir / "final.txt"), text]
    if spec.cli == "grok":
        return ["grok", "-p", text, "-m", spec.model, "--reasoning-effort", spec.effort,
                "--output-format", "streaming-json", "--always-approve", "--cwd", str(workdir),
                "--disable-web-search"]
    raise ValueError(f"unknown cli {spec.cli!r}")


# --------------------------------------------------------------------------- parsing


def _json_lines(stdout: str) -> list[dict]:
    events = []
    for line in stdout.splitlines():
        line = line.strip()
        if not line.startswith("{"):
            continue
        try:
            event = json.loads(line)
        except json.JSONDecodeError:
            continue
        if isinstance(event, dict):
            events.append(event)
    return events


def _int(value) -> int | None:
    return value if isinstance(value, int) and not isinstance(value, bool) else None


def _float(value) -> float | None:
    if isinstance(value, (int, float)) and not isinstance(value, bool):
        return float(value)
    return None


def _total_input(usage: dict) -> int | None:
    base = _int(usage.get("input_tokens"))
    if base is None:
        return None
    return base + sum(_int(usage.get(k)) or 0
                      for k in ("cache_creation_input_tokens", "cache_read_input_tokens"))


def _last(events: list[dict], kind: str) -> dict | None:
    return next((e for e in reversed(events) if e.get("type") == kind), None)


def _claude_text(event: dict) -> str:
    content = (event.get("message") or {}).get("content") or []
    return "".join(c.get("text", "") for c in content
                   if isinstance(c, dict) and c.get("type") == "text")


def _parse_claude(stdout: str) -> ParsedRun:
    events = _json_lines(stdout)
    data = _last(events, "result")
    if data is None:
        # killed before the result event (timeout): last assistant text, no totals
        texts = [t for e in events if e.get("type") == "assistant" and (t := _claude_text(e))]
        return ParsedRun(texts[-1] if texts else "", None, None, None, None)
    usage = data.get("usage") or {}
    result = data.get("result")
    return ParsedRun(
        final_message=result if isinstance(result, str) else "",
        turns=_int(data.get("num_turns")),
        input_tokens=_total_input(usage),
        output_tokens=_int(usage.get("output_tokens")),
        cost_usd=_float(data.get("total_cost_usd")),
    )


_GROK_TOOL_EVENTS = ("tool_call", "tool_call_update")


def _parse_grok(stdout: str) -> ParsedRun:
    events = _json_lines(stdout)
    chunks: list[str] = []
    for event in events:
        if event.get("type") in _GROK_TOOL_EVENTS:
            chunks = []  # text before a tool call is narration, not the final message
        elif event.get("type") == "text" and isinstance(event.get("data"), str):
            chunks.append(event["data"])
    final = "".join(chunks).strip()
    end = _last(events, "end")
    if end is None and _grok_background_wait_ran_out(events):
        end = _last(events, "error")  # carries the run's usage like "end" does
    if end is None:
        return ParsedRun(final, None, None, None, None)
    usage = end.get("usage") or {}
    return ParsedRun(
        final_message=final,
        turns=_int(end.get("num_turns")),
        input_tokens=_total_input(usage),
        output_tokens=_int(usage.get("output_tokens")),
        cost_usd=_float(end.get("total_cost_usd")),
    )


def _codex_cost(input_tokens: int, cached: int, output_tokens: int) -> float | None:
    model = next(m.model for m in MODELS if m.cli == "codex")
    price = PRICES.get(model)
    if price is None:
        return None
    return ((input_tokens - cached) * price.input + cached * price.cached_input
            + output_tokens * price.output) / 1_000_000


# grok -p waits (10 min by default) for background work the agent left running after its
# turn ended (e.g. a dev server), then stops it and exits 1 with this error event.
_GROK_BACKGROUND_WAIT_RE = re.compile(r"^the wait for background work ran out\b")


def _grok_background_wait_ran_out(events: list[dict]) -> bool:
    last = events[-1] if events else None
    return (last is not None and last.get("type") == "error"
            and bool(_GROK_BACKGROUND_WAIT_RE.match(str(last.get("message", "")))))


def agent_finished(cli: Cli, stdout: str, code: int) -> bool:
    """The CLI exited because the agent finished: exit 0, or grok's exit 1 after its
    wait for leftover background work ran out (the agent's turn had already ended)."""
    if code == 0:
        return True
    return cli == "grok" and _grok_background_wait_ran_out(_json_lines(stdout))


def _parse_codex(stdout: str) -> ParsedRun:
    final = ""
    usages = []
    for event in _json_lines(stdout):
        kind = event.get("type")
        item = event.get("item") or {}
        if kind == "item.completed" and item.get("type") == "agent_message":
            final = item.get("text") or ""
        elif kind == "turn.completed" and isinstance(event.get("usage"), dict):
            usages.append(event["usage"])
    if not usages:
        return ParsedRun(final, None, None, None, None)
    inp = sum(_int(u.get("input_tokens")) or 0 for u in usages)
    cached = sum(_int(u.get("cached_input_tokens")) or 0 for u in usages)
    out = sum(_int(u.get("output_tokens")) or 0 for u in usages)
    return ParsedRun(final, None, inp, out, _codex_cost(inp, cached, out))


_PARSERS = {"claude": _parse_claude, "codex": _parse_codex, "grok": _parse_grok}


_CODEX_NON_TOOL_ITEMS = ("agent_message", "reasoning", "error", "todo_list")


def tool_event_count(cli: Cli, stdout: str) -> int:
    """How many tool calls/results the transcript shows (0: no tool-level visibility)."""
    n = 0
    for event in _json_lines(stdout):
        kind = event.get("type")
        if cli == "claude" and kind in ("assistant", "user"):
            content = (event.get("message") or {}).get("content") or []
            n += sum(1 for c in content if isinstance(c, dict)
                     and c.get("type") in ("tool_use", "tool_result"))
        elif cli == "codex" and str(kind).startswith("item."):
            n += (event.get("item") or {}).get("type") not in _CODEX_NON_TOOL_ITEMS
        elif cli == "grok" and kind in _GROK_TOOL_EVENTS:
            n += 1
    return n


def parse_output(cli: Cli, stdout: str) -> ParsedRun:
    """What a finished run reported; fields the CLI doesn't report are None."""
    if cli not in _PARSERS:
        raise ValueError(f"unknown cli {cli!r}")
    return _PARSERS[cli](stdout)


# --------------------------------------------------------------------------- auth

_AUTH_PATTERNS = {
    "claude": re.compile(r"not logged in|please run /login|invalid api key|oauth token "
                         r"(has )?expired|authentication_error|401 unauthorized", re.I),
    "codex": re.compile(r"401 unauthorized|not logged in|please (log|sign) in|"
                        r"refresh token|token (has )?expired|invalid_api_key", re.I),
    "grok": re.compile(r"not signed in|not logged in|401 unauthorized|grok login", re.I),
}


def _cli_error_text(cli: Cli, stdout: str) -> str:
    """Error text the CLI itself emitted on stdout, excluding the agent's own output
    (tool results can legitimately contain words like "401 Unauthorized")."""
    if cli == "claude":
        data = _last(_json_lines(stdout), "result")
        if data is None or not data.get("is_error"):
            return ""
        status = data.get("api_error_status")
        return f"{data.get('result', '')} {'401 unauthorized' if status == 401 else ''}"
    events = _json_lines(stdout)
    texts = []
    for event in events:
        if event.get("type") == "error":
            texts.append(str(event.get("message", "")))
        elif event.get("type") == "turn.failed":
            texts.append(str((event.get("error") or {}).get("message", "")))
    return "\n".join(texts)


def is_auth_failure(cli: Cli, stdout: str, stderr: str, code: int) -> bool:
    """True if the run failed because the CLI wasn't authenticated (not the agent's fault)."""
    if code == 0:
        return False
    pattern = _AUTH_PATTERNS[cli]
    return bool(pattern.search(_cli_error_text(cli, stdout)) or pattern.search(stderr))
