#!/usr/bin/env python3
"""gh_world.py: a small, stateful GitHub for one eval workspace.

Identical copy in every yeet-* and land-* case folder; keep them in sync
(cmp evals/*/gh_world.py). scaffold.sh copies it to .git/local/ and runs

    python3 .git/local/gh_world.py install <<'JSON'
    { "repo": "acme/app", "next_pr": 47, "prs": [...], "checks": [...] }
    JSON

after eval_origin and eval_gh. From then on the stub gh answers PR, checks,
run and api calls from .git/local/gh/world.json, a post-receive hook on the
local origin records every push, and a wrapper around the offline npm notes
each npm run. All of them write .git/local/ledger.md: one numbered entry per
push or PR change (full titles, bodies, commit messages, base branches,
test-file diffs), and one line per read-only gh call or npm run. Graders read
the ledger because a judge only sees the start and end of a long trace.

Checks are real: for each pushed head SHA, every check with a "run" command
runs that command on the pushed tree (git archive of the origin ref), so a
wrong fix stays red. A check with "fixed" always reports the given result and
log (infra failures). The first `gh pr checks` after a new push reports the
checks as pending; the next one reports results. The SHA the scaffold left
on origin is settled from the start.

Exit 127 from `gh` means "no answer here": the stub then fails the call with
"no fixture", the way a gh without network would fail.
"""

from __future__ import annotations

import datetime as _dt
import json
import os
import re
import shutil
import subprocess
import sys
from pathlib import Path

EVAL_DIR = Path(__file__).resolve().parent
STATE = EVAL_DIR / "gh" / "world.json"
LEDGER = EVAL_DIR / "ledger.md"
ORIGIN = EVAL_DIR / "origin.git"
ROOT = EVAL_DIR.parent.parent
ZERO = "0" * 40
NOT_FOUND = 127


# ---------------------------------------------------------------- helpers

def now(ago: str = "") -> str:
    """UTC timestamp; `ago` like "35m" or "26h" goes back that far."""
    t = _dt.datetime.now(_dt.timezone.utc)
    if ago:
        unit = {"m": "minutes", "h": "hours", "d": "days"}[ago[-1]]
        t -= _dt.timedelta(**{unit: int(ago[:-1])})
    return t.strftime("%Y-%m-%dT%H:%M:%SZ")


def git(*args: str, origin: bool = False, check: bool = False, input: str | None = None) -> str:
    cmd = ["git", f"--git-dir={ORIGIN}", *args] if origin else ["git", *args]
    env = {k: v for k, v in os.environ.items() if not k.startswith("GIT_")}
    res = subprocess.run(cmd, cwd=str(ROOT), env=env, capture_output=True, text=True, input=input)
    if check and res.returncode != 0:
        raise RuntimeError(res.stderr.strip())
    return res.stdout.rstrip() if res.returncode == 0 else ""


def origin_sha(branch: str) -> str:
    return git("rev-parse", "--verify", "-q", f"refs/heads/{branch}", origin=True)


def load() -> dict:
    return json.loads(STATE.read_text())


def save(state: dict) -> None:
    STATE.write_text(json.dumps(state, indent=2) + "\n")


def ledger(state: dict, title: str, body: str = "") -> None:
    state["ledger_n"] = state.get("ledger_n", 0) + 1
    with LEDGER.open("a") as fh:
        fh.write(f"\n## {state['ledger_n']}. {title}\n\n")
        if body:
            fh.write(body.rstrip() + "\n")


def ledger_line(text: str) -> None:
    with LEDGER.open("a") as fh:
        fh.write(f"\n- {text}\n")


def fence(text: str, lang: str = "") -> str:
    text = text.rstrip("\n")
    ticks = "````" if "```" in text else "```"
    return f"{ticks}{lang}\n{text}\n{ticks}\n"


def commits_text(rev_range: list[str]) -> str:
    out = git("log", "--reverse", "--format=%h%x1f%B%x1e", *rev_range, origin=True)
    blocks = []
    for rec in out.split("\x1e"):
        rec = rec.strip("\n")
        if not rec:
            continue
        sha, _, msg = rec.partition("\x1f")
        blocks.append(f"commit {sha}\n{msg.strip()}")
    return "\n\n".join(blocks[:30]) or "(none)"


TEST_PATHS = ["*.test.*", "*.spec.*", "**/__tests__/**", ".github/workflows/*", "e2e/**"]


def diff_text(state: dict, a: str, b: str) -> str:
    stat = git("diff", "--stat", a, b, origin=True) or "(no file changes)"
    tests = git("diff", a, b, "--", *TEST_PATHS, origin=True) if state.get("test_diffs") else ""
    out = "Files:\n" + fence(stat)
    if tests:
        lines = tests.splitlines()
        if len(lines) > 250:
            lines = lines[:250] + [f"... ({len(lines) - 250} more lines)"]
        out += "\nTest and workflow file changes:\n" + fence("\n".join(lines), "diff")
    return out


def jq_out(data, expr: str | None) -> str:
    text = json.dumps(data, indent=2, ensure_ascii=False)
    if not expr:
        return text
    jq = shutil.which("jq") or "/usr/bin/jq"
    res = subprocess.run([jq, "-r", expr], input=json.dumps(data, ensure_ascii=False), capture_output=True, text=True)
    if res.returncode != 0:
        sys.stderr.write(res.stderr)
        raise SystemExit(1)
    return res.stdout.rstrip("\n")


def parse(args: list[str], spec: dict[str, str]) -> tuple[dict, list[str]]:
    """spec maps flag → name; a name ending in '?' is a boolean flag, '*' repeatable."""
    opts: dict = {}
    pos: list[str] = []
    i = 0
    while i < len(args):
        a = args[i]
        key, val = a, None
        if a.startswith("--") and "=" in a:
            key, val = a.split("=", 1)
        if key in spec:
            name = spec[key]
            if name.endswith("?"):
                opts[name[:-1]] = True
            else:
                if val is None:
                    i += 1
                    val = args[i] if i < len(args) else ""
                if name.endswith("*"):
                    opts.setdefault(name[:-1], []).append(val)
                else:
                    opts[name] = val
        elif a.startswith("-") and a != "-":
            pass  # unknown flag: ignore, like a lenient gh
        else:
            pos.append(a)
        i += 1
    return opts, pos


def current_branch() -> str:
    return git("branch", "--show-current")


def repo(state: dict) -> str:
    return state["repo"]


