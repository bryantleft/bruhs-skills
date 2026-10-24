"""LLM judges: blind pairwise comparison, checklist items, and extraction for graders.

No model judges its own family's runs: :func:`judges_for` gives the two other families
(used by :func:`pairwise` and ``graders.checklist``, each judge's verdict kept apart), and
:func:`make_judge` gives ONE other family (claude->codex, codex->grok, grok->claude) for
the low-taste extraction/matching calls the objective graders make (Ruling R18).

:func:`judge_call` runs one headless call in a fresh bare isolated home
(``homes.build_home``, under ``$BRUHSBENCH_WORK``/_judge, default
``/private/tmp/bruhsbench/_judge``) with an empty cwd and NO tools: every material is in
the message itself (text inlined, images attached), so a judge can't wander the disk.
Mechanisms (verified live, ``pytest -m live tests/test_judge.py``):

claude
    ``-p --input-format stream-json`` with the message (text + base64 image blocks) on
    stdin, ``--output-format stream-json --json-schema <schema>`` -> the result event's
    ``structured_output``; ``--tools ""``, strict empty MCP config.
codex
    ``exec --output-schema <file> -o <file> -s read-only -i <image>...`` with the shell,
    view_image and browser/computer features disabled.
grok
    ``--prompt-file <json>`` holding ACP content blocks (text + base64 images),
    ``--output-format json --json-schema <schema>`` -> ``structuredOutput``; ``--tools ""
    --disable-web-search``. (With a file-read tool and no sandbox -- grok's ``strict``
    sandbox won't start on this machine -- a grok judge that couldn't open an image read
    files across the real home looking for it, so judges get no tools at all.)

Screenshots are scaled/tiled to at most :data:`MAX_IMAGE_PX` per side
(:func:`prepare_images`, macOS ``sips``) so every judge sees the same pixels.

Output is validated against the schema (:func:`validate`); invalid output is retried once,
then :class:`JudgeError`.

Blindness (pairwise and checklist): everything a judge sees passes :func:`redact`, which
strips strings that would reveal the bruhs arm, and diffs go through
:func:`diff_for_judge`, which drops CLAUDE.md/AGENTS.md and agent-config files (they differ
by arm by construction) before truncating to :data:`MAX_DIFF_CHARS`. Pairwise shows the
two runs as A/B in an order seeded by (task, repeat, judge); the mapping lives only in
``<results_root>/_pairs/pairs_key.json``, the judge's verdict (in A/B terms) in
``<results_root>/_pairs/<task>__<cli>__r<repeat>__<judge>.json``.
"""

from __future__ import annotations

import base64
import fcntl
import hashlib
import json
import mimetypes
import random
import re
import shutil
import subprocess
import tempfile
from pathlib import Path

from .graders.scope import parse_diff
from .homes import BRUHS_REPO, build_home, claude_args
from . import untrusted
from .sandbox import private_tmp, work_base, wrap
from .types import MODELS, Cli, ModelSpec, Task

JUDGE_TIMEOUT_S = 20 * 60
MAX_DIFF_CHARS = 60_000
MAX_FINAL_CHARS = 20_000
MAX_FILES_CHARS = 150_000
# Anthropic's per-image limit once a request has more than 20 images; screenshots are
# scaled/tiled to fit so every judge sees the same pixels
MAX_IMAGE_PX = 2000
MAX_TILES = 4

# one other family for extraction (R18)
EXTRACTION_JUDGE: dict[str, str] = {"claude": "codex", "codex": "grok", "grok": "claude"}


class JudgeError(RuntimeError):
    pass


def judges_for(run_cli: Cli) -> list[ModelSpec]:
    """The two model families other than the run's own."""
    return [m for m in MODELS if m.cli != run_cli]


def _spec(cli: str) -> ModelSpec:
    return next(m for m in MODELS if m.cli == cli)


# --------------------------------------------------------------------------- schemas

PAIRWISE_SCHEMA = {
    "type": "object",
    "properties": {"winner": {"type": "string", "enum": ["A", "B", "tie"]},
                   "reasons": {"type": "string"}},
    "required": ["winner", "reasons"],
    "additionalProperties": False,
}

CHECKLIST_SCHEMA = {
    "type": "object",
    "properties": {"items": {"type": "array", "items": {
        "type": "object",
        "properties": {"id": {"type": "string"}, "hit": {"type": "boolean"},
                       "evidence": {"type": "string"}},
        "required": ["id", "hit", "evidence"],
        "additionalProperties": False,
    }}},
    "required": ["items"],
    "additionalProperties": False,
}

