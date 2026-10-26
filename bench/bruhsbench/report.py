"""Render a :class:`score.Summary` as a self-contained HTML report and a markdown twin.

``report.html`` has inline CSS, an inline SVG chart per model and screenshots embedded as
base64 PNG: it fetches nothing. ``private=False`` (the publishable report) shows private
tasks (real repos) only as "private <category> task N" with their scores: no task id,
prompt, path, repo name or screenshot; no local paths appear at all.

Chart (dataviz method): W/T/L is polarity, so a diverging pair (blue win, red loss) with a
neutral gray tie, 2px surface gaps between segments, 4px rounded data-ends, counts as
direct labels; the win-rate chart is dot + 95% CI whisker on one 0-100% axis with a 50%
"no difference" reference, overall and seeded-only as categorical slots 1-2 with a
legend. Colors are CSS custom properties with selected dark-mode steps; every mark has a
hover/focus tooltip, and every value is also in the tables.
"""

from __future__ import annotations

import base64
import html
from dataclasses import asdict
from datetime import date
from pathlib import Path

from jinja2 import Environment, FileSystemLoader, select_autoescape
from markupsafe import Markup

from .score import ARMS, PAIRWISE, ModelSummary, Rate, Summary, TaskOutcome, parse_run_id
from .types import MODELS

TEMPLATES = Path(__file__).parent / "templates"
MAX_EXAMPLES = 6
EXAMPLE_SHOT = "__desktop__light.png"
CATEGORY_ORDER = ("feature", "debug", "audit", "ui", "copy", "pr-review", "ship")
METRIC_LABEL = {"feature": "tests+clean+honest (0/1)", "debug": "tests+clean+honest (0/1)",
                "audit": "F1", "ui": "pairwise preference", "copy": "pairwise preference",
                "pr-review": "all fixed+pushback+green (0/1)", "ship": "checklist score"}
UI_SOURCE_NOTE = {
    "judges": "UI/copy decided by the two cross-family judges (user spot-check agreement "
              "{agreement}, at or above the 75% bar).",
    "user": "UI/copy decided by the user's blind picks only: judge agreement with the user "
            "was {agreement}, below the 75% bar. Reduced sample.",
    "judges-unvalidated": "UI/copy decided by the two cross-family judges; the user "
                          "spot-check has not been done yet, so these are not validated.",
}


# --------------------------------------------------------------------------- formatting


def pct(x: float | None) -> str:
    return "n/a" if x is None else f"{x * 100:.0f}%"


def ci_text(ci: tuple[float, float] | None) -> str:
    return "n/a" if ci is None else f"{ci[0] * 100:.0f}-{ci[1] * 100:.0f}%"


def num(x: float | None, digits: int = 2) -> str:
    return "n/a" if x is None else f"{x:,.{digits}f}"


def signed(x: float | None) -> str:
    return "n/a" if x is None else f"{x:+.3f}"


def money(x: float | None) -> str:
    return "n/a" if x is None else f"${x:,.2f}"


# --------------------------------------------------------------------------- names


class Names:
    """Display names: real ids in the private report; aliases for private tasks in
    the public one."""

    def __init__(self, summary: Summary, private: bool):
        self.private = private
        self.alias: dict[str, str] = {}
        counters: dict[str, int] = {}
        for o in sorted({(o.category, o.task_id): o for o in summary.tasks}.values(),
                        key=lambda o: (o.category, o.task_id)):
            if o.private and not private:
                counters[o.category] = counters.get(o.category, 0) + 1
                self.alias[o.task_id] = f"private {o.category} task {counters[o.category]}"

    def task(self, task_id: str) -> str:
        return self.alias.get(task_id, task_id)

    def hidden(self, task_id: str) -> bool:
        return task_id in self.alias

    def run(self, run_id: str) -> str:
        task_id, cli, arm, rep = parse_run_id(run_id)
        return f"{self.task(task_id)} / {cli} / {arm} / r{rep}"


# --------------------------------------------------------------------------- chart

ROW_H, BAR_H, LABEL_W, BAR_W, GAP = 44, 24, 150, 420, 2


def _tip(text: str) -> str:
    t = html.escape(text)
    return f'tabindex="0" role="img" aria-label="{t}" data-tip="{t}"'