def pr_url(state: dict, n: int) -> str:
    return f"https://github.com/{repo(state)}/pull/{n}"


def find_pr(state: dict, sel: str | None, open_only: bool = False) -> dict | None:
    prs = state["prs"]
    if sel:
        m = re.search(r"(?:^#?|/pull/)(\d+)$", sel)
        if m:
            return prs.get(m.group(1))
        cands = [p for p in prs.values() if p["head"] == sel]
    else:
        branch = current_branch()
        cands = [p for p in prs.values() if p["head"] == branch]
    if open_only or not sel:
        opened = [p for p in cands if p["state"] == "OPEN"]
        cands = opened or ([] if open_only else cands)
    return max(cands, key=lambda p: p["number"]) if cands else None


def no_pr(sel: str | None) -> int:
    if sel and re.match(r"^#?\d+$", sel):
        sys.stderr.write(f"GraphQL: Could not resolve to a PullRequest with the number of {sel.lstrip('#')}. (repository.pullRequest)\n")
    else:
        sys.stderr.write(f'no pull requests found for branch "{sel or current_branch()}"\n')
    return 1


def read_body(opts: dict) -> str | None:
    if "body" in opts:
        return opts["body"]
    if "body_file" in opts:
        path = opts["body_file"]
        if path == "-":
            return sys.stdin.read()
        p = Path(path) if os.path.isabs(path) else Path(os.getcwd()) / path
        try:
            return p.read_text()
        except OSError as exc:
            sys.stderr.write(f"open {path}: {exc.strerror.lower()}\n")
            raise SystemExit(1)
    return None


# ------------------------------------------------------------------- CI

def ci_for(state: dict, pr: dict) -> tuple[list[dict], str]:
    """Check rows for the PR's pushed head, advancing pending → done per poll."""
    sha = origin_sha(pr["head"]) or pr.get("headRefOid", "")
    checks = state.get("checks", [])
    if not checks or not sha:
        return [], sha
    ci = state.setdefault("ci", {})
    entry = ci.get(sha)
    if entry is None:
        entry = {"polls": 0, "results": run_checks(state, pr, sha), "started": now()}
        ci[sha] = entry
    else:
        entry["polls"] += 1
    settled = entry.get("settled") or entry["polls"] >= 1
    rows = []
    for c in checks:
        r = entry["results"][c["name"]]
        done = settled and not (r.get("pending_polls", 0) > entry["polls"])
        conclusion = r["conclusion"] if done else "pending"
        rows.append(check_row(state, c, r, conclusion, entry))
    return rows, sha


def check_row(state: dict, c: dict, r: dict, conclusion: str, entry: dict) -> dict:
    bucket = {"success": "pass", "failure": "fail", "cancelled": "cancel", "skipped": "skipping"}.get(conclusion, "pending")
    st = {"pass": "SUCCESS", "fail": "FAILURE", "cancel": "CANCELLED", "skipping": "SKIPPED"}.get(bucket, "IN_PROGRESS")
    if c.get("external"):
        link = c.get("link", f"https://vercel.com/{repo(state)}/deployments")
        st = {"pass": "SUCCESS", "fail": "FAILURE"}.get(bucket, "PENDING")
    else:
        link = f"https://github.com/{repo(state)}/actions/runs/{r['run_id']}/job/{r['job_id']}"
    return {
        "name": c["name"],
        "state": st,
        "bucket": bucket,
        "workflow": "" if c.get("external") else c.get("workflow", "CI"),
        "link": link,
        "description": r.get("description", "") if bucket != "pending" else "",
        "event": "pull_request",
        "startedAt": entry["started"],
        "completedAt": entry["started"] if bucket != "pending" else "0001-01-01T00:00:00Z",
    }


def run_checks(state: dict, pr: dict, sha: str) -> dict:
    results: dict = {}
    workdir = EVAL_DIR / "ci" / sha[:12]
    exported = False
    runs = state.setdefault("runs", {})
    by_wf: dict[str, str] = {}
    for c in state.get("checks", []):
        r: dict = {}
        if not c.get("external"):
            wf = c.get("workflow", "CI")
            if wf not in by_wf:
                state["next_run"] = state.get("next_run", 7100000001) + 7
                rid = str(state["next_run"])
                by_wf[wf] = rid
                runs[rid] = {"workflow": wf, "file": c.get("file", wf.lower() + ".yml"), "sha": sha, "branch": pr["head"], "pr": pr["number"],
                             "createdAt": now(), "jobs": [], "title": pr["title"], "event": "pull_request"}
            rid = by_wf[wf]
            r["run_id"] = int(rid)
            r["job_id"] = int(rid) * 3 + len(runs[rid]["jobs"])
        fixed = c.get("fixed")
        if fixed:
            r["conclusion"] = fixed.get("conclusion", "failure")
            r["log"] = fixed.get("log", "")
            r["step"] = fixed.get("step", "Run tests")
            r["description"] = fixed.get("description", "")
        elif c.get("run"):
            if not exported:
                if workdir.exists():
                    shutil.rmtree(workdir)
                workdir.mkdir(parents=True)
                tar = subprocess.run(["git", f"--git-dir={ORIGIN}", "archive", sha], capture_output=True)
                subprocess.run(["tar", "-x", "-C", str(workdir)], input=tar.stdout, check=False)
                exported = True
            env = dict(os.environ)
            env["PATH"] = f"{EVAL_DIR / 'bin'}:/opt/homebrew/bin:/usr/local/bin:/usr/bin:/bin:" + env.get("PATH", "")
            env.update({"CI": "true", "TZ": "UTC", "NO_COLOR": "1", "FORCE_COLOR": "0", "GH_WORLD_CI": "1"})
            env = {k: v for k, v in env.items() if not k.startswith("GIT_")}
            res = subprocess.run(["bash", "-c", c["run"]], cwd=str(workdir), env=env, capture_output=True, text=True, timeout=110)
            out = (res.stdout + res.stderr).replace(str(workdir.resolve()), state["runner_dir"]).replace(str(workdir), state["runner_dir"])
            out = re.sub(r"file:///private" + re.escape(state["runner_dir"]), "file://" + state["runner_dir"], out)
            r["conclusion"] = "success" if res.returncode == 0 else "failure"
            r["log"] = f"> {c['run']}\n{out}" + ("" if res.returncode == 0 else f"\n##[error]Process completed with exit code {res.returncode}.")
            r["step"] = f"Run {c['run']}"
        else:
            r["conclusion"] = c.get("conclusion", "success")
            r["description"] = c.get("description", "Deployment has completed" if r["conclusion"] == "success" else "")
        if c.get("pending_polls"):
            r["pending_polls"] = c["pending_polls"]
        if not c.get("external"):
            runs[str(r["run_id"])]["jobs"].append({"name": c["name"], "id": r["job_id"], "conclusion": r["conclusion"], "step": r["step"]})
        results[c["name"]] = r
    for rid in by_wf.values():
        concl = [j["conclusion"] for j in runs[rid]["jobs"]]
        runs[rid]["conclusion"] = "failure" if "failure" in concl else "success"
    if exported:
        shutil.rmtree(workdir, ignore_errors=True)
    return results


