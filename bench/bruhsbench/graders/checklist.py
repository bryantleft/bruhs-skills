"""Checklist score: the task's frozen ``checklist.json`` against one finished run.

checklist.json: ``{"items": [{id, text, check: "script" | "judge", script?}]}`` (a bare
list of items is accepted too).

* ``script`` items: ``script`` runs with ``bash -c`` in a disposable clone of the agent's
  workspace (never the workspace itself); exit 0 = hit.
* ``judge`` items: every judge in ``judges`` (the two other families, ``judge.judges_for``)
  answers all judge items in one call from a blind record of the run (task prompt,
  redacted diff and final message, commit messages, screenshots). Each judge's vote is
  kept in ``votes``; an item is hit only with a strict majority, so with two judges a 1-1
  split is a miss.

Result (``grades/checklist.json``): ``{applicable, items: [{id, hit, by, votes?}], score,
judge_errors, notes}`` with ``score`` = hits / items. A judging failure is never scored as
the agent's miss: if any judge fails (``JudgeError``) or leaves a judge item unanswered,
the grade is ``invalid: true`` with ``score: None``, judge items get ``hit: None``, and the
reasons are in ``judge_errors``. ``notes`` holds non-judge problems (e.g. unreadable git
history, whose commit messages are then missing from the judges' evidence).
"""

from __future__ import annotations

import json
import shutil
import tempfile
from pathlib import Path

from .. import judge as J
from .. import untrusted
from ..types import ModelSpec, Task
from ..workspace import BASE_TAG
from . import not_applicable, run_meta, workspace_of, write_grade
from .commands import clone_tree, run_check, scratch_root

MAX_COMMITS_CHARS = 10_000


def load_items(path: Path) -> list[dict]:
    data = json.loads(Path(path).read_text())
    items = data.get("items", []) if isinstance(data, dict) else data
    for item in items:
        if item.get("check") not in ("script", "judge") or "id" not in item:
            raise ValueError(f"bad checklist item in {path}: {item}")
        if item["check"] == "script" and not item.get("script"):
            raise ValueError(f"script item {item['id']} in {path} has no script")
    return items


def _run_script(item: dict, workspace: Path, run_dir: Path) -> bool:
    scratch = Path(tempfile.mkdtemp(prefix="checklist-", dir=scratch_root(workspace)))
    try:
        copy = scratch / "ws"
        clone_tree(workspace, copy)
        res = run_check(f"checklist-{item['id']}", item["script"], copy, scratch,
                        Path(run_dir) / "grades" / "logs")
        return res.ok
    finally:
        shutil.rmtree(scratch, ignore_errors=True)


def _commits(workspace: Path | None, notes: dict[str, str] | None = None) -> str:
    if workspace is None:
        return ""
    try:  # agent-controlled repo: hardened, sandboxed git (R22); fails closed
        proc = untrusted.git(workspace, "log", "--format=commit%n%B", f"{BASE_TAG}..HEAD",
                             write=False, check=False, text=True)
    except untrusted.UnsafePath as exc:
        if notes is not None:
            notes["git"] = str(exc)
        return ""
    return proc.stdout.strip() if proc.returncode == 0 else ""


