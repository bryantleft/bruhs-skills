"""Screenshot a finished ui/copy run so blind judges can compare arms (Ruling R5).

``capture`` starts ``task.dev_cmd`` (``{port}`` -> a free port picked per capture, so captures can run in parallel) in a disposable clone
of the agent's workspace, so build output never alters the workspace, waits for HTTP 200,
and screenshots every page at {desktop 1440x900, mobile 390x844} x {light, dark} as
``<page-slug>__<viewport>__<scheme>.png`` in ``out`` (``<run_dir>/screens``). The dev
server runs in its own process group with a scrubbed env, under the OS sandbox
(``sandbox.wrap``, writes only in its scratch dir), and the whole group is killed
afterwards. Failures never raise: the outcome lands in ``<run_dir>/grades/capture.json``.

``capture_before`` captures the task's base state once into ``<results_root>/_before/<id>``.
"""

from __future__ import annotations

import fcntl
import json
import os
import re
import shutil
import signal
import socket
import subprocess
import tempfile
import time
import urllib.error
import urllib.request
from pathlib import Path

from .graders.commands import clone_tree, sandboxed_env
from .sandbox import wrap
from .types import Task
from .workspace import prepare_workspace

READY_TIMEOUT_S = 180
SETTLE_MS = 500
NAV_TIMEOUT_MS = 60_000
LOG_TAIL = 2000
VIEWPORTS = {"desktop": {"width": 1440, "height": 900}, "mobile": {"width": 390, "height": 844}}
SCHEMES = ("light", "dark")


def page_slug(page: str) -> str:
    slug = re.sub(r"[^A-Za-z0-9]+", "-", page).strip("-")
    return slug or "root"


def _wait_ready(url: str, proc: subprocess.Popen, timeout: float) -> bool:
    deadline = time.monotonic() + timeout
    while time.monotonic() < deadline:
        if proc.poll() is not None:
            return False
        try:
            with urllib.request.urlopen(url, timeout=5) as resp:
                if resp.status == 200:
                    return True
        except (urllib.error.URLError, OSError, ValueError):
            pass
        time.sleep(0.5)
    return False


def _kill_group(proc: subprocess.Popen) -> None:
    for sig in (signal.SIGTERM, signal.SIGKILL):
        try:
            os.killpg(proc.pid, sig)
        except (ProcessLookupError, PermissionError):
            break
        if sig == signal.SIGTERM:
            try:
                proc.wait(timeout=3)
            except subprocess.TimeoutExpired:
                pass
    proc.wait()


def _shoot(base_url: str, pages: tuple[str, ...], out: Path
           ) -> tuple[list[Path], dict[str, str]]:
    """Screenshot every page x variant; a failing page is recorded and skipped."""
    from playwright.sync_api import sync_playwright

    files: list[Path] = []
    page_errors: dict[str, str] = {}
    with sync_playwright() as pw:
        browser = pw.chromium.launch()
        try:
            for vp_name, viewport in VIEWPORTS.items():
                for scheme in SCHEMES:
                    ctx = browser.new_context(viewport=viewport, color_scheme=scheme,
                                              reduced_motion="reduce")
                    try:
                        page = ctx.new_page()
                        for path in pages:
                            dest = out / f"{page_slug(path)}__{vp_name}__{scheme}.png"
                            try:
                                page.goto(base_url + path, wait_until="networkidle",
                                          timeout=NAV_TIMEOUT_MS)
                                page.evaluate("document.fonts.ready.then(() => true)")
                                page.wait_for_timeout(SETTLE_MS)
                                page.screenshot(path=str(dest), full_page=True)
                                files.append(dest)
                            except Exception as exc:
                                dest.unlink(missing_ok=True)
                                page_errors[dest.name] = f"{type(exc).__name__}: {exc}"[:LOG_TAIL]
                    finally:
                        ctx.close()
        finally:
            browser.close()
    return files, page_errors


def _free_port() -> int:
    """A currently free loopback port (so parallel captures never collide)."""
    with socket.socket() as s:
        s.bind(("127.0.0.1", 0))
        return s.getsockname()[1]


