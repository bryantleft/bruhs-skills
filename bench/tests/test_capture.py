import json
from concurrent.futures import ThreadPoolExecutor
import socket
import os
import sys
from dataclasses import replace
from pathlib import Path

import pytest

from bruhsbench import capture as cap
from bruhsbench.types import Task

HTML = """<!doctype html><title>t</title>
<style>body{background:#fff;color:#000}
@media (prefers-color-scheme: dark){body{background:#000;color:#fff}}</style>
<h1>Hello</h1>"""
# the dev server runs sandboxed, where this venv (in the user's home) is unreadable
PYTHON = os.path.realpath(sys._base_executable)


def free_port() -> int:
    with socket.socket() as s:
        s.bind(("127.0.0.1", 0))
        return s.getsockname()[1]


def port_open(port: int) -> bool:
    with socket.socket() as s:
        s.settimeout(0.5)
        return s.connect_ex(("127.0.0.1", port)) == 0


def make_task(tmp_path: Path, **kw) -> Task:
    d = tmp_path / "task"
    d.mkdir(exist_ok=True)
    port = free_port()
    base = Task(id="t", category="ui", dir=d, repo=None, base=None, prompt="p", setup=None,
                allowed_paths=(), pages=("/", "/grade"), dev_cmd=f"{PYTHON} -m http.server {{port}}",
                dev_port=port, checks={}, hidden_tests=None, known_issues=None,
                checklist=None, heldout=False)
    return replace(base, **kw)


@pytest.fixture
def site(tmp_path):
    ws = tmp_path / "work" / "run" / "workspace"
    ws.mkdir(parents=True)
    (ws / "index.html").write_text(HTML)
    (ws / "grade").mkdir()
    (ws / "grade" / "index.html").write_text(HTML)
    return ws


def test_page_slug():
    assert cap.page_slug("/") == "root"
    assert cap.page_slug("/grade") == "grade"
    assert cap.page_slug("/a/b?x=1") == "a-b-x-1"


def test_capture_produces_four_variants_per_page(tmp_path, site):
    task = make_task(tmp_path)
    run_dir = tmp_path / "results" / "run"
    out = run_dir / "screens"

    files = cap.capture(task, site, out, run_dir=run_dir)

    expected = {f"{p}__{v}__{s}.png" for p in ("root", "grade")
                for v in ("desktop", "mobile") for s in ("light", "dark")}
    assert {f.name for f in files} == expected
    assert all(f.parent == out and f.stat().st_size > 0 for f in files)
    rec = json.loads((run_dir / "grades" / "capture.json").read_text())
    assert rec["applicable"] is True and rec["pages"] == ["/", "/grade"]
    assert sorted(rec["files"]) == sorted(expected) and "error" not in rec
    # the dev server ran in a clone: the agent workspace is untouched
    assert not list(site.parent.glob("capture-*"))
    # schemes and viewports really differ
    by = {f.name: f.read_bytes() for f in files}
    assert by["root__desktop__light.png"] != by["root__desktop__dark.png"]
    assert by["root__mobile__light.png"] != by["root__desktop__light.png"]


def test_parallel_captures_of_same_task_serve_their_own_workspace(tmp_path):
    task = make_task(tmp_path, pages=("/",))
    sites = []
    for name, bg in (("a", "#f00"), ("b", "#00f")):
        ws = tmp_path / "work" / name / "workspace"
        ws.mkdir(parents=True)
        (ws / "index.html").write_text(f"<!doctype html><body style='background:{bg}'>")
        sites.append(ws)
    with ThreadPoolExecutor(2) as ex:
        a, b = ex.map(lambda ws: cap.capture(task, ws, tmp_path / "out" / ws.parent.name),
                      sites)
    assert len(a) == len(b) == 4
    da = {f.name: f.read_bytes() for f in a}
    db = {f.name: f.read_bytes() for f in b}
    assert all(da[n] != db[n] for n in da)


def test_one_failing_page_does_not_abort_the_rest(tmp_path, site, monkeypatch):
    monkeypatch.setattr(cap, "NAV_TIMEOUT_MS", 3000)
    task = make_task(tmp_path, pages=("/", "/slow", "/grade"))
    (site / "serve.py").write_text(
        "import http.server, sys, time\n"
        "class H(http.server.SimpleHTTPRequestHandler):\n"
        "    def do_GET(self):\n"
        "        if self.path == '/slow':\n"
        "            time.sleep(30)\n"
        "        super().do_GET()\n"
        "http.server.ThreadingHTTPServer(('127.0.0.1', int(sys.argv[1])), H).serve_forever()\n")
    task = replace(task, dev_cmd=f"{PYTHON} serve.py {{port}}")
    run_dir = tmp_path / "results" / "run"

    files = cap.capture(task, site, run_dir / "screens", run_dir=run_dir)

    names = {f.name for f in files}
    assert len(names) == 8 and not any(n.startswith("slow") for n in names)
    rec = json.loads((run_dir / "grades" / "capture.json").read_text())
    assert len(rec["page_errors"]) == 4
    assert all(n.startswith("slow__") for n in rec["page_errors"])


