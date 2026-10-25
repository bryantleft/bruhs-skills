"""Turn graded runs into the headline result: per-task win/tie/loss and per-model rates.

Win rule (frozen, Global Constraints): each category has one primary metric and a tie
margin; cost, time, turns and scope creep never decide a task.

=================  ==============================================  ==================
category           primary metric per repeat                        tie margin
=================  ==============================================  ==================
feature / debug    hidden tests pass AND no regressions AND         1 of 3 repeats
                   honest-done -> 1/0
audit              F1 vs known issues                               0.05
ui / copy          blind pairwise preference (bruhs 1, tie .5, 0)   55/45
pr-review          checklist all hit AND checks green AND hidden    1 of 3 repeats
                   tests pass -> 1/0
ship               checklist score                                  10 points
=================  ==============================================  ==================

feature/debug/pr-review (Ruling R26): a win/loss when one arm has *more than one* more
passing repeat (sum(bruhs) - sum(bare) > 1, i.e. 2+), over the surviving matched repeats;
otherwise a tie, whatever the number of surviving repeats. audit/ship: when the bruhs mean
minus the bare mean is *more than* the margin. ui/copy: when the mean preference is
>= 0.55 / <= 0.45 (Ruling R23 b).

Aggregation (Ruling R23):

a. A run that is ``contaminated`` (True), ``status`` error or setup_failed, or a
   timeout with an empty diff excludes its (task, model, repeat) pair from BOTH arms, as
   does a missing arm. ``contaminated`` None is counted and reported, not excluded.
b. ui/copy: every valid judge verdict of a pair counts (bruhs 1, tie 0.5, bare 0, via
   ``_pairs/pairs_key.json``); the task's preference is the mean over all verdicts
   across repeats. A judge error (``winner`` null) is excluded and counted. If the user's
   spot-check agreement with the judges is below 0.75, ui/copy use the user's picks only.
c. A missing metric (grader error, checklist invalid / score None) drops that pair; a
   regressions value of None means "not clean" (metric 0).
d. The summary carries health counts per arm, bruhs activation per CLI and a bare-arm
   bruhs-mention check.
"""

from __future__ import annotations

import json
import random
import re
from collections.abc import Sequence
from dataclasses import dataclass, field
from pathlib import Path
from statistics import mean
from typing import Literal

from .graders import read_grade
from .tasks import is_private, load_all_tasks
from .types import MODELS, Task

Decision = Literal["win", "loss", "tie"]
ARMS = ("bare", "bruhs")
PAIRWISE = ("ui", "copy")
# R26: "1 of 3 repeats" is a count: win/loss needs 2+ more passing repeats in one arm
# (sums over the surviving, matched repeats), whatever the number of surviving repeats
REPEAT_CATEGORIES = ("feature", "debug", "pr-review")
REPEAT_MARGIN = 1  # passing repeats
MARGINS = {"audit": 0.05, "ship": 0.10}  # on the difference of means
PREF_WIN, PREF_LOSS = 0.55, 0.45
PREF_VALUE = {"bruhs": 1.0, "tie": 0.5, "bare": 0.0}
OUTCOME_VALUE = {"win": 1.0, "tie": 0.5, "loss": 0.0}
AGREEMENT_THRESHOLD = 0.75
EPS = 1e-9  # a difference exactly at a margin must not tip over it by float noise
GRADES = ("commands", "scope", "checklist", "audit", "honesty")
RESAMPLES = 10_000


# --------------------------------------------------------------------------- metric


def _ok(grade: dict | None, key: str) -> bool:
    """The grade exists, applies, and has ``key`` (a grader exception has only
    ``applicable`` and ``error``)."""
    return bool(grade) and bool(grade.get("applicable")) and key in grade


def _hidden_pass(cmd: dict) -> bool:
    if not (cmd.get("hidden") or {}).get("applicable"):
        return True  # no hidden tests for this task: nothing to fail
    return cmd.get("hidden_total", 0) > 0 and cmd.get("hidden_pass") == cmd["hidden_total"]


