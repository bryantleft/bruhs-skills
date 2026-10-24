import base64
import json
import re
import struct
import zlib
from dataclasses import replace
from pathlib import Path

import pytest

from bruhsbench import judge as J
from bruhsbench.types import MODELS, Task

SPEC = {m.cli: m for m in MODELS}

# Everything that would tell a judge which run had bruhs installed.
FORBIDDEN = re.compile(
    r"bruhs|/cook|/slop|/peep|/yeet|/verify|/doodle|/expect|expect-cli|superpowers"
    r"|chrome-devtools|\.agents/skills|plugins/bruhs|<!--\s*bruhs:|CLAUDE\.md|AGENTS\.md"
    r"|\bbare\b",
    re.IGNORECASE,
)

BRUHS_FINAL = """Done. I ran /bruhs:cook then /slop and /expect to check it, with the
superpowers skills and chrome-devtools MCP (mcp__chrome-devtools__take_screenshot).
Also /peep, /yeet, /verify and /doodle. Skill files at .agents/skills/bruhs/SKILL.md and
/tmp/x/home/plugins/bruhs/commands/cook.md; BRUHS-managed block kept. Ran npx expect-cli.
The pricing card now has consistent spacing."""

BRUHS_DIFF = """diff --git a/CLAUDE.md b/CLAUDE.md
--- a/CLAUDE.md
+++ b/CLAUDE.md
@@ -1,2 +1,4 @@
 # Project
+<!-- bruhs:stack:begin -->
+stack rules
+<!-- bruhs:stack:end -->
diff --git a/AGENTS.md b/AGENTS.md
--- a/AGENTS.md
+++ b/AGENTS.md
@@ -1 +1,2 @@
 # Agents
+see bruhs
diff --git a/.claude/bruhs.json b/.claude/bruhs.json
new file mode 100644
--- /dev/null
+++ b/.claude/bruhs.json
@@ -0,0 +1 @@
+{"stack": "next"}
diff --git a/src/Pricing.tsx b/src/Pricing.tsx
--- a/src/Pricing.tsx
+++ b/src/Pricing.tsx
@@ -1,3 +1,3 @@
 export function Pricing() {
-  return <div className="p-3">Pricing</div>;
+  return <div className="p-4">Pricing</div>; // checked with /expect (bruhs)
 }
"""

BARE_DIFF = """diff --git a/src/Pricing.tsx b/src/Pricing.tsx
--- a/src/Pricing.tsx
+++ b/src/Pricing.tsx
@@ -1,3 +1,3 @@
 export function Pricing() {
-  return <div className="p-3">Pricing</div>;
+  return <div className="p-6">Pricing</div>;
 }
"""


def png(path: Path, rgb=(255, 0, 0), w: int = 4, h: int = 4) -> Path:
    raw = b"".join(b"\x00" + bytes(rgb) * w for _ in range(h))

    def chunk(t, d):
        return struct.pack(">I", len(d)) + t + d + struct.pack(">I", zlib.crc32(t + d))

    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_bytes(b"\x89PNG\r\n\x1a\n" + chunk(b"IHDR", struct.pack(">IIBBBBB", w, h, 8, 2, 0, 0, 0))
                     + chunk(b"IDAT", zlib.compress(raw)) + chunk(b"IEND", b""))
    return path


def make_task(tmp_path: Path, **kw) -> Task:
    d = tmp_path / "task"
    d.mkdir(exist_ok=True)
    base = Task(id="ui-pricing", category="ui", dir=d, repo=None, base=None,
                prompt="Tidy the pricing card spacing.", setup=None, allowed_paths=(),
                pages=("/",), dev_cmd=None, dev_port=None, checks={}, hidden_tests=None,
                known_issues=None, checklist=None, heldout=False)
    return replace(base, **kw)


def make_run(root: Path, run_id: str, final: str, diff: str, shots=("root__desktop__light",)) -> Path:
    d = root / run_id
    d.mkdir(parents=True)
    (d / "final.txt").write_text(final)
    (d / "diff.patch").write_text(diff)
    (d / "result.json").write_text(json.dumps({"run_id": run_id, "final_message": final}))
    for s in shots:
        png(d / "screens" / f"{s}.png")
    return d


@pytest.fixture(autouse=True)
def judge_work(tmp_path, monkeypatch):
    """Judge temp dirs (staged images, homes) go under tmp_path, not /private/tmp."""
    monkeypatch.setenv("BRUHSBENCH_WORK", str(tmp_path / "judge-work"))
    return tmp_path / "judge-work"