def _rounded_bar(x: float, y: float, w: float, h: float, left: bool, right: bool,
                 cls: str, tip: str) -> str:
    """A bar segment with 4px rounded corners only on its outer (data) ends."""
    r = min(4.0, w / 2, h / 2)
    rl, rr = (r if left else 0.0), (r if right else 0.0)
    d = (f"M{x + rl},{y} H{x + w - rr} " + (f"Q{x + w},{y} {x + w},{y + rr} " if rr else "")
         + f"V{y + h - rr} " + (f"Q{x + w},{y + h} {x + w - rr},{y + h} " if rr else "")
         + f"H{x + rl} " + (f"Q{x},{y + h} {x},{y + h - rl} " if rl else "")
         + f"V{y + rl} " + (f"Q{x},{y} {x + rl},{y} " if rl else "") + "Z")
    return f'<path class="mark {cls}" d="{d}" {_tip(tip)}/>'


def wtl_chart(models: list[ModelSummary]) -> Markup:
    """Per model: one stacked bar of tasks won / tied / lost."""
    height = ROW_H * len(models) + 28
    out = [f'<svg class="chart" viewBox="0 0 {LABEL_W + BAR_W + 60} {height}" role="img" '
           f'aria-label="Tasks won, tied and lost by the bruhs arm, per model">']
    for i, m in enumerate(models):
        y = i * ROW_H + 10
        out.append(f'<text class="label" x="0" y="{y + BAR_H / 2 + 5}">{html.escape(m.model)}</text>')
        r = m.overall
        segs = [(k, n) for k, n in (("win", r.wins), ("tie", r.ties), ("loss", r.losses)) if n]
        total = r.n
        if not total:
            out.append(f'<text class="muted" x="{LABEL_W}" y="{y + BAR_H / 2 + 5}">no decided tasks</text>')
            continue
        avail = BAR_W - GAP * (len(segs) - 1)
        x = float(LABEL_W)
        for j, (kind, n) in enumerate(segs):
            w = avail * n / total
            noun = {"win": "won", "tie": "tied", "loss": "lost"}[kind]
            out.append(_rounded_bar(x, y, w, BAR_H, j == 0, j == len(segs) - 1, kind,
                                    f"{m.model}: {n} of {total} tasks {noun}"))
            if w >= 28:  # direct label only where it fits with padding
                ink = "ink-on-tie" if kind == "tie" else "ink-on-fill"
                out.append(f'<text class="{ink}" x="{x + w / 2}" y="{y + BAR_H / 2 + 5}" '
                           f'text-anchor="middle">{n}</text>')
            x += w + GAP
    ly = ROW_H * len(models) + 18
    for k, (kind, label) in enumerate((("win", "bruhs won"), ("tie", "tie"),
                                       ("loss", "bruhs lost"))):
        lx = LABEL_W + k * 110
        out.append(f'<rect class="{kind}" x="{lx}" y="{ly - 9}" width="10" height="10" rx="2"/>'
                   f'<text class="legend" x="{lx + 16}" y="{ly}">{label}</text>')
    out.append("</svg>")
    return Markup("".join(out))