FINDINGS_SCHEMA = {
    "type": "object",
    "properties": {"findings": {"type": "array", "items": {
        "type": "object",
        "properties": {"file": {"type": ["string", "null"]},
                       "line": {"type": ["integer", "null"]},
                       "line_end": {"type": ["integer", "null"]},
                       "summary": {"type": "string"},
                       "severity": {"type": ["string", "null"]}},
        "required": ["file", "line", "line_end", "summary", "severity"],
        "additionalProperties": False,
    }}},
    "required": ["findings"],
    "additionalProperties": False,
}

CLAIM_KINDS = ["done", "fixed", "tests_pass", "verified", "other"]
CLAIMS_SCHEMA = {
    "type": "object",
    "properties": {"claims": {"type": "array", "items": {
        "type": "object",
        "properties": {"claim": {"type": "string"},
                       "kind": {"type": "string", "enum": CLAIM_KINDS}},
        "required": ["claim", "kind"],
        "additionalProperties": False,
    }}},
    "required": ["claims"],
    "additionalProperties": False,
}

MATCH_SCHEMA = {
    "type": "object",
    "properties": {"id": {"type": ["string", "null"]}, "reason": {"type": "string"}},
    "required": ["id", "reason"],
    "additionalProperties": False,
}

ITEMS_SCHEMA = {
    "type": "object",
    "properties": {"ids": {"type": "array", "items": {"type": "string"}},
                   "reason": {"type": "string"}},
    "required": ["ids", "reason"],
    "additionalProperties": False,
}

_TYPES = {
    "object": lambda v: isinstance(v, dict),
    "array": lambda v: isinstance(v, list),
    "string": lambda v: isinstance(v, str),
    "boolean": lambda v: isinstance(v, bool),
    "integer": lambda v: isinstance(v, int) and not isinstance(v, bool),
    "number": lambda v: isinstance(v, (int, float)) and not isinstance(v, bool),
    "null": lambda v: v is None,
}


def validate(value, schema: dict) -> bool:
    """Whether ``value`` satisfies ``schema`` (the subset of JSON Schema used here)."""
    types = schema.get("type")
    if types is not None:
        types = [types] if isinstance(types, str) else types
        if not any(_TYPES[t](value) for t in types):
            return False
    if "enum" in schema and value not in schema["enum"]:
        return False
    if isinstance(value, dict):
        props = schema.get("properties", {})
        if any(k not in value for k in schema.get("required", [])):
            return False
        if schema.get("additionalProperties") is False and set(value) - set(props):
            return False
        return all(validate(v, props[k]) for k, v in value.items() if k in props)
    if isinstance(value, list) and "items" in schema:
        return all(validate(v, schema["items"]) for v in value)
    return True


# --------------------------------------------------------------------------- redaction

_MARKER_BLOCK_RE = re.compile(
    r"<!--\s*/?bruhs:[^>]*-->(?:.*?<!--\s*/?bruhs:[^>]*-->)?", re.IGNORECASE | re.DOTALL)
# a removed token takes one space before it along, unless that space is indentation
_LEAD = r"(?:(?<=\S)[ \t])?"
# tokens removed whole: paths/names that carry a giveaway anywhere inside them
_TOKEN_RE = re.compile(
    _LEAD + r"[^\s`'\"()\[\]{}<>,;]*(?:bruhs|superpowers|\.agents/skills|chrome-devtools"
    r"|expect-cli|mcp__expect)[^\s`'\"()\[\]{}<>,;]*",
    re.IGNORECASE)
_SLASH_CMD_RE = re.compile(
    _LEAD + r"(?<![\w/.-])/(?:cook|slop|peep|yeet|verify|doodle|expect)(?![\w-])", re.IGNORECASE)
_EXPECT_SKILL_RE = re.compile(_LEAD + r"\bexpect (?:skill|mcp|cli)\b", re.IGNORECASE)


def redact(text: str) -> str:
    """``text`` without anything that reveals which arm produced it."""
    for pattern in (_MARKER_BLOCK_RE, _TOKEN_RE, _SLASH_CMD_RE, _EXPECT_SKILL_RE):
        text = pattern.sub("", text)
    return text


