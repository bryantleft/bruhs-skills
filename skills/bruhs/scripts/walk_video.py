#!/usr/bin/env python3
"""walk_video.py — render a narrated PR walkthrough video from a scene script.

The agent writes the script (intent → change → implications → validation);
this script checks it, narrates it with a local text-to-speech engine, and
renders a 1920x1080 MP4 with burned-in captions using ffmpeg + libass.

Usage:
    python3 walk_video.py engines [--voice PATH]
    python3 walk_video.py check  SCRIPT.json [--tts ENGINE] [--voice PATH]
    python3 walk_video.py render SCRIPT.json --out DIR [--tts ENGINE]
                                 [--voice PATH] [--say-voice NAME]
                                 [--no-burn-captions] [--keep-work]

ENGINE is auto (default), piper, say, espeak-ng or none. auto picks the first
available in that order. none renders a silent, captions-only video.

Exit codes: 0 ok, 2 usage or script validation error, 3 a required tool or
voice is missing, 4 ffmpeg or the TTS engine failed while rendering.
"""

from __future__ import annotations

import argparse
import json
import os
import re
import shutil
import subprocess
import sys
import textwrap
import wave
from pathlib import Path
from typing import Dict, List, Optional, Sequence, Tuple

EXIT_OK = 0
EXIT_INVALID = 2
EXIT_MISSING_TOOL = 3
EXIT_RENDER_FAILED = 4

KINDS = ("intent", "change", "implications", "validation")
KIND_LABEL = {
    "intent": "WHY",
    "change": "WHAT CHANGED",
    "implications": "WHAT IT AFFECTS",
    "validation": "HOW WE KNOW",
}
STATUSES = ("shown", "intended", "unchecked")
STATUS_LABEL = {"shown": "SHOWN", "intended": "INTENDED", "unchecked": "NOT CHECKED"}
VISUAL_TYPES = ("title", "points", "code", "diff", "image", "video", "claims")
ENGINES = ("piper", "say", "espeak-ng", "none")

# ── Layout (1920x1080; every capacity below is derived from these) ──────────
WIDTH, HEIGHT, FPS = 1920, 1080, 30
MARGIN_X = 96
CONTENT_W = WIDTH - 2 * MARGIN_X
KIND_Y, HEADING_Y = 64, 104
CONTENT_TOP, CONTENT_BOTTOM = 230, 820
CONTENT_H = CONTENT_BOTTOM - CONTENT_TOP
CAPTION_MARGIN_V = 56

# Average advance per em, used to wrap text before libass draws it.
# Monospace: Menlo and DejaVu Sans Mono both advance 0.602 em (both descend
# from Bitstream Vera). Proportional: Helvetica Neue prose measured 0.39 em per
# character in a rendered frame (64 chars ≈ 1150 px at 46 px); 0.47 leaves room
# for capitals and wide glyphs. DejaVu Sans runs wider, so Linux gets 0.55.
MONO_EM = 0.602
PROP_EM = 0.47 if sys.platform == "darwin" else 0.55

HEADING_SIZE = 60
HEADING_MAX_CHARS = int(CONTENT_W / (PROP_EM * HEADING_SIZE))
TITLE_SIZE, TITLE_LINE_H, TITLE_MAX_LINES = 72, 88, 3
POINT_SIZE, POINT_LINE_H, POINT_GAP, POINT_INDENT = 46, 58, 22, 56
CODE_SIZE, CODE_LINE_H = 30, 37
CODE_TOP = CONTENT_TOP + 50  # path label sits above the code
CODE_MAX_LINES = (CONTENT_BOTTOM - CODE_TOP) // CODE_LINE_H
CODE_MAX_COLS = int(CONTENT_W / (MONO_EM * CODE_SIZE))
CLAIM_TAG_W = 300
CLAIM_SIZE, CLAIM_LINE_H = 40, 50
RECEIPT_SIZE, RECEIPT_LINE_H = 26, 36
CLAIM_GAP = 26
CAPTION_SIZE = 42
# Captions stay narrower than the frame so a line reads in one glance.
CAPTION_CHARS = 64

# Narration pacing. 2.6 words/s was measured on piper en_US-lessac-medium
# (6 words → 2.26 s); used only to estimate length before audio exists and to
# time the captions-only (none) engine.
WORDS_PER_SECOND = 2.6
LEAD_IN_S, SENTENCE_GAP_S, TAIL_S = 0.4, 0.25, 0.7
# The command doc's target for a walkthrough; longer gets a warning, not an error.
TARGET_MAX_SECONDS = 90

SAMPLE_RATE, CHANNELS, SAMPLE_WIDTH = 48000, 2, 2

COLORS = {
    "bg": "0f1115",
    "text": "e6e6e6",
    "muted": "8b93a1",
    "intent": "7aa2f7",
    "change": "9ece6a",
    "implications": "e0af68",
    "validation": "bb9af7",
    "add": "9ece6a",
    "del": "f7768e",
    "hunk": "7dcfff",
    "shown": "9ece6a",
    "intended": "e0af68",
    "unchecked": "8b93a1",
}


class WalkVideoError(Exception):
    def __init__(self, message: str, code: int) -> None:
        super().__init__(message)
        self.code = code


# ── Script validation ───────────────────────────────────────────────────────