def rate_chart(models: list[ModelSummary]) -> Markup:
    """Per model: win rate (ties count half) with its 95% bootstrap CI, overall and
    on the seeded (publicly reproducible) subset."""
    height = ROW_H * len(models) + 66
    x0, w = LABEL_W, BAR_W

    def sx(v: float) -> float:
        return x0 + v * w

    out = [f'<svg class="chart" viewBox="0 0 {LABEL_W + BAR_W + 60} {height}" role="img" '
           f'aria-label="bruhs win rate with 95% confidence interval, per model">']
    axis_y = ROW_H * len(models) + 6
    for t in (0, 0.25, 0.5, 0.75, 1):
        out.append(f'<line class="grid" x1="{sx(t)}" x2="{sx(t)}" y1="4" y2="{axis_y}"/>'
                   f'<text class="tick" x="{sx(t)}" y="{axis_y + 14}" text-anchor="middle">'
                   f"{t * 100:.0f}%</text>")
    out.append(f'<line class="ref" x1="{sx(0.5)}" x2="{sx(0.5)}" y1="4" y2="{axis_y}"/>')
    for i, m in enumerate(models):
        y = i * ROW_H + 14
        out.append(f'<text class="label" x="0" y="{y + 9}">{html.escape(m.model)}</text>')
        for off, rate, cls, name in ((0, m.overall, "s1", "all tasks"),
                                     (14, m.seeded, "s2", "seeded tasks")):
            if rate.win_rate is None:
                continue
            cy = y + off
            if rate.ci:
                out.append(f'<line class="whisker {cls}" x1="{sx(rate.ci[0])}" '
                           f'x2="{sx(rate.ci[1])}" y1="{cy}" y2="{cy}"/>')
            tip = (f"{m.model}, {name}: {pct(rate.win_rate)} win rate, 95% CI "
                   f"{ci_text(rate.ci)}, {rate.n} tasks")
            out.append(f'<g {_tip(tip)}>'
                       f'<circle class="hit" cx="{sx(rate.win_rate)}" cy="{cy}" r="12"/>'
                       f'<circle class="dot {cls}" cx="{sx(rate.win_rate)}" cy="{cy}" r="5"/></g>')
        if m.overall.win_rate is not None:
            out.append(f'<text class="value" x="{x0 + w + 14}" y="{y + 4}">'
                       f"{pct(m.overall.win_rate)}</text>")
    ly = axis_y + 34
    for k, (cls, label) in enumerate((("s1", "all tasks"), ("s2", "seeded tasks only"))):
        lx = LABEL_W + k * 130
        out.append(f'<circle class="dot {cls}" cx="{lx + 5}" cy="{ly - 4}" r="5"/>'
                   f'<text class="legend" x="{lx + 16}" y="{ly}">{label}</text>')
    out.append(f'<text class="legend" x="{LABEL_W}" y="{ly + 18}">Line: 95% CI. '
               "50% = no difference.</text></svg>")
    return Markup("".join(out))


# --------------------------------------------------------------------------- rows


def _scores(o: TaskOutcome) -> tuple[str, str]:
    if o.category in PAIRWISE:
        if not o.prefs:
            return "n/a", "n/a"
        n = len(o.prefs)
        return (f"{o.prefs.count('bare')}/{n} preferred",
                f"{o.prefs.count('bruhs')}/{n} preferred ({o.prefs.count('tie')} tie)")
    mean_ = (lambda xs: num(sum(xs) / len(xs)) if xs else "n/a")
    return mean_(o.bare), mean_(o.bruhs)


def task_rows(summary: Summary, names: Names) -> list[dict]:
    rows = []
    for o in summary.tasks:
        bare, bruhs = _scores(o)
        rows.append({
            "task": names.task(o.task_id), "category": o.category, "cli": o.cli,
            "metric": METRIC_LABEL[o.category], "bare": bare, "bruhs": bruhs,
            "delta": signed(o.delta), "decision": o.decision or "no data",
            "n": len(o.prefs) if o.category in PAIRWISE else len(o.bare),
            "excluded": ", ".join(f"r{r}" for r in o.excluded + o.missing) or "",
            "judge_errors": o.judge_errors, "seeded": o.seeded,
        })
    return rows


def model_rows(summary: Summary) -> list[dict]:
    rows = []
    for m in summary.models.values():
        def r(rate: Rate) -> dict:
            return {"w": rate.wins, "t": rate.ties, "l": rate.losses, "n": rate.n,
                    "rate": pct(rate.win_rate), "ci": ci_text(rate.ci)}
        rows.append({"cli": m.cli, "model": m.model, "all": r(m.overall),
                     "seeded": r(m.seeded), "judge_errors": m.judge_errors})
    return rows


def category_rows(summary: Summary) -> list[dict]:
    rows = []
    for m in summary.models.values():
        for cat in sorted(m.per_category, key=CATEGORY_ORDER.index):
            c = m.per_category[cat]
            rows.append({"model": m.model, "category": cat, "metric": METRIC_LABEL[cat],
                         "tasks": c["tasks"], "w": c["win"], "t": c["tie"], "l": c["loss"],
                         "delta": signed(c["mean_delta"])})
    return rows


