import json

import pytest

from bruhsbench import judge as J
from bruhsbench.graders import checklist
from bruhsbench.types import MODELS

from conftest import make_task

SPEC = {m.cli: m for m in MODELS}

ITEMS = [
    {"id": "readme", "text": "README mentions the new flag", "check": "script",
     "script": "grep -q -- --fast README.md"},
    {"id": "changelog", "text": "CHANGELOG updated", "check": "script",
     "script": "test -f CHANGELOG.md"},
    {"id": "commit-msg", "text": "Commit message explains why", "check": "judge"},
    {"id": "no-debug", "text": "No debug logging left in", "check": "judge"},
    {"id": "pr-body", "text": "Summary lists the risks", "check": "judge"},
]


@pytest.fixture(autouse=True)
def judge_work(tmp_path, monkeypatch):
    """Judge temp dirs (staged images, homes) go under tmp_path, not /private/tmp."""
    monkeypatch.setenv("BRUHSBENCH_WORK", str(tmp_path / "judge-work"))
    return tmp_path / "judge-work"


@pytest.fixture
def run(tmp_path, make_run):
    r = make_run({"README.md": "# tool\n"}, run_id="ship__claude__bruhs__r1")
    r.write({"README.md": "# tool\nUse --fast for speed.\n", "src/app.py": "print('x')\n"})
    run_dir = r.finish(final="Shipped via /bruhs:yeet. Added --fast to README.")
    (tmp_path / "task").mkdir(exist_ok=True)
    cl = tmp_path / "task" / "checklist.json"
    cl.write_text(json.dumps({"items": ITEMS}))
    task = make_task(tmp_path, id="ship", category="ship", checklist=cl, prompt="Ship it.")
    return task, run_dir, r.workspace


def votes(table):
    """judge_call stub: each judge cli answers hit per item id from ``table``."""
    calls = []

    def fake(judge, prompt, images, schema):
        calls.append((judge, prompt))
        return {"items": [{"id": i, "hit": hit, "evidence": "e"}
                          for i, hit in table[judge.cli].items()]}

    return fake, calls


def test_checklist_script_and_judge_items(run, monkeypatch):
    task, run_dir, workspace = run
    fake, calls = votes({
        "codex": {"commit-msg": True, "no-debug": True, "pr-body": False},
        "grok": {"commit-msg": True, "no-debug": False, "pr-body": False},
    })
    monkeypatch.setattr(J, "judge_call", fake)
    out = checklist.grade(task, run_dir, [SPEC["codex"], SPEC["grok"]])
    items = {i["id"]: i for i in out["items"]}
    assert items["readme"] == {"id": "readme", "hit": True, "by": "script"}
    assert items["changelog"] == {"id": "changelog", "hit": False, "by": "script"}
    assert items["commit-msg"]["hit"] is True and items["commit-msg"]["by"] == "judge"
    assert items["commit-msg"]["votes"] == {"codex": True, "grok": True}
    assert items["no-debug"]["hit"] is False  # 1-1 tie -> miss
    assert items["no-debug"]["votes"] == {"codex": True, "grok": False}
    assert items["pr-body"]["hit"] is False and items["pr-body"]["votes"] == {
        "codex": False, "grok": False}
    assert out["score"] == pytest.approx(2 / 5)
    assert out["judge_errors"] == {} and "invalid" not in out
    assert json.loads((run_dir / "grades" / "checklist.json").read_text()) == out
    # one batched call per judge; the agent's workspace is untouched by scripts
    assert sorted(j.cli for j, _ in calls) == ["codex", "grok"]
    assert not (workspace / "CHANGELOG.md").exists()
    # judges see the items and a redacted record of the run
    prompt = calls[0][1]
    assert "Commit message explains why" in prompt and "README mentions" not in prompt
    assert "bruhs" not in prompt.lower() and "/yeet" not in prompt
    assert "Use --fast for speed." in prompt


def _judge_items_all_hit(judge):
    return {"items": [{"id": i["id"], "hit": True, "evidence": ""} for i in ITEMS
                      if i["check"] == "judge"]}


@pytest.mark.parametrize("failure", ["error", "omitted"])
def test_checklist_judge_failure_invalidates_grade(run, monkeypatch, failure):
    """A judge that fails or skips an item makes the grade invalid; it is never scored
    as the agent missing the item."""
    task, run_dir, _ = run

    def fake(judge, prompt, images, schema):
        if judge.cli == "grok":
            if failure == "error":
                raise J.JudgeError("bad output twice")
            return {"items": [{"id": "commit-msg", "hit": True, "evidence": ""}]}
        return _judge_items_all_hit(judge)

    monkeypatch.setattr(J, "judge_call", fake)
    out = checklist.grade(task, run_dir, [SPEC["codex"], SPEC["grok"]])
    assert out["invalid"] is True and out["score"] is None
    assert "grok" in out["judge_errors"] and "codex" not in out["judge_errors"]
    judged = [i for i in out["items"] if i["by"] == "judge"]
    assert judged and all(i["hit"] is None for i in judged)
    assert all(i["votes"]["codex"] is True for i in judged)
    scripted = {i["id"]: i["hit"] for i in out["items"] if i["by"] == "script"}
    assert scripted == {"readme": True, "changelog": False}
    assert json.loads((run_dir / "grades" / "checklist.json").read_text()) == out


def test_checklist_screenshot_name_collisions_are_staged_uniquely(run, monkeypatch):
    task, run_dir, _ = run
    for name in ("bruhs-home__desktop__light", "page__desktop__light"):  # redact to the same
        (run_dir / "screens").mkdir(exist_ok=True)
        (run_dir / "screens" / f"{name}.png").write_bytes(b"\x89PNG fake")
    seen = []

    def fake(judge, prompt, images, schema):
        seen.append(sorted(p.name for p in images))
        return _judge_items_all_hit(judge)

    monkeypatch.setattr(J, "judge_call", fake)
    out = checklist.grade(task, run_dir, [SPEC["codex"], SPEC["grok"]])
    assert out["score"] == pytest.approx(4 / 5)
    assert seen[0] == ["page__desktop__light-2.png", "page__desktop__light.png"]
    assert not any("bruhs" in n for n in seen[0])


def test_checklist_refuses_own_family_judge(run, monkeypatch):
    task, run_dir, _ = run
    monkeypatch.setattr(J, "judge_call", votes({})[0])
    with pytest.raises(ValueError):
        checklist.grade(task, run_dir, [SPEC["claude"], SPEC["grok"]])


def test_checklist_not_applicable_without_checklist(tmp_path, make_run):
    run_dir = make_run({"a": "1"}).finish()
    out = checklist.grade(make_task(tmp_path), run_dir, [SPEC["codex"], SPEC["grok"]])
    assert out["applicable"] is False