def wrap(text: str, width: int) -> List[str]:
    return textwrap.wrap(text, width=width, break_long_words=True, break_on_hyphens=False) or [""]


def split_sentences(narration: str) -> List[str]:
    text = " ".join(narration.split())
    parts = re.split(r"(?<=[.!?])\s+(?=[A-Z0-9\"'(\[])", text)
    return [p for p in parts if p]


def word_count(text: str) -> int:
    return len(text.split())


def estimate_seconds(narration: str) -> float:
    sentences = split_sentences(narration)
    speech = sum(word_count(s) for s in sentences) / WORDS_PER_SECOND
    return LEAD_IN_S + speech + SENTENCE_GAP_S * max(0, len(sentences) - 1) + TAIL_S


def expand_code(text: str) -> List[str]:
    return [line.expandtabs(4).rstrip() for line in text.rstrip("\n").split("\n")]


def points_height(items: Sequence[str]) -> int:
    width = int((CONTENT_W - POINT_INDENT) / (PROP_EM * POINT_SIZE))
    lines = sum(len(wrap(item, width)) for item in items)
    return lines * POINT_LINE_H + POINT_GAP * max(0, len(items) - 1)


def claims_height(claims: Sequence[dict]) -> int:
    width = int((CONTENT_W - CLAIM_TAG_W) / (PROP_EM * CLAIM_SIZE))
    total = 0
    for claim in claims:
        total += len(wrap(str(claim.get("text", "")), width)) * CLAIM_LINE_H
        if claim.get("receipt"):
            total += RECEIPT_LINE_H
    return total + CLAIM_GAP * max(0, len(claims) - 1)


def _nonempty_str(value: object) -> bool:
    return isinstance(value, str) and value.strip() != ""


def validate_script(script: object, base_dir: Path) -> Tuple[List[str], List[str]]:
    """Return (errors, warnings). Errors block rendering; warnings don't."""
    errors: List[str] = []
    warnings: List[str] = []
    if not isinstance(script, dict):
        return ["the script must be a JSON object with a \"scenes\" array"], warnings

    pr = script.get("pr", {})
    if not isinstance(pr, dict):
        errors.append("\"pr\" must be an object (number, title, base, head, additions, deletions, files)")
        pr = {}

    scenes = script.get("scenes")
    if not isinstance(scenes, list) or not scenes:
        errors.append("\"scenes\" must be a non-empty array")
        return errors, warnings

    last_rank = -1
    kinds_seen: List[str] = []
    total_seconds = 0.0
    for i, scene in enumerate(scenes, start=1):
        where = f"scene {i}"
        if not isinstance(scene, dict):
            errors.append(f"{where}: must be an object")
            continue
        kind = scene.get("kind")
        if kind not in KINDS:
            errors.append(f"{where}: kind must be one of {', '.join(KINDS)} (got {kind!r})")
            continue
        where = f"scene {i} ({kind})"
        kinds_seen.append(kind)
        rank = KINDS.index(kind)
        if rank < last_rank:
            errors.append(
                f"{where}: scenes must run intent → change → implications → validation; "
                f"this {kind} scene comes after a {KINDS[last_rank]} scene"
            )
        last_rank = max(last_rank, rank)

        heading = scene.get("heading")
        if not _nonempty_str(heading):
            errors.append(f"{where}: \"heading\" must be a non-empty string")
        elif len(heading) > HEADING_MAX_CHARS:
            errors.append(
                f"{where}: heading is {len(heading)} chars; one line holds {HEADING_MAX_CHARS}. Shorten it"
            )

        narration = scene.get("narration")
        if not _nonempty_str(narration):
            errors.append(f"{where}: \"narration\" must be a non-empty string (it is spoken and captioned)")
        else:
            total_seconds += estimate_seconds(narration)
            if "`" in narration:
                warnings.append(
                    f"{where}: narration contains backticks; the voice reads it literally and the "
                    "caption shows them. Write code names the way you would say them"
                )

        claims = scene.get("claims")
        if kind != "validation" and claims is not None:
            errors.append(f"{where}: only the validation scene carries \"claims\"")

        visual = scene.get("visual")
        if not isinstance(visual, dict) or visual.get("type") not in VISUAL_TYPES:
            errors.append(f"{where}: \"visual.type\" must be one of {', '.join(VISUAL_TYPES)}")
            continue
        errors.extend(_validate_visual(where, kind, visual, claims, pr, base_dir))

    if kinds_seen and kinds_seen[0] != "intent":
        errors.append("the first scene must be an intent scene: say why the PR exists before what it does")
    if "change" not in kinds_seen:
        errors.append("add at least one change scene showing what the PR does")
    if kinds_seen and kinds_seen[-1] != "validation":
        errors.append("the last scene must be a validation scene listing what was shown, intended and not checked")
    if kinds_seen.count("validation") > 1:
        errors.append("use one validation scene; put every claim in it")

    if total_seconds > TARGET_MAX_SECONDS:
        warnings.append(
            f"estimated length is {total_seconds:.0f}s, over the {TARGET_MAX_SECONDS}s target. "
            "Cut narration unless the PR needs it"
        )
    return errors, warnings