def primary_metric(task: Task, grades: dict) -> float | None:
    """The task category's primary metric for one run, or None when it is missing
    (grader error, invalid checklist): that repeat's pair is then dropped."""
    cat = task.category
    if cat in PAIRWISE:
        raise ValueError(f"{cat} tasks are scored pairwise, not per run")
    cmd = grades.get("commands")
    if cat in ("feature", "debug"):
        hon = grades.get("honesty")
        if not _ok(cmd, "checks") or not _ok(hon, "honest_done"):
            return None
        clean = cmd.get("regressions") == []  # None: not computed = not clean (R23 c)
        return float(_hidden_pass(cmd) and clean and bool(hon["honest_done"]))
    if cat == "audit":
        audit = grades.get("audit")
        return float(audit["f1"]) if _ok(audit, "f1") else None
    checklist = grades.get("checklist")
    if not _ok(checklist, "score") or checklist.get("invalid") or checklist["score"] is None:
        return None
    if cat == "ship":
        return float(checklist["score"])
    if cat == "pr-review":
        if not _ok(cmd, "checks"):
            return None
        green = all(cmd["checks"].values()) and _hidden_pass(cmd)
        return float(checklist["score"] >= 1.0 - EPS and green)
    raise ValueError(f"unknown category {cat!r}")


def preference(prefs: Sequence[str]) -> float:
    return mean(PREF_VALUE[p] for p in prefs)


def decide(task: Task, bare: Sequence[float], bruhs: Sequence[float],
           prefs: Sequence[str] | None) -> Decision:
    """bruhs vs bare on one task (for one model) by the frozen margins.

    ``bare``/``bruhs``: the primary metric per surviving repeat; ``prefs``: for ui/copy,
    every valid verdict as "bruhs" | "bare" | "tie". Raises ValueError without data.
    """
    if task.category in PAIRWISE:
        if not prefs:
            raise ValueError(f"{task.id}: no valid pairwise verdicts")
        p = preference(prefs)
        if p >= PREF_WIN - EPS:
            return "win"
        if p <= PREF_LOSS + EPS:
            return "loss"
        return "tie"
    if not bare or not bruhs:
        raise ValueError(f"{task.id}: no surviving repeats in one arm")
    if task.category in REPEAT_CATEGORIES:
        margin, delta = REPEAT_MARGIN, sum(bruhs) - sum(bare)
    else:
        margin, delta = MARGINS[task.category], mean(bruhs) - mean(bare)
    if delta > margin + EPS:
        return "win"
    if delta < -margin - EPS:
        return "loss"
    return "tie"


def bootstrap_ci(values: Sequence[float], *, resamples: int = RESAMPLES, seed: int = 0,
                 level: float = 0.95) -> tuple[float, float] | None:
    """Percentile bootstrap CI of the mean of ``values`` (resampled with replacement)."""
    if not values:
        return None
    rng = random.Random(seed)
    n = len(values)
    means = sorted(sum(rng.choices(values, k=n)) / n for _ in range(resamples))
    tail = (1 - level) / 2
    lo = means[int(tail * resamples)]
    hi = means[min(resamples - 1, int((1 - tail) * resamples))]
    return lo, hi


# --------------------------------------------------------------------------- transcripts

# bruhs docs read or a bruhs skill invoked: a path into the installed bruhs tree
# (claude plugin dir, codex .agents/skills, grok .grok/skills) or a Skill call
_ACTIVATION_RE = re.compile(
    r"(?:plugins|skills)/bruhs/|\"skill\"\s*:\s*\"bruhs|\"command\"\s*:\s*\"/?bruhs:")
_BRUHS_WORD_RE = re.compile(r"\bbruhs\b", re.IGNORECASE)


def _events_text(transcript: str) -> str:
    """The transcript without session-init events (claude's init lists installed
    skills and the plugin path whether or not anything is used)."""
    keep = []
    for line in transcript.splitlines():
        try:
            event = json.loads(line)
        except ValueError:
            keep.append(line)
            continue
        if isinstance(event, dict) and event.get("type") == "system" and \
                event.get("subtype") == "init":
            continue
        keep.append(line)
    return "\n".join(keep).replace("\\/", "/")


def activated(transcript: str) -> bool:
    """A bruhs-arm transcript shows bruhs skill/command docs read or invoked."""
    return bool(_ACTIVATION_RE.search(_events_text(transcript)))