def _capture(task: Task, workspace: Path, out: Path, ready_timeout: float
             ) -> tuple[list[Path], str | None, dict[str, str]]:
    out.mkdir(parents=True, exist_ok=True)
    for stale in out.glob("*.png"):
        stale.unlink()
    port = _free_port()
    scratch = Path(tempfile.mkdtemp(prefix="capture-", dir=Path(workspace).parent))
    proc = None
    files: list[Path] = []
    page_errors: dict[str, str] = {}
    error: str | None = None
    try:
        copy = scratch / "ws"
        clone_tree(Path(workspace), copy)
        log = scratch / "dev.log"
        with log.open("wb") as logf:
            # R19: agent-written code; sandboxed, writes only in the scratch dir
            argv = wrap(["bash", "-c", task.dev_cmd.replace("{port}", str(port))],
                        writable=[scratch])
            proc = subprocess.Popen(
                argv, cwd=copy, env=sandboxed_env(scratch), stdin=subprocess.DEVNULL,
                stdout=logf, stderr=subprocess.STDOUT, start_new_session=True)
            base_url = f"http://127.0.0.1:{port}"
            if _wait_ready(base_url + (task.pages[0] if task.pages else "/"), proc,
                           ready_timeout):
                try:
                    files, page_errors = _shoot(base_url, task.pages, out)
                except Exception as exc:  # browser itself failed; keep what exists
                    error = f"screenshot failed: {type(exc).__name__}: {exc}"
                    files = sorted(out.glob("*.png"))
            else:
                state = (f"exited {proc.returncode}" if proc.poll() is not None
                         else f"no HTTP 200 within {ready_timeout}s")
                tail = log.read_text(errors="replace")[-LOG_TAIL:]
                error = f"dev server not ready ({state}): {tail}"
    finally:
        if proc is not None:
            _kill_group(proc)
        shutil.rmtree(scratch, ignore_errors=True)
    return files, error, page_errors


def _record(path: Path, task: Task, files: list[Path], error: str | None,
            page_errors: dict[str, str] | None = None, applicable: bool = True, reason: str | None = None) -> None:
    rec: dict = {"applicable": applicable}
    if applicable:
        rec.update(pages=list(task.pages), files=[f.name for f in files])
        if error:
            rec["error"] = error
        if page_errors:
            rec["page_errors"] = page_errors
    elif reason:
        rec["reason"] = reason
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(rec, indent=2) + "\n")


def capture(task: Task, workspace: Path, out: Path, *, run_dir: Path | None = None,
            ready_timeout: float = READY_TIMEOUT_S) -> list[Path]:
    """Screenshot ``task.pages`` from ``workspace`` into ``out``; [] if it can't be done.

    With ``run_dir`` the outcome is written to ``run_dir/grades/capture.json``.
    """
    return _capture_recorded(task, Path(workspace), Path(out),
                             Path(run_dir) / "grades" / "capture.json" if run_dir else None,
                             ready_timeout)


def _capture_recorded(task: Task, workspace: Path, out: Path, record: Path | None,
                      ready_timeout: float) -> list[Path]:
    if not (task.dev_cmd and task.pages):
        if record:
            _record(record, task, [], None, applicable=False,
                    reason="task has no dev_cmd/pages")
        return []
    files, error, page_errors = _capture(task, workspace, out, ready_timeout)
    if error or page_errors:
        print(f"capture {task.id}: {error or page_errors}", flush=True)
    if record:
        _record(record, task, files, error, page_errors)
    return files


def _complete(dest: Path, task: Task) -> list[Path]:
    """The saved baseline's PNGs if its capture.json says it finished cleanly, else []."""
    try:
        rec = json.loads((dest / "capture.json").read_text())
    except (OSError, ValueError):
        return []
    files = [dest / n for n in rec.get("files", [])]
    if (rec.get("applicable") and not rec.get("error") and not rec.get("page_errors")
            and len(files) == len(task.pages) * len(VIEWPORTS) * len(SCHEMES)
            and all(f.is_file() for f in files)):
        return sorted(files)
    return []


def capture_before(task: Task, results_root: Path, work_root: Path, *,
                   ready_timeout: float = READY_TIMEOUT_S) -> list[Path]:
    """Capture the bare base state into ``<results_root>/_before/<task.id>``.

    Skipped when a complete, error-free capture is already there. A per-task file lock
    serialises concurrent callers, so the second one finds the finished baseline.
    """
    if not (task.dev_cmd and task.pages):
        return []
    before = Path(results_root) / "_before"
    before.mkdir(parents=True, exist_ok=True)
    dest = before / task.id
    with open(before / f"{task.id}.lock", "w") as lock:
        fcntl.flock(lock, fcntl.LOCK_EX)
        done = _complete(dest, task)
        if done:
            return done
        workspace = Path(work_root) / "_before" / task.id / "workspace"
        shutil.rmtree(workspace.parent, ignore_errors=True)
        try:
            prepare_workspace(task, "bare", workspace)
            return _capture_recorded(task, workspace, dest, dest / "capture.json",
                                     ready_timeout)
        finally:
            shutil.rmtree(workspace.parent, ignore_errors=True)