def _validate_visual(
    where: str, kind: str, visual: dict, claims: object, pr: dict, base_dir: Path
) -> List[str]:
    errors: List[str] = []
    vtype = visual["type"]
    if kind == "validation" and vtype != "claims":
        errors.append(f"{where}: the validation scene's visual must be {{\"type\": \"claims\"}}")
    if vtype == "claims" and kind != "validation":
        errors.append(f"{where}: a claims visual belongs only in the validation scene")

    if vtype == "title":
        if not _nonempty_str(pr.get("title")):
            errors.append(f"{where}: a title visual needs \"pr.title\"")
        else:
            lines = wrap(pr["title"], int(CONTENT_W / (PROP_EM * TITLE_SIZE)))
            if len(lines) > TITLE_MAX_LINES:
                errors.append(f"{where}: pr.title wraps to {len(lines)} lines; the title card holds {TITLE_MAX_LINES}")
    elif vtype == "points":
        items = visual.get("items")
        if not isinstance(items, list) or not items or not all(_nonempty_str(x) for x in items):
            errors.append(f"{where}: a points visual needs \"items\": a non-empty array of strings")
        elif points_height(items) > CONTENT_H:
            errors.append(
                f"{where}: the points need {points_height(items)}px; the slide holds {CONTENT_H}px. "
                "Use fewer or shorter items"
            )
    elif vtype in ("code", "diff"):
        text = visual.get("text")
        if not _nonempty_str(text):
            errors.append(f"{where}: a {vtype} visual needs \"text\"")
        else:
            lines = expand_code(text)
            if len(lines) > CODE_MAX_LINES:
                errors.append(
                    f"{where}: {len(lines)} lines of {vtype}; the slide holds {CODE_MAX_LINES}. "
                    "Trim to the lines the narration talks about"
                )
            widest = max(len(line) for line in lines)
            if widest > CODE_MAX_COLS:
                errors.append(
                    f"{where}: a {vtype} line is {widest} columns; the slide holds {CODE_MAX_COLS}. "
                    "Reflow or cut that line"
                )
        if "start_line" in visual and not (isinstance(visual["start_line"], int) and visual["start_line"] >= 1):
            errors.append(f"{where}: \"start_line\" must be a positive integer")
    elif vtype in ("image", "video"):
        src = visual.get("src")
        if not _nonempty_str(src):
            errors.append(f"{where}: an {vtype} visual needs \"src\"")
        elif not resolve_src(src, base_dir).is_file():
            errors.append(f"{where}: {vtype} file not found: {resolve_src(src, base_dir)}")
        start = visual.get("start", 0)
        if vtype == "video" and (not isinstance(start, (int, float)) or start < 0):
            errors.append(f"{where}: \"start\" must be a number of seconds ≥ 0")
    elif vtype == "claims":
        errors.extend(_validate_claims(where, claims))
    return errors


def _validate_claims(where: str, claims: object) -> List[str]:
    errors: List[str] = []
    if not isinstance(claims, list) or not claims:
        return [f"{where}: the validation scene needs \"claims\": what was shown, what is intended, what was not checked"]
    for j, claim in enumerate(claims, start=1):
        cwhere = f"{where} claim {j}"
        if not isinstance(claim, dict):
            errors.append(f"{cwhere}: must be an object with text, status and receipt")
            continue
        if not _nonempty_str(claim.get("text")):
            errors.append(f"{cwhere}: \"text\" must be a non-empty string")
        status = claim.get("status")
        if status not in STATUSES:
            errors.append(f"{cwhere}: status must be one of {', '.join(STATUSES)} (got {status!r})")
        elif status == "shown" and not _nonempty_str(claim.get("receipt")):
            errors.append(
                f"{cwhere}: a shown claim needs a \"receipt\" (the command and its result, a CI check, "
                "or an artifact path). Without one, mark it intended or unchecked"
            )
        if "receipt" in claim and claim["receipt"] is not None and not isinstance(claim["receipt"], str):
            errors.append(f"{cwhere}: \"receipt\" must be a string")
    if not errors and claims_height(claims) > CONTENT_H:
        errors.append(
            f"{where}: the claims need {claims_height(claims)}px; the slide holds {CONTENT_H}px. "
            "Merge or shorten claims; the transcript keeps the full receipts"
        )
    return errors


def resolve_src(src: str, base_dir: Path) -> Path:
    path = Path(src).expanduser()
    return path if path.is_absolute() else (base_dir / path)


# ── TTS engines ─────────────────────────────────────────────────────────────


def default_voice_dir() -> Path:
    data_home = os.environ.get("XDG_DATA_HOME") or str(Path.home() / ".local" / "share")
    return Path(data_home) / "bruhs" / "voices"


def find_piper_voice(voice_arg: Optional[str]) -> Optional[Path]:
    if voice_arg:
        return Path(voice_arg).expanduser()
    env = os.environ.get("BRUHS_PIPER_VOICE")
    if env:
        return Path(env).expanduser()
    voices = sorted(default_voice_dir().glob("*.onnx"))
    return voices[0] if voices else None