def bare_leak(transcript: str) -> bool:
    """A bare-arm transcript mentions bruhs at all (``bruhsbench`` paths don't count)."""
    return bool(_BRUHS_WORD_RE.search(_events_text(transcript)))


# --------------------------------------------------------------------------- loading


@dataclass
class Run:
    run_id: str
    task_id: str
    cli: str
    arm: str
    repeat: int
    dir: Path
    meta: dict
    grades: dict[str, dict | None]

    @property
    def exclusion(self) -> str | None:
        """Why this run excludes its pair (R23 a), or None."""
        status = self.meta.get("status")
        if self.meta.get("contaminated") is True:
            return "contaminated"
        if status in ("error", "setup_failed"):
            return status
        if status == "timeout" and not _nonempty(self.dir / "diff.patch"):
            return "timeout_no_diff"
        return None


def _nonempty(path: Path) -> bool:
    return path.is_file() and path.stat().st_size > 0


def parse_run_id(run_id: str) -> tuple[str, str, str, int]:
    task_id, cli, arm, rep = run_id.rsplit("__", 3)
    if not rep.startswith("r") or not rep[1:].isdigit() or arm not in ARMS:
        raise ValueError(f"not a run id: {run_id!r}")
    return task_id, cli, arm, int(rep[1:])


def load_runs(results_root: Path) -> list[Run]:
    runs = []
    for p in sorted(Path(results_root).glob("*/result.json")):
        try:
            task_id, cli, arm, repeat = parse_run_id(p.parent.name)
        except ValueError:
            continue
        runs.append(Run(p.parent.name, task_id, cli, arm, repeat, p.parent,
                        json.loads(p.read_text()),
                        {g: read_grade(p.parent, g) for g in GRADES}))
    return runs


def load_verdicts(results_root: Path) -> dict[tuple[str, str, int], list[dict]]:
    """(task, cli, repeat) -> pairwise verdicts in arm terms:
    ``{"judge": cli, "pref": "bruhs" | "bare" | "tie" | None, "error": str | None}``."""
    pairs = Path(results_root) / "_pairs"
    key_path = pairs / "pairs_key.json"
    key = json.loads(key_path.read_text()) if key_path.is_file() else {}
    out: dict[tuple[str, str, int], list[dict]] = {}
    for pair_id, shown in sorted(key.items()):
        path = pairs / f"{pair_id}.json"
        if not path.is_file():
            continue
        rec = json.loads(path.read_text())
        winner = rec.get("winner")
        if winner is None:
            pref = None
        elif winner == "tie":
            pref = "tie"
        else:
            pref = parse_run_id(shown[winner])[2]
        unit = (rec["task_id"], rec["model_cli"], int(rec["repeat"]))
        out.setdefault(unit, []).append(
            {"judge": rec.get("judge_cli"), "pref": pref, "error": rec.get("error")})
    return out


def unit_id(task_id: str, cli: str, repeat: int) -> str:
    return f"{task_id}__{cli}__r{repeat}"


def user_picks(results_root: Path) -> dict[str, str]:
    """Spot-check unit id -> the user's pick in arm terms ("bruhs" | "bare" | "tie")."""
    path = Path(results_root) / "spotcheck.json"
    if not path.is_file():
        return {}
    picks = json.loads(path.read_text()).get("picks", {})
    return {unit: p["arm"] for unit, p in picks.items() if p.get("arm") in PREF_VALUE}


# --------------------------------------------------------------------------- summary


@dataclass
class TaskOutcome:
    task_id: str
    category: str
    cli: str
    private: bool
    seeded: bool
    decision: Decision | None  # None: no surviving data
    bare: list[float] = field(default_factory=list)
    bruhs: list[float] = field(default_factory=list)
    prefs: list[str] = field(default_factory=list)
    excluded: list[int] = field(default_factory=list)  # repeats dropped from both arms
    missing: list[int] = field(default_factory=list)  # repeats whose metric was missing
    judge_errors: int = 0

    @property
    def delta(self) -> float | None:
        """bruhs minus bare on the primary metric; ui/copy: preference minus 0.5."""
        if self.category in PAIRWISE:
            return preference(self.prefs) - 0.5 if self.prefs else None
        if self.bare and self.bruhs:
            return mean(self.bruhs) - mean(self.bare)
        return None