@pytest.fixture
def pair(tmp_path):
    results = tmp_path / "results"
    bare = make_run(results, "ui-pricing__claude__bare__r1", "Done. Spacing fixed.", BARE_DIFF)
    bruhs = make_run(results, "ui-pricing__claude__bruhs__r1", BRUHS_FINAL, BRUHS_DIFF)
    png(results / "_before" / "ui-pricing" / "root__desktop__light.png")
    return make_task(tmp_path), bare, bruhs


class FakeJudge:
    """Stands in for judge_call: records what each judge was shown, answers from a script."""

    def __init__(self, answer):
        self.calls = []
        self.answer = answer

    def __call__(self, judge, prompt, images, schema):
        self.calls.append({"judge": judge, "prompt": prompt, "images": list(images),
                           "image_bytes": [Path(i).read_bytes() for i in images],
                           "schema": schema})
        return self.answer(judge, prompt) if callable(self.answer) else self.answer


# --------------------------------------------------------------------------- families


def test_judges_exclude_own_family():
    for cli in ("claude", "codex", "grok"):
        judges = J.judges_for(cli)
        assert len(judges) == 2
        assert cli not in {j.cli for j in judges}
        assert {j.cli for j in judges} == {"claude", "codex", "grok"} - {cli}
        assert all(j.effort == "high" for j in judges)
        one = J.make_judge(cli)
        assert one.spec.cli != cli and one.spec in judges
    assert J.make_judge("claude").spec.cli == "codex"
    assert J.make_judge("codex").spec.cli == "grok"
    assert J.make_judge("grok").spec.cli == "claude"


def test_pairwise_refuses_own_family_judge(pair, monkeypatch):
    task, bare, bruhs = pair
    monkeypatch.setattr(J, "judge_call", FakeJudge({"winner": "A", "reasons": "x"}))
    with pytest.raises(ValueError):
        J.pairwise(task, bare, bruhs, SPEC["claude"])


# --------------------------------------------------------------------------- blindness


def test_redact_removes_arm_revealing_strings():
    out = J.redact(BRUHS_FINAL)
    assert not FORBIDDEN.search(out), FORBIDDEN.search(out)
    assert "pricing card now has consistent spacing" in out
    # ordinary words and routes that merely contain the stems survive
    assert J.redact("expect(x).toBe(1); see /verifying and /cookies") == \
        "expect(x).toBe(1); see /verifying and /cookies"


def test_diff_for_judge_drops_agent_config_and_truncates():
    out = J.diff_for_judge(BRUHS_DIFF)
    assert "src/Pricing.tsx" in out and 'className="p-4"' in out
    assert not FORBIDDEN.search(out), FORBIDDEN.search(out)
    assert ".claude/" not in out
    big = "diff --git a/x b/x\n--- a/x\n+++ b/x\n@@ -0,0 +1 @@\n" + "+line\n" * 30_000
    out = J.diff_for_judge(big)
    assert len(out) <= J.MAX_DIFF_CHARS + 100 and "truncated" in out


def test_pairwise_hides_arm(pair, monkeypatch):
    task, bare, bruhs = pair
    fake = FakeJudge({"winner": "A", "reasons": "A is tidier"})
    monkeypatch.setattr(J, "judge_call", fake)
    J.pairwise(task, bare, bruhs, SPEC["codex"])
    call = fake.calls[0]
    shown = call["prompt"] + "\n".join(Path(i).name for i in call["images"])
    assert not FORBIDDEN.search(shown), FORBIDDEN.search(shown)
    for run in (bare, bruhs):
        assert run.name not in shown and str(run) not in shown
    assert "Tidy the pricing card spacing." in call["prompt"]
    assert 'className="p-4"' in call["prompt"] and 'className="p-6"' in call["prompt"]
    assert J.PAIRWISE_RUBRIC in call["prompt"]
    names = {Path(i).name for i in call["images"]}
    assert names == {"before__root__desktop__light.png", "A__root__desktop__light.png",
                     "B__root__desktop__light.png"}
    # the images handed over are copies outside the run dirs
    assert all(not Path(i).is_relative_to(bare.parent) for i in call["images"])