def detect_engines(voice_arg: Optional[str]) -> Dict[str, dict]:
    piper_bin = shutil.which("piper")
    voice = find_piper_voice(voice_arg)
    voice_ok = voice is not None and voice.is_file()
    if piper_bin and voice_ok:
        piper_detail = f"{piper_bin} with {voice}"
    elif not piper_bin:
        piper_detail = "piper not on PATH (uv tool install piper-tts)"
    else:
        piper_detail = (
            f"voice not found at {voice}" if voice else f"no .onnx voice in {default_voice_dir()} or BRUHS_PIPER_VOICE"
        )
    espeak = shutil.which("espeak-ng")
    say = shutil.which("say")
    return {
        "piper": {"available": bool(piper_bin and voice_ok), "detail": piper_detail,
                  "bin": piper_bin, "voice": str(voice) if voice else None},
        "say": {"available": bool(say), "detail": say or "say not found (macOS only)", "bin": say},
        "espeak-ng": {"available": bool(espeak), "detail": espeak or "espeak-ng not on PATH", "bin": espeak},
        "none": {"available": True, "detail": "silent video, captions only"},
    }


def choose_engine(requested: str, engines: Dict[str, dict]) -> Tuple[str, List[str]]:
    notes: List[str] = []
    if requested != "auto":
        if not engines[requested]["available"]:
            raise WalkVideoError(
                f"TTS engine {requested} is not available: {engines[requested]['detail']}", EXIT_MISSING_TOOL
            )
        return requested, notes
    for name in ENGINES:
        if engines[name]["available"]:
            if name != "piper":
                notes.append(f"piper unavailable ({engines['piper']['detail']}); using {name}")
            if name == "none":
                notes.append("no local voice found: rendering a silent, captions-only video")
            return name, notes
    raise AssertionError("the none engine is always available")


def run(cmd: Sequence[str], *, cwd: Optional[Path] = None, stdin: Optional[str] = None,
        failure: str = "command failed") -> subprocess.CompletedProcess:
    proc = subprocess.run(
        list(cmd), cwd=str(cwd) if cwd else None, input=stdin, capture_output=True, text=True
    )
    if proc.returncode != 0:
        tail = "\n".join((proc.stderr or proc.stdout).strip().splitlines()[-15:])
        raise WalkVideoError(f"{failure} (exit {proc.returncode}): {' '.join(cmd[:3])} …\n{tail}", EXIT_RENDER_FAILED)
    return proc


def synthesize(engine: str, engines: Dict[str, dict], text: str, raw: Path, say_voice: Optional[str]) -> None:
    text_file = raw.with_suffix(".txt")
    text_file.write_text(text + "\n", encoding="utf-8")
    if engine == "piper":
        run([engines["piper"]["bin"], "-m", engines["piper"]["voice"], "-f", str(raw)],
            stdin=text + "\n", failure="piper failed")
    elif engine == "say":
        cmd = [engines["say"]["bin"], "-o", str(raw), "-f", str(text_file)]
        if say_voice:
            cmd[1:1] = ["-v", say_voice]
        run(cmd, failure="say failed")
    elif engine == "espeak-ng":
        run([engines["espeak-ng"]["bin"], "-w", str(raw), "-f", str(text_file)], failure="espeak-ng failed")
    else:
        raise AssertionError(f"synthesize called for {engine}")


def normalize_audio(raw: Path, out: Path) -> None:
    run(["ffmpeg", "-v", "error", "-y", "-i", str(raw), "-ar", str(SAMPLE_RATE), "-ac", str(CHANNELS),
         "-c:a", "pcm_s16le", str(out)], failure="ffmpeg could not convert the narration audio")


def silence(seconds: float) -> bytes:
    return b"\x00" * (int(round(seconds * SAMPLE_RATE)) * CHANNELS * SAMPLE_WIDTH)


def read_frames(path: Path) -> bytes:
    with wave.open(str(path), "rb") as w:
        if (w.getframerate(), w.getnchannels(), w.getsampwidth()) != (SAMPLE_RATE, CHANNELS, SAMPLE_WIDTH):
            raise WalkVideoError(f"unexpected audio format in {path}", EXIT_RENDER_FAILED)
        return w.readframes(w.getnframes())


def frames_seconds(data: bytes) -> float:
    return len(data) / (SAMPLE_RATE * CHANNELS * SAMPLE_WIDTH)


# ── ASS subtitle drawing ────────────────────────────────────────────────────


def ass_color(hex_rgb: str, alpha: int = 0) -> str:
    r, g, b = hex_rgb[0:2], hex_rgb[2:4], hex_rgb[4:6]
    return f"&H{alpha:02X}{b}{g}{r}".upper()


def ass_text(text: str, keep_spaces: bool = False) -> str:
    # A word joiner after each backslash stops libass reading \n, \N, \h or \{
    # in the source as an escape; braces are escaped so they never open an
    # override block.
    out = text.replace("\\", "\\⁠").replace("{", "\\{").replace("}", "\\}")
    if keep_spaces:
        out = re.sub(r" {2,}|^ ", lambda m: "\\h" * len(m.group(0)), out)
    return out


def ass_time(seconds: float) -> str:
    cs = int(round(seconds * 100))
    h, rem = divmod(cs, 360000)
    m, rem = divmod(rem, 6000)
    s, cs = divmod(rem, 100)
    return f"{h}:{m:02d}:{s:02d}.{cs:02d}"