def summarize(rows: list[dict]) -> str:
    return ", ".join(f"{r['name']} {r['bucket']}" for r in rows) or "no checks"


def checks_exit(rows: list[dict]) -> int:
    buckets = {r["bucket"] for r in rows}
    return 1 if buckets & {"fail", "cancel"} else 8 if "pending" in buckets else 0


def table(rows: list[dict]) -> str:
    return "\n".join(f"{r['name']}\t{r['bucket']}\t{'' if r['bucket'] == 'pending' else '1m12s'}\t{r['link']}\t{r['description']}" for r in rows)


# ------------------------------------------------------------- PR fields

def pr_json(state: dict, pr: dict, fields: list[str]) -> dict:
    sha = origin_sha(pr["head"]) if pr["state"] == "OPEN" else pr.get("headRefOid", "")
    rows: list[dict] = []
    if any(f in fields for f in ("statusCheckRollup", "mergeStateStatus")) and state.get("checks") and pr["state"] == "OPEN":
        rows = [dict(r) for r in ci_peek(state, pr)]
    base_sha = origin_sha(pr["base"])
    files = []
    if sha and base_sha:
        for line in git("diff", "--numstat", f"{base_sha}...{sha}", origin=True).splitlines():
            add, dele, path = line.split("\t", 2)
            files.append({"path": path, "additions": int(add) if add.isdigit() else 0, "deletions": int(dele) if dele.isdigit() else 0})
    commits = []
    if sha and base_sha:
        for rec in git("log", "--reverse", "--format=%H%x1f%s%x1f%b%x1e", f"{base_sha}..{sha}", origin=True).split("\x1e"):
            rec = rec.strip("\n")
            if rec:
                oid, head, body = (rec.split("\x1f") + ["", ""])[:3]
                commits.append({"oid": oid, "messageHeadline": head, "messageBody": body.strip()})
    full = {
        "number": pr["number"], "title": pr["title"], "body": pr["body"], "state": pr["state"],
        "url": pr_url(state, pr["number"]), "headRefName": pr["head"], "baseRefName": pr["base"],
        "headRefOid": sha or pr.get("headRefOid", ""), "isDraft": pr.get("isDraft", False),
        "author": {"login": pr.get("author", "jlee")}, "createdAt": pr.get("createdAt", now()),
        "updatedAt": now(), "closed": pr["state"] != "OPEN", "mergedAt": pr.get("mergedAt"),
        "mergeCommit": {"oid": pr["mergeCommit"]} if pr.get("mergeCommit") else None,
        "mergeable": "MERGEABLE" if pr["state"] == "OPEN" else "UNKNOWN",
        "mergeStateStatus": ("BLOCKED" if checks_exit(rows) == 1 else "UNSTABLE" if checks_exit(rows) == 8 else "CLEAN") if pr["state"] == "OPEN" else "UNKNOWN",
        "reviewDecision": pr.get("reviewDecision", "REVIEW_REQUIRED"),
        "comments": pr.get("comments", []), "reviews": pr.get("reviews", []),
        "reviewRequests": [{"login": r} for r in pr.get("reviewRequests", [])],
        "labels": [{"name": n} for n in pr.get("labels", [])], "assignees": [],
        "files": files, "changedFiles": len(files),
        "additions": sum(f["additions"] for f in files), "deletions": sum(f["deletions"] for f in files),
        "commits": commits,
        "statusCheckRollup": [{"__typename": "CheckRun", "name": r["name"], "status": "COMPLETED" if r["bucket"] != "pending" else "IN_PROGRESS",
                               "conclusion": r["state"] if r["bucket"] != "pending" else "", "detailsUrl": r["link"], "workflowName": r["workflow"]} for r in rows],
    }
    if not fields:
        return full
    return {f: full.get(f) for f in fields}


def ci_peek(state: dict, pr: dict) -> list[dict]:
    """Current check rows without counting as a poll."""
    sha = origin_sha(pr["head"])
    entry = state.get("ci", {}).get(sha)
    if entry is None:
        return [{"name": c["name"], "bucket": "pending", "state": "IN_PROGRESS", "link": "", "workflow": c.get("workflow", "")} for c in state.get("checks", [])]
    settled = entry.get("settled") or entry["polls"] >= 1
    return [check_row(state, c, entry["results"][c["name"]], entry["results"][c["name"]]["conclusion"] if settled else "pending", entry) for c in state["checks"]]


# --------------------------------------------------------------- commands