def test_judge_gets_no_tools_and_images_inline(tmp_path, monkeypatch):
    """Every material is in the message; the judge's cwd is empty and it has no tools."""
    img = png(tmp_path / "A__root__desktop__light.png", (0, 0, 255))
    b64 = base64.b64encode(img.read_bytes()).decode()
    seen = {}

    def invoke(cmd, env, cwd, timeout, stdin=None):
        seen[cmd[0]] = {"cmd": cmd, "stdin": stdin, "cwd": sorted(Path(cwd).iterdir())}
        if cmd[0] == "grok":
            seen["grok"]["blocks"] = json.loads(Path(cmd[cmd.index("--prompt-file") + 1]).read_text())
            return 0, json.dumps({"structuredOutput": {"winner": "tie", "reasons": "s"}}), ""
        if cmd[0] == "codex":
            seen["codex"]["image"] = Path(cmd[cmd.index("-i") + 1]).read_bytes()
            Path(cmd[cmd.index("-o") + 1]).write_text('{"winner": "tie", "reasons": "s"}')
            return 0, "", ""
        return 0, json.dumps({"type": "result", "is_error": False,
                              "structured_output": {"winner": "tie", "reasons": "s"}}), ""

    monkeypatch.setattr(J, "_invoke", invoke)
    monkeypatch.setattr(J, "build_home", lambda *a, **k: {"HOME": str(tmp_path / "h")})
    for cli in ("claude", "codex", "grok"):
        assert J.judge_call(SPEC[cli], "compare", [img], J.PAIRWISE_SCHEMA) == {
            "winner": "tie", "reasons": "s"}
        assert seen[cli]["cwd"] == []

    claude = seen["claude"]["cmd"]
    assert claude[claude.index("--tools") + 1] == "" and "--strict-mcp-config" in claude
    content = json.loads(seen["claude"]["stdin"])["message"]["content"]
    assert "compare" in content[0]["text"] and "A__root__desktop__light.png" in content[0]["text"]
    assert content[-1]["source"]["data"] == b64

    codex = seen["codex"]["cmd"]
    for feature in ("shell_tool", "unified_exec", "view_image"):
        assert codex[codex.index(feature) - 1] == "--disable"
    assert seen["codex"]["image"] == img.read_bytes()

    grok = seen["grok"]["cmd"]
    assert grok[grok.index("--tools") + 1] == "" and "--disable-web-search" in grok
    assert seen["grok"]["blocks"][-1] == {"type": "image", "data": b64, "mimeType": "image/png"}
    assert not list((tmp_path / "judge-work").rglob("*.png"))  # temp dirs cleaned up


def test_prepare_images_tiles_tall_screenshots(tmp_path):
    small = png(tmp_path / "in" / "a.png")
    tall = png(tmp_path / "in" / "tall.png", w=10, h=J.MAX_IMAGE_PX * 2 + 5)
    out = J.prepare_images([small, tall], tmp_path / "out")
    assert [p.name for p in out] == ["a.png", "tall__part1of3.png", "tall__part2of3.png",
                                     "tall__part3of3.png"]
    assert [J._png_size(p) for p in out[1:]] == [(10, J.MAX_IMAGE_PX), (10, J.MAX_IMAGE_PX),
                                                 (10, 4)]
    wide = png(tmp_path / "in" / "wide.png", w=J.MAX_IMAGE_PX * 2, h=J.MAX_IMAGE_PX * 3)
    out = J.prepare_images([wide], tmp_path / "out2")  # halved to 2000 x 3000, then tiled
    assert [J._png_size(p) for p in out] == [(J.MAX_IMAGE_PX, J.MAX_IMAGE_PX),
                                             (J.MAX_IMAGE_PX, 999)]


# --------------------------------------------------------------------------- order