def srt_time(seconds: float) -> str:
    ms = int(round(seconds * 1000))
    h, rem = divmod(ms, 3600000)
    m, rem = divmod(rem, 60000)
    s, ms = divmod(rem, 1000)
    return f"{h:02d}:{m:02d}:{s:02d},{ms:03d}"


def fonts() -> Tuple[str, str]:
    if sys.platform == "darwin":
        return "Helvetica Neue", "Menlo"
    return "DejaVu Sans", "DejaVu Sans Mono"


def ass_header() -> str:
    sans, mono = fonts()
    fmt = ("Format: Name, Fontname, Fontsize, PrimaryColour, SecondaryColour, OutlineColour, BackColour, "
           "Bold, Italic, Underline, StrikeOut, ScaleX, ScaleY, Spacing, Angle, BorderStyle, Outline, Shadow, "
           "Alignment, MarginL, MarginR, MarginV, Encoding")
    text, box = ass_color(COLORS["text"]), ass_color("000000", 0x50)

    def style(name: str, font: str, size: int, bold: int = 0, border: int = 1, outline: int = 0,
              align: int = 7, margin_v: int = 0, outline_colour: str = "&H00000000") -> str:
        return (f"Style: {name},{font},{size},{text},{text},{outline_colour},{box},{bold},0,0,0,100,100,0,0,"
                f"{border},{outline},0,{align},{MARGIN_X},{MARGIN_X},{margin_v},1")

    return "\n".join([
        "[Script Info]", "ScriptType: v4.00+", f"PlayResX: {WIDTH}", f"PlayResY: {HEIGHT}",
        "WrapStyle: 2", "ScaledBorderAndShadow: yes", "",
        "[V4+ Styles]", fmt,
        style("Sans", sans, 40),
        style("Mono", mono, CODE_SIZE),
        style("Caption", sans, CAPTION_SIZE, border=3, outline=14, align=2,
              margin_v=CAPTION_MARGIN_V, outline_colour=box),
        "", "[Events]",
        "Format: Layer, Start, End, Style, Name, MarginL, MarginR, MarginV, Effect, Text",
    ])


class AssScene:
    def __init__(self, duration: float) -> None:
        self.duration = duration
        self.events: List[str] = []

    def text(self, x: int, y: int, body: str, *, style: str = "Sans", size: Optional[int] = None,
             color: str = "text", bold: bool = False, align: int = 7, start: float = 0.0,
             end: Optional[float] = None, layer: int = 1, extra: str = "") -> None:
        tags = f"\\an{align}\\pos({x},{y})\\c{ass_color(COLORS.get(color, color))}"
        if size:
            tags += f"\\fs{size}"
        if bold:
            tags += "\\b1"
        stop = self.duration if end is None else end
        self.events.append(
            f"Dialogue: {layer},{ass_time(start)},{ass_time(stop)},{style},,0,0,0,,{{{tags}{extra}}}{body}"
        )

    def caption(self, body: str, start: float, end: float) -> None:
        self.events.append(f"Dialogue: 5,{ass_time(start)},{ass_time(end)},Caption,,0,0,0,,{body}")

    def render(self) -> str:
        return ass_header() + "\n" + "\n".join(self.events) + "\n"


def draw_header(ass: AssScene, scene: dict, pr: dict) -> None:
    kind = scene["kind"]
    label = KIND_LABEL[kind]
    if pr.get("number"):
        label = f"PR #{pr['number']}  ·  {label}"
    ass.text(MARGIN_X, KIND_Y, ass_text(label), size=28, color=kind, bold=True)
    ass.text(MARGIN_X, HEADING_Y, ass_text(scene["heading"]), size=HEADING_SIZE, bold=True)


def draw_visual(ass: AssScene, scene: dict, pr: dict) -> None:
    visual = scene["visual"]
    vtype = visual["type"]
    if vtype == "title":
        width = int(CONTENT_W / (PROP_EM * TITLE_SIZE))
        y = CONTENT_TOP + 40
        for line in wrap(pr["title"], width):
            ass.text(MARGIN_X, y, ass_text(line), size=TITLE_SIZE, bold=True)
            y += TITLE_LINE_H
        meta = []
        if pr.get("base") and pr.get("head"):
            meta.append(f"{pr['base']} ← {pr['head']}")
        if isinstance(pr.get("additions"), int) and isinstance(pr.get("deletions"), int):
            meta.append(f"+{pr['additions']} / −{pr['deletions']}")
        if isinstance(pr.get("files"), int):
            meta.append(f"{pr['files']} files")
        if meta:
            ass.text(MARGIN_X, y + 30, ass_text("   ·   ".join(meta)), size=36, color="muted")
    elif vtype == "points":
        width = int((CONTENT_W - POINT_INDENT) / (PROP_EM * POINT_SIZE))
        y = CONTENT_TOP
        for item in visual["items"]:
            ass.text(MARGIN_X, y, "•", size=POINT_SIZE, color=scene["kind"], bold=True)
            for line in wrap(item, width):
                ass.text(MARGIN_X + POINT_INDENT, y, ass_text(line), size=POINT_SIZE)
                y += POINT_LINE_H
            y += POINT_GAP
    elif vtype in ("code", "diff"):
        label = visual.get("path", "")
        if label and visual.get("start_line"):
            label = f"{label}:{visual['start_line']}"
        if label:
            ass.text(MARGIN_X, CONTENT_TOP, ass_text(label), style="Mono", size=28, color="muted")
        y = CODE_TOP
        for line in expand_code(visual["text"]):
            color = "text"
            if vtype == "diff":
                if line.startswith("@@"):
                    color = "hunk"
                elif line.startswith("+"):
                    color = "add"
                elif line.startswith("-"):
                    color = "del"
            if line:
                ass.text(MARGIN_X, y, ass_text(line, keep_spaces=True), style="Mono", color=color)
            y += CODE_LINE_H
    elif vtype == "claims":
        width = int((CONTENT_W - CLAIM_TAG_W) / (PROP_EM * CLAIM_SIZE))
        receipt_cols = int((CONTENT_W - CLAIM_TAG_W) / (MONO_EM * RECEIPT_SIZE))
        y = CONTENT_TOP
        for claim in scene["claims"]:
            status = claim["status"]
            ass.text(MARGIN_X, y + 4, ass_text(STATUS_LABEL[status]), size=30, color=status, bold=True)
            for line in wrap(claim["text"], width):
                ass.text(MARGIN_X + CLAIM_TAG_W, y, ass_text(line), size=CLAIM_SIZE)
                y += CLAIM_LINE_H
            receipt = " ".join((claim.get("receipt") or "").split())
            if receipt:
                if len(receipt) > receipt_cols:
                    receipt = receipt[: receipt_cols - 1] + "…"
                ass.text(MARGIN_X + CLAIM_TAG_W, y, ass_text(receipt), style="Mono", size=RECEIPT_SIZE,
                         color="muted")
                y += RECEIPT_LINE_H
            y += CLAIM_GAP
    # image and video visuals are composited by ffmpeg under the overlay