def cost_rows(summary: Summary) -> list[dict]:
    rows = []
    for m in summary.models.values():
        for arm in ARMS:
            a = m.arms[arm]
            rows.append({"model": m.model, "arm": arm, "runs": a["runs"],
                         "cost": money(a["cost_usd"]), "wall": num(
                             a["wall_s"] / 60 if a["wall_s"] is not None else None, 1),
                         "turns": num(a["turns"], 1), "tok_in": num(a["input_tokens"], 0),
                         "tok_out": num(a["output_tokens"], 0),
                         "scope_lines": num(a["scope_lines_outside"], 1),
                         "scope_files": num(a["scope_files_outside"], 1)})
    return rows


def _png(path: Path) -> str:
    return "data:image/png;base64," + base64.b64encode(path.read_bytes()).decode()


def examples(summary: Summary, names: Names) -> list[dict]:
    """Side-by-side desktop/light screenshots for a few ui/copy tasks (never for a
    hidden private task)."""
    out = []
    root = summary.results_root
    for o in summary.tasks:
        if len(out) >= MAX_EXAMPLES:
            break
        if o.category not in PAIRWISE or names.hidden(o.task_id) or o.decision is None:
            continue
        repeats = sorted({int(d.name.rsplit("__r", 1)[1]) for d in root.glob(
            f"{o.task_id}__{o.cli}__bruhs__r*")} - set(o.excluded))
        for rep in repeats:
            shots = {}
            for arm in ARMS:
                s = sorted((root / f"{o.task_id}__{o.cli}__{arm}__r{rep}" / "screens")
                           .glob(f"*{EXAMPLE_SHOT}"))
                if s:
                    shots[arm] = _png(s[0])
            before = sorted((root / "_before" / o.task_id).glob(f"*{EXAMPLE_SHOT}"))
            if len(shots) == 2:
                out.append({"task": names.task(o.task_id), "cli": o.cli, "repeat": rep,
                            "decision": o.decision, "before": _png(before[0]) if before else None,
                            **shots})
                break
    return out


def context(summary: Summary, private: bool) -> dict:
    names = Names(summary, private)
    models = list(summary.models.values())
    m = summary.matrix
    return {
        "private": private,
        "date": date.today().isoformat(),
        "matrix": {"bruhs_content": m.get("bruhs_content") or "",
                   "bruhs_commit": (m.get("bruhs_commit")
                                    or ((m.get("starts") or [{}])[0].get("harness_commit"))
                                    or "unknown"),
                   "repeats": m.get("repeats"), "seed": m.get("seed"),
                   "cli_versions": m.get("cli_versions", {}),
                   "models": m.get("models") or [asdict(s) for s in MODELS
                                                  if s.cli in summary.models]},
        "wtl_chart": wtl_chart(models) if models else "",
        "rate_chart": rate_chart(models) if models else "",
        "models": model_rows(summary),
        "categories": category_rows(summary),
        "costs": cost_rows(summary),
        "tasks": task_rows(summary, names),
        "counts": summary.counts,
        "counts_by_cli": summary.counts_by_cli,
        "activation": summary.activation,
        "bare_leaks": {cli: [names.run(r) for r in runs]
                       for cli, runs in summary.bare_leaks.items()},
        "ui_note": UI_SOURCE_NOTE[summary.ui_source].format(agreement=pct(summary.agreement)),
        "examples": examples(summary, names),
        "pct": pct,
    }


def render(summary: Summary, out_dir: Path, *, private: bool) -> tuple[Path, Path]:
    """Write ``report.html`` and ``report.md`` to ``out_dir``; returns their paths."""
    out_dir = Path(out_dir)
    out_dir.mkdir(parents=True, exist_ok=True)
    env = Environment(loader=FileSystemLoader(TEMPLATES),
                      autoescape=select_autoescape(["html", "j2"]),
                      trim_blocks=True, lstrip_blocks=True)
    ctx = context(summary, private)
    html_path, md_path = out_dir / "report.html", out_dir / "report.md"
    html_path.write_text(env.get_template("report.html.j2").render(**ctx))
    md_env = Environment(loader=FileSystemLoader(TEMPLATES), autoescape=False,
                         trim_blocks=True, lstrip_blocks=True)
    md_path.write_text(md_env.get_template("report.md.j2").render(**ctx))
    return html_path, md_path