def judge_prompt(task: Task, run_dir: Path, items: list[dict], screens: list[str],
                 commits: str) -> str:
    listing = json.dumps([{"id": i["id"], "text": i["text"]} for i in items], indent=2)
    diff = (Path(run_dir) / "diff.patch")
    final = (Path(run_dir) / "final.txt")
    return (
        "An agent worked on the task below. Decide, for each checklist item, whether the "
        "delivered work satisfies it (hit = true) or not (hit = false). Judge from the "
        "evidence: the code diff, the commit messages, and the screenshots. The final "
        "message is the agent's own account: it counts as evidence only for items about "
        "what the agent told the user, never as proof the code does something. When the "
        "evidence doesn't show an item is satisfied, it is not. Give one entry per item, "
        "with a one-sentence evidence note.\n\n"
        f"## Task given\n{J.redact(task.prompt)}\n\n"
        f"## Checklist items\n{listing}\n\n"
        f"## Code diff (against the starting state)\n```diff\n"
        f"{J.diff_for_judge(diff.read_text(errors='replace') if diff.is_file() else '')}```\n\n"
        f"## Commit messages\n{J.clip(J.redact(commits), MAX_COMMITS_CHARS) or '(no commits)'}\n\n"
        f"## Screenshots\n{', '.join(screens) or '(none)'}\n\n"
        f"## Final message\n"
        f"{J.clip(J.redact(final.read_text(errors='replace') if final.is_file() else ''), J.MAX_FINAL_CHARS)}\n"
    )


def _votes(task: Task, run_dir: Path, items: list[dict], judges: list[ModelSpec],
           errors: dict[str, str], notes: dict[str, str]) -> dict[str, dict[str, bool | None]]:
    """item id -> {judge cli: hit or None}; failures and unanswered items land in
    ``errors``."""
    ids = [i["id"] for i in items]
    votes: dict[str, dict[str, bool | None]] = {i: {} for i in ids}
    stage = Path(tempfile.mkdtemp(prefix="checklist-", dir=J.work_base()))
    try:
        try:
            images = J.stage_images(
                [("", s) for s in sorted((Path(run_dir) / "screens").glob("*.png"))], stage)
        except J.JudgeError as exc:
            for judge in judges:
                errors[judge.cli] = str(exc)
            return {i: {j.cli: None for j in judges} for i in ids}
        prompt = judge_prompt(task, run_dir, items, [p.name for p in images],
                              _commits(workspace_of(run_dir), notes))
        for judge in judges:
            try:
                answer = J.judge_call(judge, prompt, images, J.CHECKLIST_SCHEMA)
            except J.JudgeError as exc:
                errors[judge.cli] = str(exc)
                answer = {"items": []}
            said = {a["id"]: a["hit"] for a in answer["items"]}
            for i in ids:
                votes[i][judge.cli] = said.get(i)
            if judge.cli not in errors and (missing := [i for i in ids if i not in said]):
                errors[judge.cli] = f"judge left items unanswered: {missing}"
    finally:
        shutil.rmtree(stage, ignore_errors=True)
    return votes


def grade(task: Task, run_dir: Path, judges: list[ModelSpec]) -> dict:
    if task.checklist is None or not task.checklist.is_file():
        return not_applicable(run_dir, "checklist", "no checklist.json")
    run_id = run_meta(run_dir).get("run_id") or Path(run_dir).name
    J.check_judge_family(J.parse_run_id(run_id)[1], judges)
    workspace = workspace_of(run_dir)
    if workspace is None:
        return not_applicable(run_dir, "checklist",
                              f"no workspace (status {run_meta(run_dir).get('status')})")
    items = load_items(task.checklist)

    errors: dict[str, str] = {}
    notes: dict[str, str] = {}
    judge_items = [i for i in items if i["check"] == "judge"]
    votes = _votes(task, run_dir, judge_items, judges, errors, notes) if judge_items else {}
    invalid = bool(errors)

    graded = []
    for item in items:
        if item["check"] == "script":
            graded.append({"id": item["id"], "hit": _run_script(item, workspace, run_dir),
                           "by": "script"})
        else:
            v = votes[item["id"]]
            yes = sum(x is True for x in v.values())
            graded.append({"id": item["id"], "hit": None if invalid else yes * 2 > len(judges),
                           "by": "judge", "votes": v})
    if invalid:
        score = None
    else:
        score = sum(i["hit"] for i in graded) / len(graded) if graded else 0.0
    result = {"applicable": True, "items": graded, "score": score, "judge_errors": errors,
              "notes": notes}
    if invalid:
        result["invalid"] = True
    return write_grade(run_dir, "checklist", result)
