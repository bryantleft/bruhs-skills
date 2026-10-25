"""Builders for a fake results root: tasks, finished runs with grades, pairwise verdicts.

No model or CLI is ever called; everything is the JSON the real stages would write.
"""

from __future__ import annotations

import json
from pathlib import Path

from bruhsbench.tasks import load_task
from bruhsbench.types import Task

# a 1x1 PNG
PNG = bytes.fromhex(
    "89504e470d0a1a0a0000000d4948445200000001000000010806000000"
    "1f15c4890000000d49444154789c6360f8cfc0f01f0005000201e5273de4"
    "0000000049454e44ae426082")


def make_task(root: Path, task_id: str, category: str, *, private: bool = False,
              repo: str | None = None, prompt: str | None = None, pages=()) -> Task:
    d = Path(root) / ("tasks-private" if private else "tasks") / task_id
    d.mkdir(parents=True, exist_ok=True)
    lines = [f'id = "{task_id}"', f'category = "{category}"']
    if repo:
        lines += [f'repo = "{repo}"', 'base = "abc123"']
    if pages:
        lines += ['dev_cmd = "true"', "dev_port = 3000",
                  "pages = [" + ", ".join(f'"{p}"' for p in pages) + "]"]
    (d / "task.toml").write_text("\n".join(lines) + "\n")
    (d / "prompt.md").write_text(prompt or f"please do the {task_id} thing\n")
    return load_task(d)


def run_id(task: Task, cli: str, arm: str, repeat: int) -> str:
    return f"{task.id}__{cli}__{arm}__r{repeat}"


def make_run(results: Path, task: Task, cli: str, arm: str, repeat: int, *,
             status: str = "ok", contaminated: bool | None = False, diff: str = "diff --git a/x b/x\n",
             grades: dict | None = None, transcript: str = "", cost: float | None = 1.0,
             wall_s: float = 60.0, turns: int | None = 10, orphaned: bool = False,
             screens: bool = False) -> Path:
    rid = run_id(task, cli, arm, repeat)
    d = Path(results) / rid
    d.mkdir(parents=True, exist_ok=True)
    (d / "diff.patch").write_text(diff)
    (d / "transcript.jsonl").write_text(transcript)
    (d / "final.txt").write_text("done")
    result = {
        "run_id": rid, "status": status, "wall_s": wall_s, "turns": turns,
        "input_tokens": 100, "output_tokens": 50, "cost_usd": cost, "final_message": "done",
        "diff_path": str(d / "diff.patch"), "transcript_path": str(d / "transcript.jsonl"),
        "contaminated": contaminated, "contamination": [], "workspace": None, "error": None,
        "unsafe_files": [], "orphaned_output": orphaned,
    }
    (d / "result.json").write_text(json.dumps(result))
    g = d / "grades"
    g.mkdir(exist_ok=True)
    for name, grade in (grades or {}).items():
        (g / f"{name}.json").write_text(json.dumps(grade))
    if screens:
        (d / "screens").mkdir(exist_ok=True)
        (d / "screens" / "root__desktop__light.png").write_bytes(PNG)
    return d


def feature_grades(ok: bool) -> dict:
    """Grades of a feature/debug run whose primary metric is 1 (ok) or 0."""
    return {
        "commands": {"applicable": True, "checks": {"test": True}, "hidden_pass": 3 if ok else 1,
                     "hidden_total": 3, "regressions": [], "timed_out": [],
                     "hidden": {"applicable": True}},
        "honesty": {"applicable": True, "claims": 1, "false_claims": 0, "honest_done": True},
        "scope": {"applicable": True, "files_outside": [], "lines_outside": 0,
                  "files_changed": 1, "lines_changed": 5},
    }


def audit_grades(f1: float) -> dict:
    return {"audit": {"applicable": True, "f1": f1},
            "scope": {"applicable": True, "files_outside": [], "lines_outside": 0}}


def ship_grades(score: float | None) -> dict:
    grade = {"applicable": True, "score": score, "items": []}
    if score is None:
        grade["invalid"] = True
    return {"checklist": grade,
            "scope": {"applicable": True, "files_outside": [], "lines_outside": 0}}


def make_verdict(results: Path, task: Task, cli: str, repeat: int, judge: str,
                 winner_arm: str | None, *, bruhs_shown_as: str = "A") -> None:
    """A pairwise verdict file + pairs_key entry; ``winner_arm`` in arm terms (None =
    judge error)."""
    pairs = Path(results) / "_pairs"
    pairs.mkdir(parents=True, exist_ok=True)
    pair_id = f"{task.id}__{cli}__r{repeat}__{judge}"
    other = "B" if bruhs_shown_as == "A" else "A"
    shown = {bruhs_shown_as: run_id(task, cli, "bruhs", repeat),
             other: run_id(task, cli, "bare", repeat)}
    key_path = pairs / "pairs_key.json"
    key = json.loads(key_path.read_text()) if key_path.is_file() else {}
    key[pair_id] = shown
    key_path.write_text(json.dumps(key))
    if winner_arm is None:
        winner = None
    elif winner_arm == "tie":
        winner = "tie"
    else:
        winner = bruhs_shown_as if winner_arm == "bruhs" else other
    record = {"task_id": task.id, "model_cli": cli, "repeat": repeat, "judge_cli": judge,
              "winner": winner, "reasons": "r"}
    if winner is None:
        record["error"] = "judge failed"
    (pairs / f"{pair_id}.json").write_text(json.dumps(record))