@dataclass
class Rate:
    wins: int = 0
    ties: int = 0
    losses: int = 0
    win_rate: float | None = None  # (wins + ties/2) / tasks
    ci: tuple[float, float] | None = None

    @property
    def n(self) -> int:
        return self.wins + self.ties + self.losses


@dataclass
class ModelSummary:
    cli: str
    model: str
    overall: Rate
    seeded: Rate
    per_category: dict[str, dict]
    arms: dict[str, dict]
    judge_errors: int = 0


@dataclass
class Summary:
    results_root: Path
    tasks: list[TaskOutcome]
    models: dict[str, ModelSummary]
    counts: dict[str, dict[str, int]]  # arm -> health counts, all CLIs
    counts_by_cli: dict[str, dict[str, dict[str, int]]]  # cli -> arm -> health counts
    activation: dict[str, dict]
    bare_leaks: dict[str, list[str]]
    agreement: float | None
    ui_source: Literal["judges", "user", "judges-unvalidated"]
    task_info: dict[str, Task]
    matrix: dict


def _rate(outcomes: list[TaskOutcome], seed: int, resamples: int) -> Rate:
    decided = [o.decision for o in outcomes if o.decision is not None]
    values = [OUTCOME_VALUE[d] for d in decided]
    return Rate(decided.count("win"), decided.count("tie"), decided.count("loss"),
                mean(values) if values else None,
                bootstrap_ci(values, resamples=resamples, seed=seed))


def _mean(xs: list) -> float | None:
    xs = [x for x in xs if x is not None]
    return mean(xs) if xs else None


def _arm_stats(runs: list[Run]) -> dict:
    scope = [r.grades.get("scope") or {} for r in runs]
    return {
        "runs": len(runs),
        "cost_usd": _mean([r.meta.get("cost_usd") for r in runs]),
        "wall_s": _mean([r.meta.get("wall_s") for r in runs]),
        "turns": _mean([r.meta.get("turns") for r in runs]),
        "input_tokens": _mean([r.meta.get("input_tokens") for r in runs]),
        "output_tokens": _mean([r.meta.get("output_tokens") for r in runs]),
        "scope_lines_outside": _mean([s.get("lines_outside") for s in scope]),
        "scope_files_outside": _mean([len(s["files_outside"]) if "files_outside" in s
                                      else None for s in scope]),
    }


def _counts(runs: list[Run]) -> dict[str, dict[str, int]]:
    counts = {}
    for arm in ARMS:
        rs = [r for r in runs if r.arm == arm]
        st = [r.meta.get("status") for r in rs]
        counts[arm] = {
            "runs": len(rs),
            "ok": st.count("ok"),
            "error": st.count("error"),
            "setup_failed": st.count("setup_failed"),
            "timeout": st.count("timeout"),
            "timeout_no_diff": sum(r.exclusion == "timeout_no_diff" for r in rs),
            "contaminated": sum(r.meta.get("contaminated") is True for r in rs),
            "contaminated_unknown": sum(r.meta.get("contaminated") is None for r in rs),
            "orphaned_output": sum(bool(r.meta.get("orphaned_output")) for r in rs),
            "checklist_invalid": sum(bool((r.grades.get("checklist") or {}).get("invalid"))
                                     for r in rs),
            "grader_errors": sum(1 for r in rs for g in r.grades.values()
                                 if g and g.get("applicable") and set(g) == {"applicable",
                                                                             "error"}),
        }
    return counts


def _transcript(run: Run) -> str:
    p = run.dir / "transcript.jsonl"
    return p.read_text(errors="replace") if p.is_file() else ""


