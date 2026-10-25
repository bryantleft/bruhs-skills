"""Blind user spot-check of ui/copy pairs, and judge/user agreement.

``select_pairs`` samples up to ``n`` judged (task, model, repeat) units whose two runs
both survive the R23 exclusions, shows each as left/right in a seeded order, and stores
the sample in ``<results_root>/spotcheck.json`` (resumable: an existing sample is kept).
``serve`` runs a local page (127.0.0.1 only) that shows each pair's task prompt, the
starting screenshots and both results' screenshots under neutral labels; a pick is
recorded as left/right/tie plus the arm it resolves to. Nothing on the page (names,
URLs, image paths) reveals the arm.

``agreement`` = share of valid judge verdicts on the picked units that match the user's
pick (each judge verdict compared separately). Below 0.75 the report takes ui/copy from
the user's picks only (``score.summarize``).
"""

from __future__ import annotations

import html
import json
import random
from datetime import datetime, timezone
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path

from .score import load_runs, load_verdicts, parse_run_id, unit_id
from .tasks import load_all_tasks
from .types import Task

STATE = "spotcheck.json"
DEFAULT_N = 20
CHOICES = ("left", "right", "tie")


def _path(root: Path) -> Path:
    return Path(root) / STATE


def _load(root: Path) -> dict:
    p = _path(root)
    return json.loads(p.read_text()) if p.is_file() else {"pairs": [], "picks": {}}


def _save(root: Path, state: dict) -> None:
    p = _path(root)
    tmp = p.with_suffix(".tmp")
    tmp.write_text(json.dumps(state, indent=2) + "\n")
    tmp.replace(p)


def candidate_units(root: Path) -> list[tuple[str, str, int]]:
    """Judged ui/copy units whose two runs are both present and not excluded."""
    verdicts = load_verdicts(root)
    units: dict[tuple[str, str, int], dict] = {}
    for r in load_runs(root):
        units.setdefault((r.task_id, r.cli, r.repeat), {})[r.arm] = r
    return sorted(u for u, arms in units.items()
                  if u in verdicts and set(arms) == {"bare", "bruhs"}
                  and not any(r.exclusion for r in arms.values()))


def select_pairs(root: Path, n: int = DEFAULT_N, seed: int = 0) -> list[dict]:
    """The spot-check sample (created once, then reused)."""
    state = _load(root)
    if state["pairs"]:
        return state["pairs"]
    rng = random.Random(seed)
    units = candidate_units(root)
    chosen = sorted(rng.sample(units, min(n, len(units))), key=lambda _: rng.random())
    pairs = []
    for task_id, cli, repeat in chosen:
        runs = [f"{task_id}__{cli}__{arm}__r{repeat}" for arm in ("bare", "bruhs")]
        rng.shuffle(runs)
        pairs.append({"unit": unit_id(task_id, cli, repeat), "task_id": task_id,
                      "left": runs[0], "right": runs[1]})
    state.update(pairs=pairs, seed=seed)
    _save(root, state)
    return pairs


def record_pick(root: Path, unit: str, choice: str) -> None:
    if choice not in CHOICES:
        raise ValueError(f"choice must be one of {CHOICES}")
    state = _load(root)
    pair = next((p for p in state["pairs"] if p["unit"] == unit), None)
    if pair is None:
        raise KeyError(unit)
    arm = "tie" if choice == "tie" else parse_run_id(pair[choice])[2]
    state["picks"][unit] = {"choice": choice, "arm": arm,
                            "at": datetime.now(timezone.utc).isoformat(timespec="seconds")}
    _save(root, state)


def agreement(root: Path) -> float | None:
    """Share of valid judge verdicts on user-picked units that match the user's pick;
    None before any pick."""
    picks = _load(root).get("picks", {})
    verdicts = load_verdicts(root)
    agree = total = 0
    for unit, pick in picks.items():
        task_id, cli, rep = unit.rsplit("__", 2)
        for v in verdicts.get((task_id, cli, int(rep[1:])), []):
            if v["pref"] is None:
                continue
            total += 1
            agree += v["pref"] == pick["arm"]
    return agree / total if total else None


# --------------------------------------------------------------------------- page


def _shots(root: Path, pair: dict, side: str) -> list[str]:
    d = Path(root) / pair[side] / "screens"
    return sorted(p.name for p in d.glob("*.png")) if d.is_dir() else []


def _before(root: Path, pair: dict) -> list[str]:
    d = Path(root) / "_before" / pair["task_id"]
    return sorted(p.name for p in d.glob("*.png")) if d.is_dir() else []


