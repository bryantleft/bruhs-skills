"""``bruhsbench digest``: one markdown file the user reviews before ``bruhsbench freeze``.

For every real (private) task that isn't held out: id, category, the prompt verbatim, and
each checklist item / known issue as graded (checklist.json, known_issues.json) with its
source and any ``flag_for_user`` note. Sources come from the task's ``*_src.py`` (the
``source`` / ``audit_ref`` / ``fix`` of each entry), else from the task's NOTES.md table row
for that id. Seeded tasks get one line each. Held-out tasks are left out (sealed). The
default output, ``tasks-private/_digest.md``, is gitignored with the private tasks.
"""

from __future__ import annotations

import json
import re
import runpy
from datetime import date
from pathlib import Path

from .tasks import BENCH_DIR, PRIVATE_DIR, is_private
from .types import Task

DIGEST_FILE = BENCH_DIR / PRIVATE_DIR / "_digest.md"
SOURCE_KEYS = ("source", "audit_ref", "fix")


def _src_entries(task: Task) -> tuple[dict[str, dict], list[str]]:
    """``{id: entry}`` from every list of dicts with an ``id`` in the task's ``*_src.py``
    files (trusted task sources), and load problems."""
    entries: dict[str, dict] = {}
    problems: list[str] = []
    for src in sorted(Path(task.dir).glob("*_src.py")):
        try:
            module = runpy.run_path(str(src), run_name="bruhsbench_digest")
        except Exception as exc:  # a broken source file is reported, not fatal
            problems.append(f"could not load {src.name}: {type(exc).__name__}: {exc}")
            continue
        for value in module.values():
            if isinstance(value, list) and value and all(
                    isinstance(e, dict) and "id" in e for e in value):
                for e in value:
                    entries.setdefault(e["id"], {}).update(e)
    return entries, problems


def _notes_rows(task: Task) -> dict[str, str]:
    """``{id: rest of the row}`` for NOTES.md table rows whose first cell is an id."""
    notes = Path(task.dir) / "NOTES.md"
    if not notes.is_file():
        return {}
    rows = {}
    for line in notes.read_text().splitlines():
        cells = [c.strip() for c in line.strip().strip("|").split("|")]
        if line.lstrip().startswith("|") and len(cells) >= 2:
            key = cells[0].strip("`")
            if re.fullmatch(r"[a-z0-9][a-z0-9-]*", key):
                rows.setdefault(key, " | ".join(cells[1:]))
    return rows


def _source(item_id: str, entries: dict[str, dict], notes: dict[str, str]) -> str | None:
    e = entries.get(item_id, {})
    parts = [f"{k}: {e[k]}" if k != "source" else str(e[k]) for k in SOURCE_KEYS if e.get(k)]
    if parts:
        return "; ".join(parts)
    return f"NOTES.md: {notes[item_id]}" if item_id in notes else None


def _fence(text: str) -> str:
    longest = max((len(m) for m in re.findall(r"`+", text)), default=0)
    return "`" * max(3, longest + 1)


def _load_json(path: Path | None):
    return json.loads(path.read_text()) if path is not None and path.is_file() else None


def _items(task: Task) -> list[dict]:
    data = _load_json(task.checklist)
    return list(data.get("items", [])) if isinstance(data, dict) else []


def _issues(task: Task) -> list[dict]:
    data = _load_json(task.known_issues)
    return list(data) if isinstance(data, list) else []


def _grading(task: Task) -> str:
    parts = []
    if task.checks:
        parts.append("checks " + ", ".join(sorted(k for k in task.checks if k != "hidden")))
    if task.hidden_tests is not None and task.hidden_tests.is_dir():
        files = sorted(p.relative_to(task.hidden_tests).as_posix()
                       for p in task.hidden_tests.rglob("*") if p.is_file())
        parts.append(f"hidden tests ({', '.join(files)})")
    if task.pages:
        parts.append(f"screenshots of {', '.join(task.pages)}")
    return "; ".join(parts) or "none besides the checklist/known issues"