def summarize(results_root: Path, tasks: Sequence[Task] | None = None, *, seed: int = 0,
              resamples: int = RESAMPLES) -> Summary:
    """Aggregate every graded run under ``results_root`` (see the module docstring).

    ``tasks`` defaults to every task under ``tasks.TASK_ROOTS``; runs of tasks not in it
    are ignored.
    """
    from .spotcheck import agreement as spot_agreement

    results_root = Path(results_root)
    by_id = {t.id: t for t in (tasks if tasks is not None else load_all_tasks())}
    runs = [r for r in load_runs(results_root) if r.task_id in by_id]
    verdicts = load_verdicts(results_root)
    agree = spot_agreement(results_root)
    picks = user_picks(results_root)
    ui_source = ("judges-unvalidated" if agree is None
                 else "user" if agree < AGREEMENT_THRESHOLD else "judges")

    units: dict[tuple[str, str, int], dict[str, Run]] = {}
    for r in runs:
        units.setdefault((r.task_id, r.cli, r.repeat), {})[r.arm] = r

    outcomes: dict[tuple[str, str], TaskOutcome] = {}
    valid_runs: list[Run] = []
    for (task_id, cli, repeat), arms in sorted(units.items()):
        task = by_id[task_id]
        o = outcomes.setdefault((task_id, cli), TaskOutcome(
            task_id, task.category, cli, is_private(task), not is_private(task), None))
        if set(arms) != set(ARMS) or any(r.exclusion for r in arms.values()):
            o.excluded.append(repeat)
            continue
        valid_runs += arms.values()
        if task.category in PAIRWISE:
            if ui_source == "user":
                pick = picks.get(unit_id(task_id, cli, repeat))
                if pick:
                    o.prefs.append(pick)
            else:
                for v in verdicts.get((task_id, cli, repeat), []):
                    if v["pref"] is None:
                        o.judge_errors += 1
                    else:
                        o.prefs.append(v["pref"])
            continue
        bare = primary_metric(task, arms["bare"].grades)
        bruhs = primary_metric(task, arms["bruhs"].grades)
        if bare is None or bruhs is None:
            o.missing.append(repeat)
            continue
        o.bare.append(bare)
        o.bruhs.append(bruhs)

    for o in outcomes.values():
        task = by_id[o.task_id]
        if (o.prefs if task.category in PAIRWISE else (o.bare and o.bruhs)):
            o.decision = decide(task, o.bare, o.bruhs, o.prefs)

    models: dict[str, ModelSummary] = {}
    for spec in MODELS:
        mine = [o for o in outcomes.values() if o.cli == spec.cli]
        if not mine:
            continue
        per_cat = {}
        for cat in sorted({o.category for o in mine}):
            cat_o = [o for o in mine if o.category == cat]
            per_cat[cat] = {"tasks": len(cat_o), "mean_delta": _mean([o.delta for o in cat_o]),
                            **{d: sum(o.decision == d for o in cat_o)
                               for d in ("win", "tie", "loss")}}
        mine_runs = [r for r in valid_runs if r.cli == spec.cli]
        models[spec.cli] = ModelSummary(
            spec.cli, spec.model,
            _rate(mine, seed, resamples), _rate([o for o in mine if o.seeded], seed, resamples),
            per_cat, {arm: _arm_stats([r for r in mine_runs if r.arm == arm]) for arm in ARMS},
            judge_errors=sum(o.judge_errors for o in mine))

    activation, leaks = {}, {}
    for spec in MODELS:
        bruhs_runs = [r for r in runs if r.cli == spec.cli and r.arm == "bruhs"
                      and r.meta.get("status") not in ("error", "setup_failed")]
        bare_runs = [r for r in runs if r.cli == spec.cli and r.arm == "bare"]
        if not bruhs_runs and not bare_runs:
            continue
        hit = sum(activated(_transcript(r)) for r in bruhs_runs)
        activation[spec.cli] = {"runs": len(bruhs_runs), "activated": hit,
                                "rate": hit / len(bruhs_runs) if bruhs_runs else None}
        leaks[spec.cli] = sorted(r.run_id for r in bare_runs if bare_leak(_transcript(r)))

    matrix_path = results_root / "matrix.json"
    matrix = json.loads(matrix_path.read_text()) if matrix_path.is_file() else {}
    order = {m.cli: i for i, m in enumerate(MODELS)}
    return Summary(
        results_root, sorted(outcomes.values(), key=lambda o: (o.category, o.task_id,
                                                               order.get(o.cli, 9))),
        models, _counts(runs),
        {m.cli: _counts([r for r in runs if r.cli == m.cli]) for m in MODELS
         if any(r.cli == m.cli for r in runs)},
        activation, leaks, agree, ui_source,
        {t: by_id[t] for t in sorted({o.task_id for o in outcomes.values()})}, matrix)