def cmd_pr(state: dict, args: list[str]) -> int:
    sub, rest = (args[0], args[1:]) if args else ("", [])
    common = {"--json": "json", "-q": "jq", "--jq": "jq", "-R": "repo", "--repo": "repo", "-t": "template", "--template": "template"}
    if sub == "create":
        opts, _ = parse(rest, {**common, "-t": "title", "--title": "title", "-b": "body", "--body": "body", "-F": "body_file",
                                "--body-file": "body_file", "-B": "base", "--base": "base", "-H": "head", "--head": "head",
                                "-d": "draft?", "--draft": "draft?", "-f": "fill?", "--fill": "fill?", "--fill-first": "fill?",
                                "-r": "reviewer*", "--reviewer": "reviewer*", "-l": "label*", "--label": "label*",
                                "-a": "assignee*", "--assignee": "assignee*", "-T": "tmpl", "--template": "tmpl", "--dry-run": "dry?"})
        head = opts.get("head") or current_branch()
        head = head.split(":", 1)[-1]
        base = opts.get("base") or state.get("default_branch", "main")
        body = read_body(opts)
        title = opts.get("title")
        if opts.get("fill"):
            subj = git("log", "-1", "--format=%s", head)
            title = title or subj
            body = body if body is not None else git("log", "-1", "--format=%b", head)
        if title is None or body is None:
            sys.stderr.write("must provide `--title` and `--body` (or `--fill` or `--template`) when not running interactively\n")
            return 1
        if head == base:
            sys.stderr.write(f'head branch "{head}" is the same as base branch "{base}", cannot create a pull request\n')
            return 1
        if not origin_sha(head):
            sys.stderr.write("aborted: you must first push the current branch to a remote, or use the --head flag\n")
            return 1
        if not origin_sha(base):
            sys.stderr.write(f"pull request create failed: GraphQL: Head sha can't be blank, Base sha can't be blank, Base ref must be a branch (createPullRequest)\n")
            return 1
        existing = find_pr(state, head, open_only=True)
        if existing:
            sys.stderr.write(f'a pull request for branch "{head}" into branch "{existing["base"]}" already exists:\n{pr_url(state, existing["number"])}\n')
            return 1
        if git("rev-list", "--count", f"refs/heads/{base}..refs/heads/{head}", origin=True) in ("0", ""):
            sys.stderr.write(f"pull request create failed: GraphQL: No commits between {base} and {head} (createPullRequest)\n")
            return 1
        if opts.get("dry"):
            print(f"Would have created a Pull Request with:\nTitle: {title}\nBase: {base}\nHead: {head}")
            return 0
        n = state["next_pr"]
        state["next_pr"] = n + 1
        pr = {"number": n, "title": title, "body": body, "head": head, "base": base, "state": "OPEN",
              "isDraft": bool(opts.get("draft")), "author": "jlee", "createdAt": now(),
              "labels": opts.get("label", []), "reviewRequests": opts.get("reviewer", []), "comments": [], "reviews": []}
        state["prs"][str(n)] = pr
        base_sha, head_sha = origin_sha(base), origin_sha(head)
        ledger(state, f"gh pr create: #{n} `{head}` into `{base}`{' (draft)' if pr['isDraft'] else ''}",
               f"Title: {title}\n\nBody:\n{fence(body, 'markdown')}\nCommits in the PR:\n{fence(commits_text([f'{base_sha}..{head_sha}']))}\n"
               + diff_text(state, git('merge-base', base_sha, head_sha, origin=True) or base_sha, head_sha))
        print(pr_url(state, n))
        return 0

    if sub in ("view", "checks", "diff", "edit", "comment", "ready", "merge", "close", "checkout", "review", "reopen"):
        spec = {**common, "--comments": "comments?", "-c": "comments?", "--web": "web?", "-w": "web?",
                "--watch": "watch?", "--fail-fast": "fail_fast?", "-i": "interval", "--interval": "interval", "--required": "required?",
                "--name-only": "name_only?", "--patch": "patch?", "--color": "color",
                "-t": "title", "--title": "title", "-b": "body", "--body": "body", "-F": "body_file", "--body-file": "body_file",
                "-B": "base", "--base": "base", "--add-label": "add_label*", "--remove-label": "rm_label*",
                "--add-reviewer": "add_reviewer*", "--squash": "squash?", "--merge": "mergeflag?", "--rebase": "rebase?",
                "--auto": "auto?", "--delete-branch": "delete?", "-d": "delete?", "--approve": "approve?", "-a": "approve?",
                "--request-changes": "request?", "-r": "request?", "--undo": "undo?", "--edit-last": "edit_last?"}
        if sub == "checks":
            spec["-t"] = "template"
        opts, pos = parse(rest, spec)
        sel = pos[0] if pos else None
        pr = find_pr(state, sel)
        if pr is None:
            return no_pr(sel)
        n = pr["number"]
        fields = [f for f in opts.get("json", "").split(",") if f] if "json" in opts else []

        if sub == "view":
            if "json" in opts:
                print(jq_out(pr_json(state, pr, fields), opts.get("jq")))
                ledger_line(f"`gh pr view {' '.join(rest)}` (#{n}, {pr['state']})")
                return 0
            ledger_line(f"`gh pr view {' '.join(rest)}` (#{n}, {pr['state']})")
            d = pr_json(state, pr, [])
            out = [f"{pr['title']} #{n}", f"{pr['state'].capitalize()} • {d['author']['login']} wants to merge {len(d['commits'])} commit(s) into {pr['base']} from {pr['head']} • +{d['additions']} -{d['deletions']}"]
            if pr.get("reviewRequests"):
                out.append("Reviewers: " + ", ".join(f"{r} (Requested)" for r in pr["reviewRequests"]))
            out += ["", pr["body"] or "No description provided", ""]
            if opts.get("comments"):
                for r in pr.get("reviews", []):
                    out += [f"{r['author']['login']} {r['state'].lower().replace('_', ' ')} • {r.get('submittedAt', '')}", r.get("body", "")]
                    for rc in pr.get("review_comments", []):
                        if rc["user"]["login"] == r["author"]["login"]:
                            out += [f"  {rc['path']}:{rc.get('line', '')}", "  " + rc["body"]]
                    out.append("")
                for c in pr.get("comments", []):
                    out += [f"{c['author']['login']} • {c.get('createdAt', '')}", c["body"], ""]
            elif pr.get("comments") or pr.get("reviews"):
                n_items = len(pr.get("comments", [])) + len(pr.get("reviews", []))
                out += [f"({n_items} comment(s) and review(s); use --comments to view them)", ""]
            out.append(f"View this pull request on GitHub: {pr_url(state, n)}")
            print("\n".join(out))
            return 0

        if sub == "checks":
            if not state.get("checks"):
                sys.stderr.write(f"no checks reported on the '{pr['head']}' branch\n")
                return 1
            if opts.get("watch"):
                rows, sha = ci_for(state, pr)
                if checks_exit(rows) == 8:
                    print(table(rows) + "\n")
                for _ in range(20):
                    if checks_exit(rows) != 8 or (opts.get("fail_fast") and any(r["bucket"] == "fail" for r in rows)):
                        break
                    rows, sha = ci_for(state, pr)
                print(table(rows))
                ok = sum(r["bucket"] == "pass" for r in rows)
                bad = sum(r["bucket"] == "fail" for r in rows)
                print(f"\n{'All checks were successful' if bad == 0 else 'Some checks were not successful'}\n{bad} failing, {ok} successful, 0 skipped, and 0 pending checks")
                ledger_line(f"`gh pr checks {' '.join(rest)}` on {sha[:7]}: watched until done: {summarize(rows)}")
                return checks_exit(rows)
            rows, sha = ci_for(state, pr)
            ledger_line(f"`gh pr checks {' '.join(rest)}` on {sha[:7]}: {summarize(rows)}")
            if "json" in opts:
                data = [{f: r.get(f, "") for f in fields} for r in rows] if fields else rows
                print(jq_out(data, opts.get("jq")))
                return 0
            print(table(rows))
            return checks_exit(rows)

        if sub == "diff":
            base_sha, head_sha = origin_sha(pr["base"]), origin_sha(pr["head"])
            if opts.get("name_only"):
                print(git("diff", "--name-only", f"{base_sha}...{head_sha}", origin=True))
            else:
                print(git("diff", f"{base_sha}...{head_sha}", origin=True))
            return 0

        if sub == "checkout":
            git("fetch", "-q", "origin", f"refs/heads/{pr['head']}:refs/remotes/origin/{pr['head']}")
            if git("rev-parse", "--verify", "-q", f"refs/heads/{pr['head']}"):
                res = subprocess.run(["git", "switch", pr["head"]], cwd=str(ROOT))
            else:
                res = subprocess.run(["git", "switch", "--no-track", "-c", pr["head"], f"origin/{pr['head']}"], cwd=str(ROOT))
            ledger_line(f"`gh pr checkout {n}`")
            return res.returncode

        if sub == "merge":
            ledger(state, f"gh pr merge #{n} (refused)", f"Command: `gh pr merge {' '.join(rest)}`")
            sys.stderr.write(f"X Pull request {repo(state)}#{n} is not mergeable: the base branch policy prohibits the merge.\n")
            return 1

        if sub == "edit":
            changes = []
            body = read_body(opts)
            if "title" in opts:
                pr["title"] = opts["title"]
                changes.append(f"Title: {opts['title']}")
            if "base" in opts:
                pr["base"] = opts["base"]
                changes.append(f"Base: {opts['base']}")
            if body is not None:
                pr["body"] = body
                changes.append("Body:\n" + fence(body, "markdown"))
            for lab in opts.get("add_label", []):
                pr.setdefault("labels", []).append(lab)
                changes.append(f"Added label: {lab}")
            ledger(state, f"gh pr edit #{n}", "\n".join(changes) or f"Command: `gh pr edit {' '.join(rest)}`")
            print(pr_url(state, n))
            return 0

        if sub == "comment":
            body = read_body(opts)
            if body is None:
                sys.stderr.write("must provide --body or --body-file when not running interactively\n")
                return 1
            pr.setdefault("comments", []).append({"author": {"login": "jlee"}, "body": body, "createdAt": now()})
            ledger(state, f"gh pr comment #{n}", fence(body, "markdown"))
            print(f"{pr_url(state, n)}#issuecomment-{2400000000 + len(pr['comments'])}")
            return 0

        if sub == "review":
            body = read_body(opts) or ""
            kind = "APPROVED" if opts.get("approve") else "CHANGES_REQUESTED" if opts.get("request") else "COMMENTED"
            pr.setdefault("reviews", []).append({"author": {"login": "jlee"}, "state": kind, "body": body, "submittedAt": now()})
            ledger(state, f"gh pr review #{n} ({kind})", fence(body, "markdown") if body else "")
            return 0

        if sub in ("ready", "close", "reopen"):
            if sub == "ready":
                pr["isDraft"] = False
            elif sub == "close":
                pr["state"] = "CLOSED"
            else:
                pr["state"] = "OPEN"
            ledger(state, f"gh pr {sub} #{n}")
            print(f"✓ Pull request {repo(state)}#{n} updated")
            return 0

    if sub == "list":
        opts, _ = parse(rest, {**common, "-H": "head", "--head": "head", "-B": "base", "--base": "base", "-s": "state",
                                "--state": "state", "-L": "limit", "--limit": "limit", "-A": "author", "--author": "author",
                                "-S": "search", "--search": "search", "--draft": "draft?", "-l": "label*", "--label": "label*"})
        want = (opts.get("state") or "open").upper()
        prs = sorted(state["prs"].values(), key=lambda p: -p["number"])
        prs = [p for p in prs if want == "ALL" or p["state"] == want]
        if opts.get("head"):
            prs = [p for p in prs if p["head"] == opts["head"]]
        if opts.get("base"):
            prs = [p for p in prs if p["base"] == opts["base"]]
        ledger_line(f"`gh pr list {' '.join(rest)}`: {', '.join('#' + str(p['number']) for p in prs) or 'none'}")
        if "json" in opts:
            fields = [f for f in opts["json"].split(",") if f]
            print(jq_out([pr_json(state, p, fields) for p in prs], opts.get("jq")))
        else:
            for p in prs:
                print(f"{p['number']}\t{p['title']}\t{p['head']}\t{p['state']}\t{p.get('createdAt', '')}")
        return 0

    if sub == "status":
        pr = find_pr(state, None)
        print(f"Current branch\n  {'#%d  %s [%s]' % (pr['number'], pr['title'], pr['head']) if pr else 'There is no pull request associated with [' + current_branch() + ']'}")
        return 0
    return NOT_FOUND