def test_pairwise_order_randomized_and_recoverable(tmp_path, monkeypatch):
    results = tmp_path / "results"
    task = make_task(tmp_path)
    fake = FakeJudge({"winner": "A", "reasons": "A better"})
    monkeypatch.setattr(J, "judge_call", fake)
    orders = set()
    for repeat in range(1, 7):
        bare = make_run(results, f"ui-pricing__grok__bare__r{repeat}", "Done.", BARE_DIFF)
        bruhs = make_run(results, f"ui-pricing__grok__bruhs__r{repeat}", "Done!", BRUHS_DIFF)
        for judge in (SPEC["claude"], SPEC["codex"]):
            out = J.pairwise(task, bare, bruhs, judge)
            key = json.loads((results / "_pairs" / "pairs_key.json").read_text())
            entry = key[f"ui-pricing__grok__r{repeat}__{judge.cli}"]
            orders.add(entry["A"])
            # judge said "A": the caller's a_dir won exactly when A was the bare run
            assert out["winner"] == ("A" if entry["A"] == bare.name else "B")
            verdict = json.loads(
                (results / "_pairs" / f"ui-pricing__grok__r{repeat}__{judge.cli}.json").read_text())
            assert verdict["winner"] == "A" and verdict["judge_cli"] == judge.cli
            assert "bare" not in json.dumps(verdict) and "bruhs" not in json.dumps(verdict)
            # same seed, swapped caller order -> same shown order, mirrored answer
            again = J.pairwise(task, bruhs, bare, judge)
            key2 = json.loads((results / "_pairs" / "pairs_key.json").read_text())
            assert key2[f"ui-pricing__grok__r{repeat}__{judge.cli}"] == entry
            assert again["winner"] == ("A" if entry["A"] == bruhs.name else "B")
    # across 12 (repeat, judge) seeds both arms get shown as "A"
    assert {o.split("__")[2] for o in orders} == {"bare", "bruhs"}


def test_pairwise_tie_maps_to_tie(pair, monkeypatch):
    task, bare, bruhs = pair
    monkeypatch.setattr(J, "judge_call", FakeJudge({"winner": "tie", "reasons": "same"}))
    assert J.pairwise(task, bare, bruhs, SPEC["grok"])["winner"] == "tie"


def test_pairwise_rejects_mismatched_runs(tmp_path, monkeypatch):
    results = tmp_path / "results"
    task = make_task(tmp_path)
    a = make_run(results, "ui-pricing__claude__bare__r1", "", "")
    b = make_run(results, "ui-pricing__claude__bruhs__r2", "", "")
    monkeypatch.setattr(J, "judge_call", FakeJudge({"winner": "A", "reasons": ""}))
    with pytest.raises(ValueError):
        J.pairwise(task, a, b, SPEC["codex"])


# --------------------------------------------------------------------------- judge_call


def _stub_cli(monkeypatch, tmp_path, outputs):
    calls = []

    def invoke(cmd, env, cwd, timeout, stdin=None):
        calls.append(cmd)
        out = outputs[len(calls) - 1]
        if "codex" == cmd[0]:
            last = Path(cmd[cmd.index("-o") + 1])
            last.write_text(out)
            return 0, "", ""
        return 0, out, ""

    monkeypatch.setattr(J, "_invoke", invoke)
    monkeypatch.setattr(J, "build_home", lambda *a, **k: {"HOME": str(tmp_path / "h")})
    monkeypatch.setenv("BRUHSBENCH_WORK", str(tmp_path / "work"))
    return calls


def _claude_out(obj) -> str:
    return json.dumps({"type": "result", "is_error": False, "structured_output": obj})


def test_invalid_json_retried_once(tmp_path, monkeypatch):
    good = {"winner": "B", "reasons": "B is cleaner"}
    calls = _stub_cli(monkeypatch, tmp_path, [_claude_out({"winner": "C"}), _claude_out(good)])
    assert J.judge_call(SPEC["claude"], "p", [], J.PAIRWISE_SCHEMA) == good
    assert len(calls) == 2

    calls = _stub_cli(monkeypatch, tmp_path, ["not json at all", "{}"])
    with pytest.raises(J.JudgeError):
        J.judge_call(SPEC["claude"], "p", [], J.PAIRWISE_SCHEMA)
    assert len(calls) == 2


@pytest.mark.parametrize("cli", ["claude", "codex", "grok"])
def test_judge_call_parses_each_cli(cli, tmp_path, monkeypatch):
    good = {"winner": "A", "reasons": "r"}
    out = {"claude": _claude_out(good), "codex": json.dumps(good),
           "grok": json.dumps({"text": json.dumps(good), "structuredOutput": good})}[cli]
    calls = _stub_cli(monkeypatch, tmp_path, [out])
    img = png(tmp_path / "A__x.png")
    assert J.judge_call(SPEC[cli], "p", [img], J.PAIRWISE_SCHEMA) == good
    cmd = calls[0]
    assert SPEC[cli].model in cmd
    if cli == "claude":
        assert cmd[cmd.index("--json-schema") + 1] == json.dumps(J.PAIRWISE_SCHEMA)
        assert cmd[cmd.index("--input-format") + 1] == "stream-json"
        assert cmd[cmd.index("--effort") + 1] == "high"
    elif cli == "codex":
        assert "--output-schema" in cmd and cmd[cmd.index("-s") + 1] == "read-only"
        assert cmd[cmd.index("-i") + 1].endswith("A__x.png")
        assert 'model_reasoning_effort="high"' in cmd and 'web_search="disabled"' in cmd
        assert cmd[-2] == "--" and "A__x.png" in cmd[-1]  # the prompt names the image
    else:
        assert cmd[cmd.index("--json-schema") + 1] == json.dumps(J.PAIRWISE_SCHEMA)
        assert "--prompt-file" in cmd and cmd[cmd.index("--effort") + 1] == "high"