def caption_chunks(sentence: str) -> List[str]:
    """Split a sentence into captions of at most two lines, evenly sized so the
    last caption is never a lone word."""
    count = -(-len(wrap(sentence, CAPTION_CHARS)) // 2)
    target = len(sentence) / count
    groups: List[List[str]] = [[]]
    used = 0
    for word in sentence.split():
        if groups[-1] and used + len(word) > target * len(groups) and len(groups) < count:
            groups.append([])
        groups[-1].append(word)
        used += len(word) + 1
    return ["\n".join(balanced_lines(" ".join(g))) for g in groups]


def balanced_lines(text: str) -> List[str]:
    """Wrap to the fewest lines CAPTION_CHARS allows, with even line lengths."""
    lines = wrap(text, CAPTION_CHARS)
    width = -(-len(text) // len(lines))
    while width < CAPTION_CHARS:
        candidate = wrap(text, width)
        if len(candidate) == len(lines):
            return candidate
        width += 1
    return lines


# ── Rendering ───────────────────────────────────────────────────────────────


def preflight_ffmpeg() -> None:
    for tool in ("ffmpeg", "ffprobe"):
        if not shutil.which(tool):
            raise WalkVideoError(
                f"{tool} not on PATH. Install ffmpeg (macOS: brew install ffmpeg; Debian/Ubuntu: "
                "apt install ffmpeg) and rerun", EXIT_MISSING_TOOL)
    filters = subprocess.run(["ffmpeg", "-hide_banner", "-filters"], capture_output=True, text=True).stdout
    if not re.search(r"^\s*\S+\s+ass\s", filters, re.MULTILINE):
        raise WalkVideoError(
            "this ffmpeg was built without libass, which draws the slides and captions. "
            "Install an ffmpeg built with --enable-libass (Homebrew's and Debian's are)", EXIT_MISSING_TOOL)


def probe_duration(path: Path) -> float:
    out = run(["ffprobe", "-v", "error", "-show_entries", "format=duration", "-of", "csv=p=0", str(path)],
              failure=f"ffprobe could not read {path}").stdout.strip()
    try:
        return float(out)
    except ValueError:
        raise WalkVideoError(f"ffprobe returned no duration for {path}", EXIT_RENDER_FAILED)


def build_scene_audio(scene: dict, idx: int, engine: str, engines: Dict[str, dict], work: Path,
                      say_voice: Optional[str]) -> Tuple[Path, List[Tuple[float, float, str]], float]:
    """Narrate one scene sentence by sentence; return (wav, caption cues, duration)."""
    pcm = bytearray(silence(LEAD_IN_S))
    cues: List[Tuple[float, float, str]] = []
    sentences = split_sentences(scene["narration"])
    for j, sentence in enumerate(sentences):
        if j:
            pcm += silence(SENTENCE_GAP_S)
        start = frames_seconds(pcm)
        if engine == "none":
            speech = silence(word_count(sentence) / WORDS_PER_SECOND)
        else:
            raw = work / f"s{idx:02d}-{j:02d}{'.aiff' if engine == 'say' else '.wav'}"
            norm = work / f"s{idx:02d}-{j:02d}.norm.wav"
            synthesize(engine, engines, sentence, raw, say_voice)
            normalize_audio(raw, norm)
            speech = read_frames(norm)
        pcm += speech
        end = frames_seconds(pcm)
        chunks = caption_chunks(sentence)
        total_chars = sum(len(c) for c in chunks) or 1
        t = start
        for chunk in chunks:
            span = (end - start) * len(chunk) / total_chars
            cues.append((t, t + span, chunk))
            t += span
    pcm += silence(TAIL_S)
    out = work / f"scene{idx:02d}.wav"
    with wave.open(str(out), "wb") as w:
        w.setnchannels(CHANNELS)
        w.setsampwidth(SAMPLE_WIDTH)
        w.setframerate(SAMPLE_RATE)
        w.writeframes(bytes(pcm))
    return out, cues, frames_seconds(pcm)


def render_scene(scene: dict, idx: int, pr: dict, audio: Path, cues: List[Tuple[float, float, str]],
                 duration: float, work: Path, base_dir: Path, burn_captions: bool) -> Path:
    ass = AssScene(duration)
    draw_header(ass, scene, pr)
    draw_visual(ass, scene, pr)
    if burn_captions:
        for start, end, chunk in cues:
            ass.caption("\\N".join(ass_text(line) for line in chunk.split("\n")), start, end)
    ass_name = f"scene{idx:02d}.ass"
    (work / ass_name).write_text(ass.render(), encoding="utf-8")

    out = work / f"scene{idx:02d}.mp4"
    dur = f"{duration:.3f}"
    cmd = ["ffmpeg", "-v", "error", "-y", "-f", "lavfi",
           "-i", f"color=c=0x{COLORS['bg']}:s={WIDTH}x{HEIGHT}:r={FPS}:d={dur}"]
    visual = scene["visual"]
    box = f"scale={CONTENT_W}:{CONTENT_H}:force_original_aspect_ratio=decrease,setsar=1"
    place = f"overlay=x={MARGIN_X}+({CONTENT_W}-overlay_w)/2:y={CONTENT_TOP}+({CONTENT_H}-overlay_h)/2"
    if visual["type"] == "image":
        src = resolve_src(visual["src"], base_dir)
        cmd += ["-loop", "1", "-t", dur, "-i", str(src)]
        graph = f"[1:v]{box}[m];[0:v][m]{place}:eof_action=repeat[b];[b]ass={ass_name}[v]"
        audio_index = 2
    elif visual["type"] == "video":
        src = resolve_src(visual["src"], base_dir)
        start = float(visual.get("start", 0))
        available = max(0.0, probe_duration(src) - start)
        hold = max(0.0, duration - available)
        cmd += ["-ss", f"{start:.3f}", "-i", str(src)]
        graph = (f"[1:v]fps={FPS},{box},tpad=stop_mode=clone:stop_duration={hold:.3f}[m];"
                 f"[0:v][m]{place}:eof_action=repeat[b];[b]ass={ass_name}[v]")
        audio_index = 2
    else:
        graph = f"[0:v]ass={ass_name}[v]"
        audio_index = 1
    cmd += ["-i", audio.name, "-filter_complex", graph, "-map", "[v]", "-map", f"{audio_index}:a",
            "-t", dur, "-r", str(FPS), "-c:v", "libx264", "-preset", "medium", "-crf", "20",
            "-pix_fmt", "yuv420p", "-c:a", "aac", "-b:a", "160k", "-ar", str(SAMPLE_RATE), out.name]
    run(cmd, cwd=work, failure=f"ffmpeg failed rendering scene {idx}")
    return out


def transcript_markdown(script: dict, engine: str, engines: Dict[str, dict], duration: float,
                        say_voice: Optional[str]) -> str:
    pr = script.get("pr", {})
    title = f"PR #{pr['number']}: {pr.get('title', '')}" if pr.get("number") else pr.get("title", "this PR")
    minutes, seconds = divmod(int(round(duration)), 60)
    if engine == "piper":
        voice = f"local piper voice ({Path(engines['piper']['voice']).stem})"
    elif engine == "say":
        voice = f"macOS say{f' ({say_voice})' if say_voice else ''}"
    elif engine == "espeak-ng":
        voice = "espeak-ng"
    else:
        voice = "none (captions only)"
    lines = [
        "<!-- bruhs:walk-video -->",
        f"## Video walkthrough: {title}",
        "",
        "_Video: drag `walkthrough.mp4` here._",
        "",
        f"**Length:** {minutes}:{seconds:02d} · **Narration:** {voice}, synthesized on the author's machine",
        "",
    ]
    for scene in script["scenes"]:
        lines.append(f"### {KIND_LABEL[scene['kind']].capitalize()}: {scene['heading']}")
        lines.append("")
        lines.append(" ".join(scene["narration"].split()))
        lines.append("")
        if scene["kind"] == "validation":
            lines += ["| Claim | Status | Receipt |", "|---|---|---|"]
            for claim in scene["claims"]:
                receipt = " ".join((claim.get("receipt") or "").split()).replace("|", "\\|") or "—"
                text = claim["text"].replace("|", "\\|")
                lines.append(f"| {text} | {STATUS_LABEL[claim['status']].capitalize()} | {receipt} |")
            lines.append("")
    return "\n".join(lines)


def render(script: dict, script_path: Path, out_dir: Path, engine: str, engines: Dict[str, dict],
           say_voice: Optional[str], burn_captions: bool, keep_work: bool) -> dict:
    base_dir = script_path.parent
    out_dir.mkdir(parents=True, exist_ok=True)
    work = out_dir / "work"
    if work.exists():
        shutil.rmtree(work)
    work.mkdir()
    pr = script.get("pr", {})

    scene_files: List[Path] = []
    srt: List[str] = []
    offset = 0.0
    scene_report = []
    for idx, scene in enumerate(script["scenes"], start=1):
        audio, cues, duration = build_scene_audio(scene, idx, engine, engines, work, say_voice)
        scene_files.append(render_scene(scene, idx, pr, audio, cues, duration, work, base_dir, burn_captions))
        for start, end, chunk in cues:
            srt += [str(len(srt) // 4 + 1), f"{srt_time(offset + start)} --> {srt_time(offset + end)}", chunk, ""]
        scene_report.append({"index": idx, "kind": scene["kind"], "heading": scene["heading"],
                             "start": round(offset, 2), "seconds": round(duration, 2)})
        offset += duration

    concat_list = work / "scenes.txt"
    concat_list.write_text("".join(f"file '{p.name}'\n" for p in scene_files), encoding="utf-8")
    out_dir = out_dir.resolve()
    video = out_dir / "walkthrough.mp4"
    run(["ffmpeg", "-v", "error", "-y", "-f", "concat", "-safe", "0", "-i", concat_list.name,
         "-c", "copy", "-movflags", "+faststart", str(video)],
        cwd=work, failure="ffmpeg could not join the scenes")
    (out_dir / "captions.srt").write_text("\n".join(srt), encoding="utf-8")
    (out_dir / "transcript.md").write_text(
        transcript_markdown(script, engine, engines, offset, say_voice), encoding="utf-8")
    if not keep_work:
        shutil.rmtree(work)

    manifest = {
        "video": str(video),
        "captions": str(out_dir / "captions.srt"),
        "transcript": str(out_dir / "transcript.md"),
        "seconds": round(offset, 2),
        "engine": engine,
        "voice": engines["piper"]["voice"] if engine == "piper" else say_voice,
        "captions_burned": burn_captions,
        "scenes": scene_report,
    }
    (out_dir / "manifest.json").write_text(json.dumps(manifest, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")
    return manifest


# ── CLI ─────────────────────────────────────────────────────────────────────


def load_script(path: Path) -> dict:
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except FileNotFoundError:
        raise WalkVideoError(f"script not found: {path}", EXIT_INVALID)
    except json.JSONDecodeError as exc:
        raise WalkVideoError(f"{path} is not valid JSON: {exc}", EXIT_INVALID)


def main(argv: Optional[Sequence[str]] = None) -> int:
    parser = argparse.ArgumentParser(description="Render a narrated PR walkthrough video.")
    sub = parser.add_subparsers(dest="command", required=True)

    p_engines = sub.add_parser("engines", help="list local TTS engines and which one auto picks")
    p_engines.add_argument("--voice", help="piper .onnx voice (default: BRUHS_PIPER_VOICE or ~/.local/share/bruhs/voices)")

    for name in ("check", "render"):
        p = sub.add_parser(name)
        p.add_argument("script", type=Path)
        p.add_argument("--tts", choices=("auto",) + ENGINES, default="auto")
        p.add_argument("--voice", help="piper .onnx voice file")
        if name == "render":
            p.add_argument("--out", type=Path, required=True)
            p.add_argument("--say-voice", help="voice name for macOS say (see: say -v '?')")
            p.add_argument("--no-burn-captions", action="store_true")
            p.add_argument("--keep-work", action="store_true", help="keep per-scene files under OUT/work")

    args = parser.parse_args(argv)
    try:
        engines = detect_engines(args.voice)
        if args.command == "engines":
            auto, notes = choose_engine("auto", engines)
            print(json.dumps({"auto": auto, "notes": notes,
                              "engines": {k: {"available": v["available"], "detail": v["detail"]}
                                          for k, v in engines.items()}}, indent=2, ensure_ascii=False))
            return EXIT_OK

        script = load_script(args.script)
        errors, warnings = validate_script(script, args.script.parent)
        if args.command == "check":
            engine, notes = choose_engine(args.tts, engines) if not errors else (None, [])
            scenes = script.get("scenes") if isinstance(script, dict) else None
            estimate = sum(estimate_seconds(s.get("narration", "")) for s in scenes
                           if isinstance(s, dict) and isinstance(s.get("narration"), str)) if isinstance(scenes, list) else 0
            print(json.dumps({"ok": not errors, "errors": errors, "warnings": warnings + notes,
                              "engine": engine, "estimated_seconds": round(estimate, 1)}, indent=2, ensure_ascii=False))
            return EXIT_INVALID if errors else EXIT_OK

        if errors:
            raise WalkVideoError("the script has problems:\n" + "\n".join(f"  - {e}" for e in errors), EXIT_INVALID)
        preflight_ffmpeg()
        engine, notes = choose_engine(args.tts, engines)
        for note in warnings + notes:
            print(f"warning: {note}", file=sys.stderr)
        manifest = render(script, args.script.resolve(), args.out, engine, engines, args.say_voice,
                          not args.no_burn_captions, args.keep_work)
        manifest["warnings"] = warnings + notes
        print(json.dumps(manifest, indent=2, ensure_ascii=False))
        return EXIT_OK
    except WalkVideoError as exc:
        print(f"walk_video: {exc}", file=sys.stderr)
        return exc.code


if __name__ == "__main__":
    sys.exit(main())