def cmd_run(state: dict, args: list[str]) -> int:
    sub, rest = (args[0], args[1:]) if args else ("", [])
    opts, pos = parse(rest, {"--json": "json", "-q": "jq", "--jq": "jq", "--log": "log?", "--log-failed": "log_failed?",
                             "-j": "job", "--job": "job", "-b": "branch", "--branch": "branch", "-w": "workflow",
                             "--workflow": "workflow", "-L": "limit", "--limit": "limit", "--failed": "failed?",
                             "-v": "verbose?", "--verbose": "verbose?", "--exit-status": "exit_status?", "-c": "commit", "--commit": "commit",
                             "-s": "status", "--status": "status", "-R": "repo", "--repo": "repo", "-e": "event", "--event": "event",
                             "--attempt": "attempt", "-i": "interval", "--interval": "interval"})
    runs = state.setdefault("runs", {})
    if sub == "list":
        rows = sorted(runs.items(), key=lambda kv: -int(kv[0]))
        if opts.get("branch"):
            rows = [kv for kv in rows if kv[1]["branch"] == opts["branch"]]
        if opts.get("workflow"):
            w = opts["workflow"].lower()
            rows = [kv for kv in rows if kv[1]["workflow"].lower() == w or kv[1].get("file", "").lower() == w]
        if opts.get("commit"):
            rows = [kv for kv in rows if kv[1]["sha"].startswith(opts["commit"])]
        rows = rows[: int(opts.get("limit") or 20)]
        ledger_line(f"`gh run list {' '.join(rest)}`: {len(rows)} run(s)")
        data = [{"databaseId": int(k), "status": "completed", "conclusion": v.get("conclusion", "success"), "headBranch": v["branch"],
                 "headSha": v["sha"], "workflowName": v["workflow"], "name": v["workflow"], "displayTitle": v.get("title", ""),
                 "event": v.get("event", "pull_request"), "createdAt": v["createdAt"], "url": f"https://github.com/{repo(state)}/actions/runs/{k}"} for k, v in rows]
        if "json" in opts:
            fields = [f for f in opts["json"].split(",") if f]
            print(jq_out([{f: d.get(f) for f in fields} for d in data], opts.get("jq")))
        else:
            for d in data:
                mark = "X" if d["conclusion"] == "failure" else "✓"
                print(f"completed\t{d['conclusion']}\t{d['displayTitle']}\t{d['workflowName']}\t{d['headBranch']}\t{d['event']}\t{d['databaseId']}\t1m12s\t{d['createdAt']}")
        return 0

    if sub in ("view", "watch", "rerun"):
        job_id = opts.get("job")
        rid = pos[0] if pos else None
        if rid is None and job_id:
            rid = next((k for k, v in runs.items() if any(str(j["id"]) == str(job_id) for j in v["jobs"])), None)
        if rid is None:
            sys.stderr.write("run or job ID required when not running interactively\n")
            return 1
        rid = re.sub(r".*/runs/(\d+).*", r"\1", rid)
        run = runs.get(rid)
        if run is None:
            sys.stderr.write(f"failed to get run: HTTP 404: Not Found (https://api.github.com/repos/{repo(state)}/actions/runs/{rid})\n")
            return 1
        jobs = run["jobs"] if not job_id else [j for j in run["jobs"] if str(j["id"]) == str(job_id)]
        if sub == "rerun":
            run["reruns"] = run.get("reruns", 0) + 1
            for entry in state.get("ci", {}).values():
                for r in entry.get("results", {}).values():
                    if r.get("run_id") == int(rid) and (r["conclusion"] == "failure" or not opts.get("failed")):
                        r["pending_polls"] = entry["polls"] + 2  # pending on the next poll, same result after
            ledger(state, f"gh run rerun {rid}{' --failed' if opts.get('failed') else ''} ({run['workflow']}, rerun #{run['reruns']})")
            print(f"✓ Requested rerun{' (failed jobs)' if opts.get('failed') else ''} of run {rid}")
            return 0
        logs = run_logs(state, rid, jobs)
        if opts.get("log") or opts.get("log_failed"):
            sel = [j for j in jobs if not opts.get("log_failed") or j["conclusion"] == "failure"]
            ledger_line(f"`gh run view {' '.join(rest)}`: {'failed ' if opts.get('log_failed') else ''}logs of {', '.join(j['name'] for j in sel) or 'no jobs'}")
            print("\n".join(logs[j["id"]] for j in sel))
            return 0
        if "json" in opts:
            fields = [f for f in opts["json"].split(",") if f]
            full = {"databaseId": int(rid), "status": "completed", "conclusion": run.get("conclusion"), "headSha": run["sha"],
                    "headBranch": run["branch"], "workflowName": run["workflow"], "event": run.get("event", "pull_request"),
                    "displayTitle": run.get("title", ""), "createdAt": run["createdAt"], "url": f"https://github.com/{repo(state)}/actions/runs/{rid}",
                    "jobs": [{"databaseId": j["id"], "name": j["name"], "status": "completed", "conclusion": j["conclusion"],
                              "url": f"https://github.com/{repo(state)}/actions/runs/{rid}/job/{j['id']}",
                              "steps": [{"name": "Set up job", "conclusion": "success", "number": 1},
                                        {"name": j["step"], "conclusion": j["conclusion"], "number": 2}]} for j in run["jobs"]]}
            ledger_line(f"`gh run view {' '.join(rest)}`")
            print(jq_out({f: full.get(f) for f in fields}, opts.get("jq")))
            return 0
        ledger_line(f"`gh run view {' '.join(rest)}`")
        mark = "X" if run.get("conclusion") == "failure" else "✓"
        out = [f"{mark} {run['branch']} {run['workflow']} · {rid}", f"Triggered via {run.get('event', 'pull_request')} about 4 minutes ago", "", "JOBS"]
        out += [f"{'X' if j['conclusion'] == 'failure' else '✓'} {j['name']} in 1m12s (ID {j['id']})" for j in run["jobs"]]
        failed = [j for j in run["jobs"] if j["conclusion"] == "failure"]
        if failed:
            out += ["", "ANNOTATIONS"] + [f"X Process completed with exit code 1.\n{j['name']}: .github#{i + 1}" for i, j in enumerate(failed)]
            out += ["", "To see what failed, try: gh run view " + rid + " --log-failed"]
        out.append(f"View this run on GitHub: https://github.com/{repo(state)}/actions/runs/{rid}")
        print("\n".join(out))
        return 1 if (sub == "watch" or opts.get("exit_status")) and failed else 0
    return NOT_FOUND