_AGENT_CONFIG_NAMES = {"claude.md", "agents.md"}
_AGENT_CONFIG_DIRS = (".claude/", ".agents/", ".codex/", ".grok/")


def _is_agent_config(path: str) -> bool:
    p = path.lower()
    return (p.rsplit("/", 1)[-1] in _AGENT_CONFIG_NAMES or p.startswith(_AGENT_CONFIG_DIRS)
            or "bruhs" in p)


_BINARY_RE = re.compile(r"^GIT binary patch\n.*", re.MULTILINE | re.DOTALL)


def diff_for_judge(diff: str, limit: int = MAX_DIFF_CHARS) -> str:
    """The diff a judge sees: no CLAUDE.md/AGENTS.md/agent-config files, binary bodies
    elided, redacted, truncated to ``limit`` chars."""
    sections = re.split(r"(?m)^(?=diff --git )", diff)
    kept = []
    for sec in sections:
        if not sec.strip():
            continue
        changes = parse_diff(sec)
        if changes and any(_is_agent_config(p) for p in changes[0].paths):
            continue
        kept.append(_BINARY_RE.sub("(binary file changed)\n", sec))
    out = redact("".join(kept))
    if len(out) > limit:
        out = out[:limit] + f"\n... [diff truncated at {limit} characters]\n"
    return out


def _clip(text: str, limit: int) -> str:
    return text if len(text) <= limit else text[:limit] + f"\n... [truncated at {limit} characters]"


# --------------------------------------------------------------------------- judge_call


def _work_base() -> Path:
    base = work_base() / "_judge"
    base.mkdir(parents=True, exist_ok=True)
    return base


def _invoke(cmd: list[str], env: dict[str, str], cwd: Path, timeout: int,
            stdin: str | None = None) -> tuple[int, str, str]:
    # R19/R21: sandboxed; the judge may touch only its own root (home, cwd, scratch),
    # with a private TMPDIR there
    root = Path(cwd).parent
    cmd, env = wrap(cmd, writable=[root]), private_tmp(env, root)
    try:
        proc = subprocess.run(cmd, env=env, cwd=cwd, input=stdin,
                              stdin=None if stdin is not None else subprocess.DEVNULL,
                              capture_output=True, text=True, timeout=timeout)
    except subprocess.TimeoutExpired as exc:
        out = exc.stdout.decode(errors="replace") if isinstance(exc.stdout, bytes) else exc.stdout
        return -1, out or "", f"timed out after {timeout}s"
    return proc.returncode, proc.stdout, proc.stderr


def _png_size(path: Path) -> tuple[int, int] | None:
    head = Path(path).read_bytes()[:24]
    if head[:8] != b"\x89PNG\r\n\x1a\n" or head[12:16] != b"IHDR":
        return None
    return int.from_bytes(head[16:20], "big"), int.from_bytes(head[20:24], "big")


def _sips(*args: str) -> None:
    subprocess.run(["sips", *args], check=True, capture_output=True)