def _flag(e: dict) -> list[str]:
    return [f"   - **Flag for user:** {e['flag_for_user']}"] if e.get("flag_for_user") else []


def real_task_section(task: Task) -> str:
    entries, problems = _src_entries(task)
    notes = _notes_rows(task)
    fence = _fence(task.prompt)
    out = [f"### {task.id}", "",
           f"- Category: {task.category}",
           f"- Repo: {task.repo.name if task.repo else '-'} @ {(task.base or '-')[:12]}",
           f"- Grading: {_grading(task)}", "",
           "Prompt (verbatim):", "", f"{fence}text", task.prompt.rstrip("\n"), fence, ""]
    out += [f"> {p}" for p in problems]
    items, issues = _items(task), _issues(task)
    if items:
        out += [f"Checklist ({len(items)} items):", ""]
        for n, it in enumerate(items, 1):
            src = _source(it["id"], entries, notes)
            out += [f"{n}. `{it['id']}` ({it.get('check', '?')}): {it.get('text', '')}",
                    f"   - Source: {src or '**none found**'}", *_flag(entries.get(it["id"], {}))]
        out.append("")
    if issues:
        out += [f"Known issues ({len(issues)}):", ""]
        for n, ki in enumerate(issues, 1):
            lines = ki.get("lines") or []
            where = f"{ki.get('file', '?')}:{'-'.join(str(x) for x in lines)}" if lines \
                else ki.get("file", "?")
            decoy = " (decoy)" if ki.get("decoy") else ""
            src = _source(ki["id"], entries, notes)
            out += [f"{n}. `{ki['id']}` [{ki.get('severity', '?')}{decoy}] {where}: "
                    f"{ki.get('summary', '')}",
                    f"   - Source: {src or '**none found**'}", *_flag(entries.get(ki["id"], {}))]
        out.append("")
    graded = {i["id"] for i in items} | {k["id"] for k in issues}
    stale = sorted(i for i, e in entries.items()
                   if i not in graded and ("check" in e or "summary" in e))
    if stale:
        out += [f"> In a *_src.py but not in the graded JSON (rebuild it?): {', '.join(stale)}",
                ""]
    if not items and not issues:
        out += ["No checklist or known issues (graded by its checks / hidden tests).", ""]
    return "\n".join(out)


def seeded_line(task: Task) -> str:
    first = next((ln.strip() for ln in task.prompt.splitlines() if ln.strip()), "")
    if len(first) > 120:
        first = first[:117] + "..."
    grading = []
    if items := _items(task):
        grading.append(f"{len(items)} checklist items")
    if issues := _issues(task):
        grading.append(f"{len(issues)} known issues")
    if task.hidden_tests is not None and task.hidden_tests.is_dir():
        grading.append("hidden tests")
    return (f"- `{task.id}` ({task.category}): {first}"
            + (f" [{', '.join(grading)}]" if grading else ""))


def render(tasks: list[Task]) -> str:
    visible = [t for t in tasks if not t.heldout]
    real = sorted((t for t in visible if is_private(t)), key=lambda t: t.id)
    seeded = sorted((t for t in visible if not is_private(t)), key=lambda t: t.id)
    out = ["# bruhsbench task digest", "",
           f"Generated {date.today().isoformat()} by `bruhsbench digest`. Review every prompt "
           "and checklist item / known issue below, then run `bruhsbench freeze`. Held-out "
           "tasks are not listed.", "",
           f"## Real tasks ({len(real)})", ""]
    out += [real_task_section(t) for t in real]
    out += [f"## Seeded tasks ({len(seeded)})", "", *[seeded_line(t) for t in seeded], ""]
    return "\n".join(out)


def write_digest(tasks: list[Task], out: Path = DIGEST_FILE) -> Path:
    out = Path(out)
    out.parent.mkdir(parents=True, exist_ok=True)
    out.write_text(render(tasks))
    return out