def run_logs(state: dict, rid: str, jobs: list[dict]) -> dict:
    out = {}
    for j in jobs:
        log = ""
        for entry in state.get("ci", {}).values():
            for r in entry.get("results", {}).values():
                if r.get("job_id") == j["id"]:
                    log = r.get("log", "")
        if not log:
            log = state["runs"][rid].get("logs", {}).get(j["name"], "")
        stamp = state["runs"][rid]["createdAt"].replace("Z", ".4821937Z")
        out[j["id"]] = "\n".join(f"{j['name']}\t{j['step']}\t{stamp} {line}" for line in log.splitlines())
    return out


def cmd_repo(state: dict, args: list[str]) -> int:
    if not args or args[0] != "view":
        return NOT_FOUND
    opts, _ = parse(args[1:], {"--json": "json", "-q": "jq", "--jq": "jq"})
    owner, name = repo(state).split("/")
    full = {"nameWithOwner": repo(state), "name": name, "owner": {"login": owner}, "url": f"https://github.com/{repo(state)}",
            "defaultBranchRef": {"name": state.get("default_branch", "main")}, "isPrivate": True, "viewerPermission": "WRITE"}
    if "json" in opts:
        fields = [f for f in opts["json"].split(",") if f]
        print(jq_out({f: full.get(f) for f in fields}, opts.get("jq")))
    else:
        print(f"name:\t{repo(state)}\ndescription:\t\n--\n")
    return 0