def test_validate_schema():
    v = J.validate
    assert v({"winner": "A", "reasons": "x"}, J.PAIRWISE_SCHEMA)
    assert not v({"winner": "A"}, J.PAIRWISE_SCHEMA)
    assert not v({"winner": "A", "reasons": "x", "extra": 1}, J.PAIRWISE_SCHEMA)
    assert not v({"winner": "A", "reasons": 3}, J.PAIRWISE_SCHEMA)
    f = {"file": None, "line": 3, "line_end": None, "summary": "s", "severity": "high"}
    assert v({"findings": [f]}, J.FINDINGS_SCHEMA)
    assert not v({"findings": [{**f, "line": True}]}, J.FINDINGS_SCHEMA)
    assert not v({"findings": [{**f, "line": "3"}]}, J.FINDINGS_SCHEMA)


# --------------------------------------------------------------------------- Judge protocol


def test_make_judge_extraction_functions(monkeypatch):
    answers = {
        "findings": {"findings": [
            {"file": "src/a.ts", "line": 10, "line_end": 14, "summary": "SQL injection",
             "severity": "High"},
            {"file": None, "line": None, "line_end": None, "summary": "no tests",
             "severity": None}]},
        "claims": {"claims": [{"claim": "All tests pass", "kind": "tests_pass"}]},
        "match": {"id": "K9", "reason": "not a candidate"},
        "items": {"ids": ["c1", "zz"], "reason": "r"},
    }
    seen = []

    def fake(judge, prompt, images, schema):
        seen.append((judge, prompt))
        key = next(iter(schema["properties"]))
        return answers[{"findings": "findings", "claims": "claims", "id": "match",
                        "ids": "items"}[key]]

    monkeypatch.setattr(J, "judge_call", fake)
    j = J.make_judge("codex")
    findings = j.extract_findings("Found SQL injection in src/a.ts:10-14", {"AUDIT.md": "# audit"})
    assert findings == [
        {"file": "src/a.ts", "line": 10, "lines": [10, 14], "summary": "SQL injection",
         "severity": "high"},
        {"file": None, "line": None, "summary": "no tests", "severity": None}]
    assert "AUDIT.md" in seen[0][1] and "# audit" in seen[0][1]
    assert j.extract_claims("All tests pass") == [{"claim": "All tests pass", "kind": "tests_pass"}]
    cands = [{"id": "K1", "summary": "x", "decoy": True}, {"id": "K2", "summary": "y"}]
    assert j.match_finding({"summary": "z"}, cands) is None  # K9 isn't a candidate
    assert "decoy" not in seen[2][1]  # the decoy flag is never shown
    assert j.claimed_items({"claim": "c", "kind": "done"},
                           [{"id": "c1", "text": "t"}, {"id": "c2", "text": "u"}]) == ["c1"]
    assert all(js.cli == "grok" for js, _ in seen)


# --------------------------------------------------------------------------- live


@pytest.mark.live
@pytest.mark.parametrize("cli", ["claude", "codex", "grok"])
def test_live_judge_call(cli, tmp_path):
    red = png(tmp_path / "img_1.png", (255, 0, 0), w=64, h=64)
    schema = {
        "type": "object",
        "properties": {"color": {"type": "string"},
                       "line": {"type": ["integer", "null"]}},
        "required": ["color", "line"],
        "additionalProperties": False,
    }
    out = J.judge_call(
        SPEC[cli], "What is the dominant color of image img_1.png? Answer color as one "
        "lowercase word; set line to null.", [red], schema)
    assert J.validate(out, schema)
    assert out["color"] == "red" and out["line"] is None