def render_page(root: Path, tasks: dict[str, Task] | None = None) -> str:
    state = _load(root)
    tasks = tasks if tasks is not None else {t.id: t for t in load_all_tasks()}
    blocks = []
    for i, pair in enumerate(state["pairs"]):
        task = tasks.get(pair["task_id"])
        prompt = html.escape(task.prompt) if task else ""
        picked = state["picks"].get(pair["unit"], {}).get("choice")

        def imgs(kind: str, names: list[str]) -> str:
            return "".join(f'<figure><img loading="lazy" src="/img/{i}/{kind}/{html.escape(n)}">'
                           f"<figcaption>{html.escape(n)}</figcaption></figure>" for n in names)
        buttons = "".join(
            f'<button data-i="{i}" data-choice="{c}"{" class=on" if picked == c else ""}>'
            f"{label}</button>" for c, label in (("left", "Left is better"), ("tie", "Tie"),
                                                ("right", "Right is better")))
        blocks.append(
            f'<section id="p{i}"><h2>Pair {i + 1} of {len(state["pairs"])}</h2>'
            f"<details><summary>Task</summary><pre>{prompt}</pre></details>"
            f"<h3>Before</h3><div class=row>{imgs('before', _before(root, pair))}</div>"
            f"<div class=cols><div><h3>Left</h3>{imgs('left', _shots(root, pair, 'left'))}</div>"
            f"<div><h3>Right</h3>{imgs('right', _shots(root, pair, 'right'))}</div></div>"
            f"<div class=pick>{buttons}</div></section>")
    picks = len(state["picks"])
    return f"""<!doctype html><html><head><meta charset=utf-8><title>Spot-check</title>
<style>
body{{font:14px system-ui,-apple-system,sans-serif;margin:24px;color:#0b0b0b;background:#f9f9f7}}
section{{background:#fcfcfb;border:1px solid rgba(11,11,11,.1);border-radius:8px;padding:16px;margin:0 0 24px}}
.cols{{display:grid;grid-template-columns:1fr 1fr;gap:16px}}
.row{{display:flex;gap:8px;overflow-x:auto}} .row figure{{width:240px;flex:none}}
figure{{margin:0 0 8px}} img{{width:100%;border:1px solid #e1e0d9}} figcaption{{color:#52514e;font-size:12px}}
.pick button{{font:inherit;padding:8px 14px;margin-right:8px;border-radius:6px;border:1px solid #c3c2b7;background:#fff;cursor:pointer}}
.pick button.on{{background:#2a78d6;color:#fff;border-color:#2a78d6}}
pre{{white-space:pre-wrap}}
</style></head><body><h1>Blind spot-check</h1>
<p id=count>{picks} of {len(state["pairs"])} picked. Pick the better result in each pair.</p>
{''.join(blocks) or '<p>No judged ui/copy pairs yet.</p>'}
<script>
const units = {json.dumps([p["unit"] for p in state["pairs"]])};
document.querySelectorAll('.pick button').forEach(b => b.addEventListener('click', async () => {{
  const r = await fetch('/pick', {{method: 'POST', body: JSON.stringify(
    {{unit: units[+b.dataset.i], choice: b.dataset.choice}})}});
  if (!r.ok) return alert('could not save pick');
  b.parentElement.querySelectorAll('button').forEach(x => x.classList.toggle('on', x === b));
  document.getElementById('count').textContent = (await r.json()).picked + ' of ' + units.length + ' picked.';
}}));
</script></body></html>"""


def make_server(root: Path, n: int = DEFAULT_N, seed: int = 0, *, port: int = 8765,
                tasks: dict[str, Task] | None = None) -> ThreadingHTTPServer:
    root = Path(root)
    pairs = select_pairs(root, n, seed)

    class Handler(BaseHTTPRequestHandler):
        def log_message(self, *args):  # quiet
            pass

        def _send(self, code: int, body: bytes, ctype: str) -> None:
            self.send_response(code)
            self.send_header("Content-Type", ctype)
            self.send_header("Content-Length", str(len(body)))
            self.end_headers()
            self.wfile.write(body)

        def do_GET(self):
            if self.path == "/":
                return self._send(200, render_page(root, tasks).encode(), "text/html; charset=utf-8")
            parts = self.path.split("/")
            if len(parts) == 5 and parts[1] == "img" and parts[2].isdigit():
                i, kind, name = int(parts[2]), parts[3], parts[4]
                if i < len(pairs) and kind in ("before", "left", "right"):
                    names = (_before(root, pairs[i]) if kind == "before"
                             else _shots(root, pairs[i], kind))
                    if name in names:  # only listed files: no path traversal
                        d = (root / "_before" / pairs[i]["task_id"] if kind == "before"
                             else root / pairs[i][kind] / "screens")
                        return self._send(200, (d / name).read_bytes(), "image/png")
            self._send(404, b"not found", "text/plain")

        def do_POST(self):
            if self.path != "/pick":
                return self._send(404, b"not found", "text/plain")
            try:
                body = json.loads(self.rfile.read(int(self.headers.get("Content-Length", 0))))
                record_pick(root, str(body["unit"]), str(body["choice"]))
            except (ValueError, KeyError, TypeError) as exc:
                return self._send(400, str(exc).encode(), "text/plain")
            picked = len(_load(root)["picks"])
            self._send(200, json.dumps({"picked": picked}).encode(), "application/json")

    return ThreadingHTTPServer(("127.0.0.1", port), Handler)


def serve(results_root: Path, n: int = DEFAULT_N, seed: int = 0, *, port: int = 8765) -> None:
    """Serve the spot-check page until Ctrl-C; picks are saved as they are made."""
    server = make_server(results_root, n, seed, port=port)
    pairs = _load(results_root)["pairs"]
    print(f"spot-check: {len(pairs)} pairs at http://127.0.0.1:{server.server_address[1]}/ "
          "(Ctrl-C to stop; picks are saved as you go)", flush=True)
    try:
        server.serve_forever()
    except KeyboardInterrupt:
        pass
    finally:
        server.server_close()
    a = agreement(results_root)
    print("judge/user agreement: " + ("n/a (no picks)" if a is None else f"{a:.0%}"))