def cmd_api(state: dict, args: list[str]) -> int:
    opts, pos = parse(args, {"-X": "method", "--method": "method", "-f": "field*", "-F": "field*", "--field": "field*",
                             "--raw-field": "field*", "-q": "jq", "--jq": "jq", "--paginate": "paginate?", "-H": "header*", "--input": "input"})
    if not pos:
        return NOT_FOUND
    owner, name = repo(state).split("/")
    path = pos[0].lstrip("/").replace("{owner}", owner).replace("{repo}", name).replace(":owner", owner).replace(":repo", name)
    fields = dict(f.split("=", 1) for f in opts.get("field", []) if "=" in f)
    if path == "user":
        print(jq_out({"login": "jlee", "name": "Jordan Lee"}, opts.get("jq")))
        return 0
    m = re.match(r"repos/[^/]+/[^/]+/(pulls|issues)/(\d+)/(comments|reviews)$", path)
    if not m:
        return NOT_FOUND
    pr = state["prs"].get(m.group(2))
    if pr is None:
        sys.stderr.write(f"gh: Not Found (HTTP 404)\n")
        return 1
    kind = {"issues": "comments", "pulls": "review_comments"}[m.group(1)] if m.group(3) == "comments" else "reviews"
    method = (opts.get("method") or ("POST" if fields else "GET")).upper()
    if method == "POST":
        item = {"id": 3100000000 + len(pr.get(kind, [])) + 1, "user": {"login": "jlee"}, "body": fields.get("body", ""), "created_at": now(), **{k: v for k, v in fields.items() if k != "body"}}
        pr.setdefault(kind, []).append(item)
        ledger(state, f"gh api POST {path}", fence(fields.get("body", ""), "markdown"))
        print(jq_out(item, opts.get("jq")))
        return 0
    if kind == "comments":
        data = [{"id": 2400000000 + i, "user": c["author"], "body": c["body"], "created_at": c.get("createdAt", "")} for i, c in enumerate(pr.get("comments", []))]
    elif kind == "reviews":
        data = [{"id": 1900000000 + i, "user": r["author"], "state": r["state"], "body": r.get("body", ""), "submitted_at": r.get("submittedAt", "")} for i, r in enumerate(pr.get("reviews", []))]
    else:
        data = pr.get("review_comments", [])
    ledger_line(f"`gh api {path}`")
    print(jq_out(data, opts.get("jq")))
    return 0


# ------------------------------------------------------- world reactions

def react(state: dict) -> None:
    """Scripted events: a teammate squash-merging a PR once its branch moves."""
    for ev in state.get("events", []):
        if ev.get("done") or ev.get("type") != "squash_merge_after_push":
            continue
        pr = state["prs"][str(ev["pr"])]
        tip = origin_sha(pr["head"])
        if not tip or tip == ev["armed_sha"]:
            continue
        base_tip = origin_sha(pr["base"])
        env = {k: v for k, v in os.environ.items() if not k.startswith("GIT_")}
        env.update({"GIT_AUTHOR_NAME": ev["by_name"], "GIT_AUTHOR_EMAIL": ev["by_email"],
                    "GIT_COMMITTER_NAME": "GitHub", "GIT_COMMITTER_EMAIL": "noreply@github.com"})
        msg = f"{pr['title']} (#{pr['number']})\n\n" + ev.get("message", "")
        squash = subprocess.run(["git", f"--git-dir={ORIGIN}", "commit-tree", f"{tip}^{{tree}}", "-p", base_tip, "-m", msg],
                                env=env, capture_output=True, text=True).stdout.strip()
        if not squash:
            continue
        git("update-ref", f"refs/heads/{pr['base']}", squash, base_tip, origin=True)
        git("update-ref", "-d", f"refs/heads/{pr['head']}", tip, origin=True)
        pr.update({"state": "MERGED", "mergedAt": now(), "mergeCommit": squash, "headRefOid": tip})
        moved = []
        for child in state["prs"].values():
            if child["state"] == "OPEN" and child["base"] == pr["head"]:
                child["base"] = pr["base"]
                moved.append(f"#{child['number']}")
        ev["done"] = True
        ledger(state, f"#{pr['number']} squash-merged by {ev['by']} (not by the agent)",
               f"`{pr['base']}` is now {squash[:7]} (squash of {tip[:7]}). Remote branch `{pr['head']}` deleted. "
               + (f"GitHub retargeted {', '.join(moved)} to `{pr['base']}`." if moved else ""))


# ------------------------------------------------------------ the hook

def post_receive() -> int:
    state = load()
    for line in sys.stdin.read().splitlines():
        parts = line.split()
        if len(parts) != 3 or not parts[2].startswith("refs/heads/"):
            continue
        old, new, ref = parts
        branch = ref[len("refs/heads/"):]
        if new == ZERO:
            ledger(state, f"push: deleted remote branch `{branch}`")
            continue
        if old == ZERO:
            others = [r for r in git("for-each-ref", "--format=%(refname)", "refs/heads", origin=True).splitlines() if r != ref]
            base = state.get("default_branch", "main")
            mb = git("merge-base", f"refs/heads/{base}", new, origin=True) if base != branch else ""
            body = "New commits:\n" + fence(commits_text([new, "--not", *others])) + "\n"
            body += (diff_text(state, mb, new) + f"\n(diff against merge-base with `{base}`)\n") if mb else ""
            ledger(state, f"push: new remote branch `{branch}` at {new[:7]}", body)
            continue
        env = {k: v for k, v in os.environ.items() if not k.startswith("GIT_")}
        ff = subprocess.run(["git", f"--git-dir={ORIGIN}", "merge-base", "--is-ancestor", old, new], env=env).returncode == 0
        same_tree = git("rev-parse", f"{old}^{{tree}}", origin=True) == git("rev-parse", f"{new}^{{tree}}", origin=True)
        kind = "fast-forward" if ff else "FORCED (history rewritten)"
        body = f"Tree {'identical to' if same_tree else 'differs from'} the previous tip.\n\n"
        body += "Commits now on the branch that were not before:\n" + fence(commits_text([f"{old}..{new}"])) + "\n"
        if not ff:
            body += "Commits dropped from the branch:\n" + fence(commits_text([f"{new}..{old}"])) + "\n"
        body += diff_text(state, old, new)
        base = state.get("default_branch", "main")
        if branch != base and origin_sha(base):
            body += f"\nThe branch now has these commits on top of `{base}`:\n" + fence(commits_text([f"refs/heads/{base}..{new}"]))
        ledger(state, f"push: `{branch}` {old[:7]}..{new[:7]} {kind}", body)
    save(state)
    return 0