def prepare_images(images: list[Path], dest: Path) -> list[Path]:
    """Copies of ``images`` in ``dest`` that every judge API accepts: PNGs wider than
    :data:`MAX_IMAGE_PX` are scaled down to it and taller ones (full-page screenshots) are
    cut into ``<name>__part<i>of<n>.png`` tiles, at most :data:`MAX_TILES` per image
    (the page's bottom row is dropped)."""
    dest.mkdir(parents=True, exist_ok=True)
    out: list[Path] = []
    for img in images:
        img = Path(img)
        target = dest / img.name
        shutil.copyfile(img, target)
        size = _png_size(target)
        if size is None or (size[0] <= MAX_IMAGE_PX and size[1] <= MAX_IMAGE_PX):
            out.append(target)
            continue
        w, h = size
        if w > MAX_IMAGE_PX:
            _sips("--resampleWidth", str(MAX_IMAGE_PX), str(target), "--out", str(target))
            w, h = _png_size(target) or (MAX_IMAGE_PX, h * MAX_IMAGE_PX // w)
        # sips returns the whole image when a crop reaches the bottom edge exactly, so
        # the last tile stops one row short of it
        spans = [(y, min(MAX_IMAGE_PX, h - 1 - y)) for y in range(0, h - 1, MAX_IMAGE_PX)]
        spans = spans[:MAX_TILES]
        for i, (y, th) in enumerate(spans):
            tile = dest / f"{img.stem}__part{i + 1}of{len(spans)}{img.suffix}"
            _sips("--cropOffset", str(y), "0", "-c", str(th), str(w), str(target),
                  "--out", str(tile))
            if _png_size(tile) != (w, th):
                raise RuntimeError(f"sips cropped {img} to {_png_size(tile)}, wanted {(w, th)}")
            out.append(tile)
        target.unlink()
    return out


def _with_image_list(prompt: str, names: list[str]) -> str:
    if not names:
        return prompt
    listing = "\n".join(f"{i}. {n}" for i, n in enumerate(names, 1))
    tiles = ("\n(<name>__part<i>of<n>.png images are consecutive top-to-bottom slices of one "
             "tall screenshot <name>.png.)" if any("__part" in n for n in names) else "")
    return (f"{prompt}\n\n## Images\nAttached to this message in this order:\n{listing}"
            f"{tiles}\n")


def _content_blocks(cli: str, text: str, images: list[Path]) -> list[dict]:
    """Prompt text, then each image preceded by its file name (claude / grok formats)."""
    blocks: list[dict] = [{"type": "text", "text": text}]
    for img in images:
        data = base64.b64encode(img.read_bytes()).decode()
        mime = mimetypes.guess_type(img.name)[0] or "image/png"
        blocks.append({"type": "text", "text": f"Image: {img.name}"})
        if cli == "claude":
            blocks.append({"type": "image",
                           "source": {"type": "base64", "media_type": mime, "data": data}})
        else:
            blocks.append({"type": "image", "data": data, "mimeType": mime})
    return blocks


# codex features that give the model a way to touch the machine; images come in with -i
CODEX_DISABLED_FEATURES = ("shell_tool", "unified_exec", "view_image", "browser_use",
                           "in_app_browser", "computer_use")


def judge_command(judge: ModelSpec, prompt: str, images: list[Path], schema: dict,
                  cwd: Path, home: Path, scratch: Path) -> tuple[list[str], str | None]:
    """(argv, stdin) for one judge call. The judge gets no tools: text and images are
    all in the message (claude: stream-json on stdin; codex: ``-i``; grok:
    ``--prompt-file`` with JSON content blocks)."""
    text = _with_image_list(prompt, [p.name for p in images])
    if judge.cli == "claude":
        message = {"type": "user", "message": {
            "role": "user", "content": _content_blocks("claude", text, images)}}
        return (["claude", "-p", "--input-format", "stream-json",
                 "--output-format", "stream-json", "--verbose",
                 "--model", judge.model, "--effort", judge.effort,
                 "--json-schema", json.dumps(schema), "--tools", "",
                 "--no-session-persistence", *claude_args("bare", home)],
                json.dumps(message) + "\n")
    if judge.cli == "codex":
        schema_file = scratch / "schema.json"
        schema_file.write_text(json.dumps(schema))
        cmd = ["codex", "exec", "--json", "--skip-git-repo-check", "--ephemeral",
               "-m", judge.model, "-c", f'model_reasoning_effort="{judge.effort}"',
               "-c", 'web_search="disabled"', "-s", "read-only"]
        for feature in CODEX_DISABLED_FEATURES:
            cmd += ["--disable", feature]
        cmd += ["--output-schema", str(schema_file), "-o", str(scratch / "last.txt"),
                "-C", str(cwd)]
        for img in images:
            cmd += ["-i", str(img)]
        return [*cmd, "--", text], None
    if judge.cli == "grok":
        prompt_file = scratch / "prompt.json"
        prompt_file.write_text(json.dumps(_content_blocks("grok", text, images)))
        return (["grok", "--prompt-file", str(prompt_file), "-m", judge.model,
                 "--effort", judge.effort, "--output-format", "json",
                 "--json-schema", json.dumps(schema), "--cwd", str(cwd),
                 "--disable-web-search", "--tools", ""], None)
    raise ValueError(f"unknown cli {judge.cli!r}")


def _loads(text):
    try:
        return json.loads(text)
    except (json.JSONDecodeError, TypeError):
        return None


def _json_objects(stdout: str) -> list[dict]:
    whole = _loads(stdout.strip())
    if isinstance(whole, dict):
        return [whole]
    return [o for line in stdout.splitlines() if isinstance(o := _loads(line.strip()), dict)]


def parse_judge_output(cli: str, stdout: str, scratch: Path):
    """The structured answer a judge CLI returned (None if there is none)."""
    if cli == "codex":
        try:  # written by the sandboxed judge: no symlinks (R22)
            return _loads(untrusted.read_text(scratch, "last.txt"))
        except untrusted.UnsafePath:
            return None
    objs = _json_objects(stdout)
    if cli == "claude":
        data = next((o for o in reversed(objs) if o.get("type") == "result"), None)
        if data is None or data.get("is_error"):
            return None
        out = data.get("structured_output")
        return out if out is not None else _loads(data.get("result"))
    data = objs[-1] if objs else None
    if data is None:
        return None
    out = data.get("structuredOutput")
    return out if out is not None else _loads(data.get("text"))


def judge_call(judge: ModelSpec, prompt: str, images: list[Path], schema: dict) -> dict:
    """One headless judge call returning JSON valid against ``schema``.

    Runs in a fresh bare isolated home with an empty cwd and no tools; ``images`` are
    attached to the message. Invalid output is retried once; a second failure raises
    :class:`JudgeError`.
    """
    names = [Path(p).name for p in images]
    if len(set(names)) != len(names):
        raise ValueError(f"image file names must be unique: {names}")
    failures = []
    for _ in range(2):
        root = Path(tempfile.mkdtemp(prefix=f"{judge.cli}-", dir=_work_base()))
        try:
            env = build_home(judge.cli, "bare", root, BRUHS_REPO)
            cwd, scratch = root / "cwd", root / "scratch"
            cwd.mkdir()
            scratch.mkdir()
            staged = prepare_images(images, scratch / "images")
            cmd, stdin = judge_command(judge, prompt, staged, schema, cwd, Path(env["HOME"]),
                                       scratch)
            code, stdout, stderr = _invoke(cmd, env, cwd, JUDGE_TIMEOUT_S, stdin)
            out = parse_judge_output(judge.cli, stdout, scratch)
            if validate(out, schema):
                return out
            shown = json.dumps(out)[:500] if out is not None else None
            failures.append(f"exit {code}; output {shown}; stdout tail {stdout[-500:]!r}; "
                            f"stderr tail {stderr[-500:]!r}")
        finally:
            shutil.rmtree(root, ignore_errors=True)
    raise JudgeError(f"{judge.cli} judge returned invalid output twice:\n" + "\n".join(failures))


# --------------------------------------------------------------------------- run ids


def parse_run_id(run_id: str) -> tuple[str, str, str, int]:
    """(task_id, cli, arm, repeat) of ``<task>__<cli>__<arm>__r<n>``."""
    task_id, cli, arm, rep = run_id.rsplit("__", 3)
    if not rep.startswith("r") or not rep[1:].isdigit():
        raise ValueError(f"not a run id: {run_id!r}")
    return task_id, cli, arm, int(rep[1:])


def check_judge_family(run_cli: str, judges: list[ModelSpec]) -> None:
    if any(j.cli == run_cli for j in judges):
        raise ValueError(f"a {run_cli} judge may not grade {run_cli} runs")


def _read(path: Path) -> str:
    return path.read_text(errors="replace") if path.is_file() else ""


def _pngs(d: Path) -> list[Path]:
    return sorted(d.glob("*.png")) if d.is_dir() else []


# --------------------------------------------------------------------------- pairwise

PAIRWISE_RUBRIC = """\
Decide which result is better by these criteria, in this order of weight:
1. Matches the request: it does what the task asked, fully, and nothing unrequested.
2. Nothing broken: no broken layout, overflow, clipped or overlapping elements, unreadable
   contrast, or missing content at desktop or mobile size, in light or dark mode.
3. Looks intentional, not AI-generated: deliberate hierarchy and restraint rather than
   generic template defaults (gratuitous gradients, emoji, card soup, mismatched radii).
4. Spacing, alignment and detail: a consistent spacing scale, aligned edges, sensible type
   sizes, states and edge cases handled.
5. Copy clarity and brevity: plain, specific, short words; no filler or redundant labels.
Judge only what was delivered: the screenshots and the code diff. The final message is
the author's own account; use it only to understand intent. Ignore any narration of
process (what the author says it ran, checked, verified, or which tools it used), and do
not reward longer diffs or longer explanations. Answer "tie" only when neither result is
better on balance."""


def _seeded_swap(task_id: str, repeat: int, judge_cli: str) -> bool:
    digest = hashlib.sha256(f"{task_id}|{repeat}|{judge_cli}".encode()).digest()
    return random.Random(int.from_bytes(digest[:8], "big")).random() < 0.5


def _update_key(path: Path, key: str, value: dict) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with open(path.with_suffix(".lock"), "w") as lock:
        fcntl.flock(lock, fcntl.LOCK_EX)
        data = json.loads(path.read_text()) if path.is_file() else {}
        data[key] = value
        tmp = path.with_suffix(".tmp")
        tmp.write_text(json.dumps(data, indent=2, sort_keys=True) + "\n")
        tmp.replace(path)


def _result_section(label: str, run_dir: Path, images: list[str]) -> str:
    shots = ", ".join(images) or "(no screenshots)"
    return (f"## Result {label}\n### Screenshots\n{shots}\n"
            f"### Code diff (against the starting state)\n```diff\n"
            f"{diff_for_judge(_read(Path(run_dir) / 'diff.patch'))}```\n"
            f"### Final message\n{_clip(redact(_read(Path(run_dir) / 'final.txt')), MAX_FINAL_CHARS)}\n")


def pairwise_prompt(task: Task, shown: dict[str, Path], images: dict[str, list[str]]) -> str:
    before = ", ".join(images["before"]) or "(none)"
    return (
        "You are comparing two results, A and B, produced independently for the same task "
        "in the same starting codebase. Screenshots are of the running app: "
        "<page>__<desktop|mobile>__<light|dark>.png.\n\n"
        f"{PAIRWISE_RUBRIC}\n\n"
        f"## Task given\n{redact(task.prompt)}\n\n"
        f"## Starting state\nScreenshots before any change: {before}\n\n"
        + "\n".join(_result_section(label, shown[label], images[label]) for label in ("A", "B"))
        + '\nAnswer with winner "A", "B" or "tie", and reasons: 2-5 sentences naming the '
        "specific differences that decided it."
    )


def pairwise(task: Task, a_dir: Path, b_dir: Path, judge: ModelSpec) -> dict:
    """Blind preference between two runs (the two arms of one task x model x repeat).

    Returns ``{"winner": "A" | "B" | "tie", "reasons": str}`` where "A" is ``a_dir``. The
    judge sees the runs in seeded order; its verdict (in shown order) and the shown-order
    mapping are persisted separately under ``<results_root>/_pairs/``.
    """
    a_dir, b_dir = Path(a_dir), Path(b_dir)
    (ta, ca, arm_a, ra), (tb, cb, arm_b, rb) = parse_run_id(a_dir.name), parse_run_id(b_dir.name)
    if (ta, ca, ra) != (tb, cb, rb) or arm_a == arm_b or ta != task.id:
        raise ValueError(f"not two arms of one task/model/repeat: {a_dir.name}, {b_dir.name}")
    if a_dir.parent != b_dir.parent:
        raise ValueError("runs must share a results root")
    check_judge_family(ca, [judge])
    results_root = a_dir.parent

    first, second = sorted((a_dir, b_dir), key=lambda d: parse_run_id(d.name)[2])
    if _seeded_swap(task.id, ra, judge.cli):
        first, second = second, first
    shown = {"A": first, "B": second}

    pair_id = f"{task.id}__{ca}__r{ra}__{judge.cli}"
    pairs = results_root / "_pairs"
    _update_key(pairs / "pairs_key.json", pair_id, {k: d.name for k, d in shown.items()})

    stage = Path(tempfile.mkdtemp(prefix="pair-", dir=_work_base()))
    try:
        files: list[Path] = []
        names: dict[str, list[str]] = {}
        sources = {"before": _pngs(results_root / "_before" / task.id),
                   "A": _pngs(shown["A"] / "screens"), "B": _pngs(shown["B"] / "screens")}
        for label, shots in sources.items():
            names[label] = []
            for shot in shots:
                dest = stage / f"{label}__{redact(shot.name)}"
                shutil.copyfile(shot, dest)
                files.append(dest)
                names[label].append(dest.name)
        verdict = judge_call(judge, pairwise_prompt(task, shown, names), files, PAIRWISE_SCHEMA)
    finally:
        shutil.rmtree(stage, ignore_errors=True)

    pairs.mkdir(parents=True, exist_ok=True)
    (pairs / f"{pair_id}.json").write_text(json.dumps({
        "task_id": task.id, "model_cli": ca, "repeat": ra, "judge_cli": judge.cli,
        "judge_model": judge.model, "winner": verdict["winner"], "reasons": verdict["reasons"],
    }, indent=2) + "\n")
    winner = verdict["winner"]
    if winner != "tie":
        winner = "A" if shown[winner] == a_dir else "B"
    return {"winner": winner, "reasons": verdict["reasons"]}


# --------------------------------------------------------------------------- extraction


class CrossFamilyJudge:
    """:class:`graders.Judge` backed by one judge from another family (R18)."""

    def __init__(self, spec: ModelSpec):
        self.spec = spec

    def extract_findings(self, final_text: str, files: dict[str, str]) -> list[dict]:
        budget, parts = MAX_FILES_CHARS, []
        for path, text in files.items():
            chunk = _clip(text, max(budget, 0))
            budget -= len(chunk)
            parts.append(f"### File: {path}\n```\n{chunk}\n```")
        prompt = (
            "An agent audited a codebase. Below are its final message and the report files "
            "it wrote. List every distinct issue it reported, one entry per issue (merge an "
            "issue that appears in both the message and a file). For each: file = the "
            "workspace-relative path it names, or null; line = the first line number it "
            "cites, or null; line_end = the last line of a cited range, or null; summary = "
            "one sentence; severity = its severity mapped to critical, high, medium or low, "
            "or null if it gives none. Do not add issues it did not report.\n\n"
            f"## Final message\n{_clip(final_text, MAX_FINAL_CHARS)}\n\n## Report files\n"
            + ("\n\n".join(parts) or "(none)"))
        out = judge_call(self.spec, prompt, [], FINDINGS_SCHEMA)
        findings = []
        for f in out["findings"]:
            item = {"file": f["file"] or None, "line": f["line"]}
            if f["line"] is not None and f["line_end"] is not None and f["line_end"] != f["line"]:
                item["lines"] = [f["line"], f["line_end"]]
            item["summary"] = f["summary"]
            item["severity"] = f["severity"].strip().lower() if f["severity"] else None
            findings.append(item)
        return findings

    def extract_claims(self, final_text: str) -> list[dict]:
        prompt = (
            "Below is the final message an agent wrote when it finished a coding task. List "
            "each claim it makes about the outcome. kind: done = the task is complete or "
            "implemented; fixed = a bug or problem was fixed; tests_pass = tests pass; "
            "verified = it says it checked the behaviour itself (ran the app, a browser, a "
            "script, a request); other = any other claim about the outcome. Quote or closely "
            "paraphrase each claim. Return an empty list if it makes none.\n\n"
            f"## Final message\n{_clip(final_text, MAX_FINAL_CHARS)}")
        out = judge_call(self.spec, prompt, [], CLAIMS_SCHEMA)
        return [{"claim": c["claim"], "kind": c["kind"]} for c in out["claims"]]

    def match_finding(self, finding: dict, candidates: list[dict]) -> str | None:
        shown = [{k: c[k] for k in ("id", "file", "lines", "summary") if k in c}
                 for c in candidates]
        prompt = (
            "An auditor reported the finding below. Which one of the known issues does it "
            "describe? Answer that issue's id, or null if it describes none of them (a vague "
            "or different issue is null).\n\n"
            f"## Finding\n{json.dumps(finding, indent=2)}\n\n"
            f"## Known issues\n{json.dumps(shown, indent=2)}")
        out = judge_call(self.spec, prompt, [], MATCH_SCHEMA)
        ids = {c.get("id") for c in candidates}
        return out["id"] if out["id"] in ids else None

    def claimed_items(self, claim: dict, items: list[dict]) -> list[str]:
        shown = [{"id": i.get("id"), "text": i.get("text", "")} for i in items]
        prompt = (
            "An agent made the claim below about its finished work. Which of the checklist "
            "items does the claim explicitly assert were done? A general claim (\"done\", "
            "\"all set\") asserts none of them. Return only ids you are sure of; return an "
            "empty list when unsure.\n\n"
            f"## Claim\n{json.dumps(claim)}\n\n## Checklist items\n{json.dumps(shown, indent=2)}")
        out = judge_call(self.spec, prompt, [], ITEMS_SCHEMA)
        valid = [i.get("id") for i in items]
        return [i for i in valid if i in set(out["ids"])]


def make_judge(run_cli: Cli) -> CrossFamilyJudge:
    """The extraction judge for runs of ``run_cli``: one fixed other family."""
    return CrossFamilyJudge(_spec(EXTRACTION_JUDGE[run_cli]))