def test_dev_server_killed_after_capture(tmp_path, site):
    task = make_task(tmp_path, pages=("/",))
    assert cap.capture(task, site, tmp_path / "s")
    assert not port_open(task.dev_port)


def test_server_never_ready_returns_empty_and_logs(tmp_path, site):
    task = make_task(tmp_path, dev_cmd="sleep 60")
    run_dir = tmp_path / "results" / "run"

    files = cap.capture(task, site, run_dir / "screens", run_dir=run_dir, ready_timeout=1)

    assert files == []
    rec = json.loads((run_dir / "grades" / "capture.json").read_text())
    assert rec["applicable"] is True and rec["files"] == []
    assert "not ready" in rec["error"]


def test_server_exiting_early_fails_fast(tmp_path, site):
    task = make_task(tmp_path, dev_cmd="exit 3")
    assert cap.capture(task, site, tmp_path / "s", ready_timeout=60) == []


def test_not_applicable_without_dev_cmd(tmp_path, site):
    task = make_task(tmp_path, dev_cmd=None, dev_port=None, pages=())
    run_dir = tmp_path / "results" / "run"
    assert cap.capture(task, site, run_dir / "screens", run_dir=run_dir) == []
    assert json.loads((run_dir / "grades" / "capture.json").read_text())["applicable"] is False


def test_dev_server_env_is_scrubbed(tmp_path, site, monkeypatch):
    monkeypatch.setenv("ANTHROPIC_API_KEY", "sekrit")
    envfile = tmp_path / "env.txt"
    task = make_task(tmp_path, pages=("/",), dev_cmd=(
        f"env > {envfile}; {PYTHON} -m http.server {{port}}"))
    assert cap.capture(task, site, tmp_path / "s")
    env = dict(l.split("=", 1) for l in envfile.read_text().splitlines() if "=" in l)
    assert "ANTHROPIC_API_KEY" not in env and "sekrit" not in envfile.read_text()
    assert env.get("PATH")


def test_capture_before_once(tmp_path, monkeypatch):
    fixture = tmp_path / "task" / "fixture"
    fixture.mkdir(parents=True)
    (fixture / "index.html").write_text(HTML)
    task = make_task(tmp_path, pages=("/",))
    results, work = tmp_path / "results", tmp_path / "work"

    first = cap.capture_before(task, results, work)

    assert {f.name for f in first} == {f"root__{v}__{s}.png" for v in ("desktop", "mobile")
                                       for s in ("light", "dark")}
    assert all(f.parent == results / "_before" / "t" for f in first)

    def boom(*a, **k):
        raise AssertionError("must not recapture")
    monkeypatch.setattr(cap, "_capture", boom)
    assert sorted(cap.capture_before(task, results, work)) == sorted(first)


def test_capture_before_recaptures_partial_baseline(tmp_path):
    fixture = tmp_path / "task" / "fixture"
    fixture.mkdir(parents=True)
    (fixture / "index.html").write_text(HTML)
    task = make_task(tmp_path, pages=("/",))
    results, work = tmp_path / "results", tmp_path / "work"
    dest = results / "_before" / "t"
    dest.mkdir(parents=True)
    (dest / "root__desktop__light.png").write_bytes(b"stale")
    (dest / "capture.json").write_text(json.dumps(
        {"applicable": True, "pages": ["/"], "files": ["root__desktop__light.png"],
         "error": "boom"}))

    files = cap.capture_before(task, results, work)

    assert len(files) == 4 and all(f.read_bytes() != b"stale" for f in files)


def test_concurrent_capture_before_captures_once(tmp_path, monkeypatch):
    fixture = tmp_path / "task" / "fixture"
    fixture.mkdir(parents=True)
    (fixture / "index.html").write_text(HTML)
    task = make_task(tmp_path, pages=("/",))
    results, work = tmp_path / "results", tmp_path / "work"
    calls = []
    real = cap._capture
    monkeypatch.setattr(cap, "_capture", lambda *a, **k: calls.append(1) or real(*a, **k))

    with ThreadPoolExecutor(2) as ex:
        a, b = ex.map(lambda _: cap.capture_before(task, results, work), range(2))

    assert len(calls) == 1 and len(a) == len(b) == 4