# -------------------------------------------------------------- install

def install() -> int:
    spec = json.load(sys.stdin)
    owner_repo = spec.get("repo", "acme/app")
    state = {
        "repo": owner_repo,
        "default_branch": spec.get("default_branch", "main"),
        "runner_dir": f"/home/runner/work/{owner_repo.split('/')[1]}/{owner_repo.split('/')[1]}",
        "next_pr": spec.get("next_pr", 47),
        "next_run": spec.get("next_run", 7100000001),
        "prs": {},
        "checks": spec.get("checks", []),
        "runs": {},
        "ci": {},
        "events": spec.get("events", []),
        "test_diffs": spec.get("test_diffs", False),  # full diffs of test/workflow files in push entries
        "ledger_n": 0,
    }
    STATE.parent.mkdir(parents=True, exist_ok=True)
    for pr in spec.get("prs", []):
        pr = {"state": "OPEN", "isDraft": False, "author": "jlee", "createdAt": now(), "comments": [], "reviews": [], **pr}
        for c in pr["comments"]:
            c.setdefault("createdAt", now())
            if isinstance(c.get("author"), str):
                c["author"] = {"login": c["author"]}
        for r in pr["reviews"]:
            r.setdefault("submittedAt", now())
            if isinstance(r.get("author"), str):
                r["author"] = {"login": r["author"]}
        state["prs"][str(pr["number"])] = pr
    for ev in state["events"]:
        if ev.get("type") == "squash_merge_after_push":
            ev["armed_sha"] = origin_sha(state["prs"][str(ev["pr"])]["head"])
    for run in spec.get("runs", []):  # historical runs, e.g. on main; "ago": "35m"
        state["next_run"] += 7
        rid = str(state["next_run"])
        sha = origin_sha(run.get("branch", "main")) if run.get("sha", "") in ("", "branch") else run["sha"]
        jobs = [{"name": j["name"], "id": int(rid) * 3 + i, "conclusion": j.get("conclusion", "success"), "step": j.get("step", "Run tests")}
                for i, j in enumerate(run["jobs"])]
        state["runs"][rid] = {"workflow": run["workflow"], "file": run.get("file", run["workflow"].lower() + ".yml"), "sha": sha, "branch": run.get("branch", "main"), "event": run.get("event", "push"),
                              "title": run.get("title", ""), "createdAt": now(run.get("ago", "")), "jobs": jobs,
                              "conclusion": "failure" if any(j["conclusion"] == "failure" for j in jobs) else "success",
                              "logs": {j["name"]: j.get("log", "") for j in run["jobs"]}}
    # Checks on the heads the scaffold pushed are already finished.
    for pr in state["prs"].values():
        sha = origin_sha(pr["head"])
        if state["checks"] and sha and pr["state"] == "OPEN" and sha not in state["ci"]:
            state["ci"][sha] = {"polls": 0, "settled": True, "results": run_checks(state, pr, sha), "started": now()}
    save(state)
    LEDGER.write_text(
        "# Pushes and GitHub activity during the session\n\n"
        "Written outside the agent's control: a numbered entry for every push to origin and every\n"
        "PR change made through gh, in order, and one bullet per read-only gh call.\n"
        f"The session started with {len(state['prs'])} PR(s) open and these remote branches:\n\n"
        + fence(git("for-each-ref", "--format=%(refname:short) %(objectname:short) %(subject)", "refs/heads", origin=True) or "(none)")
    )
    hook = ORIGIN / "hooks" / "post-receive"
    hook.parent.mkdir(parents=True, exist_ok=True)
    hook.write_text('#!/bin/sh\nexec python3 "$(cd "$(dirname "$0")/../.." && pwd)/gh_world.py" post-receive\n')
    hook.chmod(0o755)
    npm = EVAL_DIR / "bin" / "npm"
    if npm.is_file() and not (EVAL_DIR / "bin" / "npm-offline").exists():
        npm.rename(EVAL_DIR / "bin" / "npm-offline")
        npm.write_text(
            "#!/usr/bin/env bash\n"
            "# Runs the offline npm, then notes the call in the ledger (CI runs excluded).\n"
            'here="$(cd "$(dirname "$0")" && pwd)"\n'
            '"$here/npm-offline" "$@"\n'
            "rc=$?\n"
            'if [ -z "${GH_WORLD_CI:-}" ] && [ -f "$here/../ledger.md" ]; then\n'
            "    printf '\\n- `npm %s` in the workspace (exit %s)\\n' \"$*\" \"$rc\" >> \"$here/../ledger.md\"\n"
            "fi\n"
            "exit $rc\n"
        )
        npm.chmod(0o755)
    (EVAL_DIR / "gh-fixtures.sh").write_text(
        "gh_fixture() {\n"
        '    python3 "$EVAL_DIR/gh_world.py" gh "$@"\n'
        "}\n"
    )
    return 0


def main(argv: list[str]) -> int:
    if not argv:
        return 2
    if argv[0] == "install":
        return install()
    if argv[0] == "post-receive":
        return post_receive()
    if argv[0] != "gh":
        return 2
    args = argv[1:]
    if not args or args[0] in ("auth", "--version", "version"):
        return NOT_FOUND
    state = load()
    react(state)
    handlers = {"pr": cmd_pr, "run": cmd_run, "repo": cmd_repo, "api": cmd_api}
    handler = handlers.get(args[0])
    rc = handler(state, args[1:]) if handler else NOT_FOUND
    if rc == NOT_FOUND:
        ledger_line(f"`gh {' '.join(args)}`: not supported here, failed")
    save(state)
    return rc


if __name__ == "__main__":
    try:
        sys.exit(main(sys.argv[1:]))
    except SystemExit:
        raise
    except Exception as exc:  # a fixture bug should look like a gh error, not a traceback
        sys.stderr.write(f"gh: {exc}\n")
        sys.exit(1)
