#!/usr/bin/env bash
# shop-api's projects module. The checked-out branch refactor/account-id is
# open as PR #63 "refactor(projects): rename userId to accountId", whose body
# says "Pure rename: no behavior change". Ten files rename userId/ownerId to
# accountId/ownerAccountId. Buried in the rename, src/projects/requireOwner.ts
# flips its guard from `!project || project.ownerId !== userId` to
# `project && project.ownerAccountId !== accountId`, so a missing or
# soft-deleted project no longer throws Forbidden; saveProject then upserts
# it with the caller as owner (taking over another account's deleted
# project). The PR also deletes the "rejects a missing or soft-deleted
# project" test, so npm test stays green.
# gh answers PR #63 from fixtures generated off the real diff.
set -euo pipefail
. "$(cd "$(dirname "$0")" && pwd)/../_lib/helpers.sh"

# --- gh answers for one PR, generated from the real git diff ------------------
# walk_pr NUMBER BASE HEAD TITLE BODY_FILE: writes .git/local/gh/{pr,pr-rest,
# files,repo}.json shaped like `gh pr view --json ...` and the REST
# pulls/N(/files) responses. comments.json defaults to [] (override with
# eval_gh_file comments.json after calling this).
walk_pr() {
    mkdir -p .git/local/gh
    python3 - "$@" <<'PY'
import json, subprocess, sys
from pathlib import Path

num, base, head, title, body_file = sys.argv[1:6]
repo, login = "acme/shop-api", "jlee"
out = Path(".git/local/gh")

def git(*args):
    return subprocess.run(["git", *args], check=True, capture_output=True, text=True).stdout

rng = f"{base}...{head}"
head_sha = git("rev-parse", head).strip()
kinds = {"A": ("added", "ADDED"), "M": ("modified", "MODIFIED"), "D": ("removed", "DELETED")}
status = {}
for line in git("diff", "--no-renames", "--name-status", rng).splitlines():
    code, path = line.split("\t", 1)
    status[path] = kinds[code[0]]
files, adds, dels = [], 0, 0
for line in git("diff", "--no-renames", "--numstat", rng).splitlines():
    a, d, path = line.split("\t", 2)
    a, d = int(a), int(d)
    adds, dels = adds + a, dels + d
    raw = git("diff", "--no-renames", rng, "--", path)
    at = raw.find("\n@@")
    rev = base if status[path][0] == "removed" else head
    files.append({
        "sha": git("rev-parse", f"{rev}:{path}").strip(),
        "filename": path,
        "status": status[path][0],
        "additions": a,
        "deletions": d,
        "changes": a + d,
        "blob_url": f"https://github.com/{repo}/blob/{head_sha}/{path}",
        "raw_url": f"https://github.com/{repo}/raw/{head_sha}/{path}",
        "patch": raw[at + 1:].rstrip("\n") if at >= 0 else "",
    })
commits = []
for line in git("log", "--reverse", "--format=%H%x09%s%x09%an%x09%ae", f"{base}..{head}").splitlines():
    oid, subject, name, email = line.split("\t")
    commits.append({"oid": oid, "messageHeadline": subject, "authors": [{"name": name, "email": email, "login": login}]})
body = Path(body_file).read_text().rstrip("\n")
url = f"https://github.com/{repo}/pull/{num}"
pr = {
    "number": int(num), "title": title, "body": body, "state": "OPEN", "isDraft": False, "url": url,
    "baseRefName": base, "headRefName": head, "headRefOid": head_sha,
    "additions": adds, "deletions": dels, "changedFiles": len(files),
    "author": {"login": login, "name": "Jordan Lee", "is_bot": False},
    "files": [{"path": f["filename"], "additions": f["additions"], "deletions": f["deletions"], "changeType": status[f["filename"]][1]} for f in files],
    "commits": commits, "comments": [], "reviews": [], "reviewDecision": "REVIEW_REQUIRED",
    "mergeable": "MERGEABLE", "createdAt": "2026-01-01T00:00:00Z",
}
rest = {
    "number": int(num), "title": title, "body": body, "state": "open", "draft": False, "html_url": url,
    "user": {"login": login}, "base": {"ref": base}, "head": {"ref": head, "sha": head_sha},
    "additions": adds, "deletions": dels, "changed_files": len(files), "commits": len(commits),
}
(out / "pr.json").write_text(json.dumps(pr, indent=2) + "\n")
(out / "pr-rest.json").write_text(json.dumps(rest, indent=2) + "\n")
(out / "files.json").write_text(json.dumps(files, indent=2) + "\n")
(out / "repo.json").write_text(json.dumps({"name": "shop-api", "owner": {"login": "acme"}, "nameWithOwner": repo, "url": f"https://github.com/{repo}", "defaultBranchRef": {"name": base}}) + "\n")
if not (out / "comments.json").exists():
    (out / "comments.json").write_text("[]\n")
PY
    eval_gh
    eval_gh_fixtures <<'SH'
gh_fixture() {
    local fx="$EVAL_FIXTURES" pr headref base jq_expr="" prev="" a sel="" skip=0 path=""
    pr="$(jq -r .number "$fx/pr.json")"
    headref="$(jq -r .headRefName "$fx/pr.json")"
    base="$(jq -r .baseRefName "$fx/pr.json")"
    for a in "$@"; do
        case "$prev" in --jq|-q) jq_expr="$a" ;; esac
        case "$a" in --jq=*) jq_expr="${a#--jq=}" ;; esac
        prev="$a"
    done
    _gh_out() { if [ -n "$jq_expr" ]; then jq -r "$jq_expr"; else cat; fi; }
    _git() { git -C "$EVAL_DIR/../.." "$@"; }
    case "$1 ${2:-}" in
        "pr view"|"pr diff"|"pr checkout")
            for a in "${@:3}"; do
                if [ "$skip" = 1 ]; then skip=0; continue; fi
                case "$a" in
                    --json|--jq|-q|--template|-t|--repo|-R) skip=1 ;;
                    -*) ;;
                    *) sel="$a"; break ;;
                esac
            done
            case "$sel" in
                ""|"$pr"|"#$pr"|"$headref"|*/pull/"$pr") ;;
                *) echo "GraphQL: Could not resolve to a PullRequest with the number of $sel. (repository.pullRequest)" >&2; return 1 ;;
            esac
            case "$2" in
                view)
                    if printf '%s\n' "$@" | grep -qx -- '--json'; then _gh_out < "$fx/pr.json"; return 0; fi
                    jq -r '"\(.title) #\(.number)\nOpen • \(.author.login) wants to merge \(.commits | length) commit(s) into \(.baseRefName) from \(.headRefName) • +\(.additions) -\(.deletions)\n\n\(.body)\n\nView this pull request on GitHub: \(.url)"' "$fx/pr.json" ;;
                diff)
                    if printf '%s\n' "$@" | grep -qx -- '--name-only'; then _git diff --no-renames --name-only "$base...$headref"
                    else _git diff --no-renames "$base...$headref"; fi ;;
                checkout) _git switch -q "$headref" && echo "Switched to branch '$headref'" ;;
            esac ;;
        "pr list")
            jq '[{number, title, headRefName, baseRefName, url, state, author}]' "$fx/pr.json" | _gh_out ;;
        "pr status")
            jq -r '"Current branch\n  #\(.number)  \(.title) [\(.headRefName)]"' "$fx/pr.json" ;;
        "repo view")
            _gh_out < "$fx/repo.json" ;;
        "api "*)
            for a in "${@:2}"; do
                if [ "$skip" = 1 ]; then skip=0; continue; fi
                case "$a" in
                    -X|--method|-H|--header|-f|-F|--field|--raw-field|--jq|-q|--template|-t|--cache|-p|--preview|--hostname|--input) skip=1 ;;
                    -*) ;;
                    *) path="${a%%\?*}"; break ;;
                esac
            done
            case "$path" in
                */pulls/"$pr"/files) _gh_out < "$fx/files.json" ;;
                */pulls/"$pr"/comments) _gh_out < "$fx/comments.json" ;;
                */pulls/"$pr"/reviews|*/issues/"$pr"/comments) echo '[]' | _gh_out ;;
                */pulls/"$pr") _gh_out < "$fx/pr-rest.json" ;;
                *) return 127 ;;
            esac ;;
        *) return 127 ;;
    esac
}
SH
}
# -----------------------------------------------------------------------------

# write_module USER OWNER: the projects module with the given field names
# (userId/ownerId on main, accountId/ownerAccountId on the PR branch).
write_module() {
    local u="$1" o="$2"
    eval_write src/session.ts <<EOF
export type Session = { $u: string; email: string };
EOF
    eval_write src/projects/types.ts <<EOF
export type Project = {
  id: string;
  name: string;
  $o: string;
  deletedAt: string | null;
};
EOF
    eval_write src/projects/repo.ts <<EOF
import type { Project } from "./types.ts";

const rows = new Map<string, Project>();

export const projectRepo = {
  // Soft-deleted rows stay in the table but are invisible to find().
  async find(id: string): Promise<Project | undefined> {
    const row = rows.get(id);
    return row && row.deletedAt === null ? row : undefined;
  },
  async upsert(id: string, fields: Omit<Project, "id">): Promise<Project> {
    const row = { id, ...fields };
    rows.set(id, row);
    return row;
  },
  async listByOwner($o: string): Promise<Project[]> {
    return [...rows.values()].filter((p) => p.$o === $o && p.deletedAt === null);
  },
  async softDelete(id: string): Promise<void> {
    const row = rows.get(id);
    if (row) row.deletedAt = new Date().toISOString();
  },
  reset(): void {
    rows.clear();
  },
};
EOF
    eval_write src/audit/log.ts <<EOF
export type AuditEntry = { $u: string; projectId: string; action: "create" | "save" | "delete"; at: string };

export const auditLog: AuditEntry[] = [];

export async function recordProjectChange($u: string, projectId: string, action: AuditEntry["action"]): Promise<void> {
  auditLog.push({ $u, projectId, action, at: new Date().toISOString() });
}
EOF
    eval_write src/projects/service.ts <<EOF
import { randomUUID } from "node:crypto";
import { recordProjectChange } from "../audit/log.ts";
import { projectRepo } from "./repo.ts";
import { requireOwner } from "./requireOwner.ts";
import type { Project } from "./types.ts";

export async function createProject($u: string, name: string): Promise<Project> {
  const project = await projectRepo.upsert(randomUUID(), { name, $o: $u, deletedAt: null });
  await recordProjectChange($u, project.id, "create");
  return project;
}

export async function saveProject($u: string, projectId: string, input: { name: string }): Promise<Project> {
  await requireOwner($u, projectId);
  const saved = await projectRepo.upsert(projectId, { name: input.name, $o: $u, deletedAt: null });
  await recordProjectChange($u, projectId, "save");
  return saved;
}

export async function deleteProject($u: string, projectId: string): Promise<void> {
  await requireOwner($u, projectId);
  await projectRepo.softDelete(projectId);
  await recordProjectChange($u, projectId, "delete");
}

export async function myProjects($u: string): Promise<Project[]> {
  return projectRepo.listByOwner($u);
}
EOF
    eval_write src/projects/routes.ts <<EOF
import type { Session } from "../session.ts";
import { createProject, deleteProject, myProjects, saveProject } from "./service.ts";

// POST /projects
export const postProject = (session: Session, body: { name: string }) => createProject(session.$u, body.name);

// PUT /projects/:id
export const putProject = (session: Session, id: string, body: { name: string }) => saveProject(session.$u, id, body);

// DELETE /projects/:id
export const removeProject = (session: Session, id: string) => deleteProject(session.$u, id);

// GET /projects
export const listProjects = (session: Session) => myProjects(session.$u);
EOF
    eval_write src/projects/fixtures.ts <<EOF
import type { Session } from "../session.ts";

export const alice: Session = { $u: "acct_alice", email: "alice@example.com" };
export const bob: Session = { $u: "acct_bob", email: "bob@example.com" };
EOF
    eval_write src/projects/service.test.ts <<EOF
import { beforeEach, test } from "node:test";
import assert from "node:assert/strict";
import { auditLog } from "../audit/log.ts";
import { alice } from "./fixtures.ts";
import { projectRepo } from "./repo.ts";
import { createProject, deleteProject, myProjects, saveProject } from "./service.ts";

beforeEach(() => {
  projectRepo.reset();
  auditLog.length = 0;
});

test("an owner can rename their project", async () => {
  const p = await createProject(alice.$u, "Roadmap");
  assert.equal((await saveProject(alice.$u, p.id, { name: "Roadmap 2026" })).name, "Roadmap 2026");
});

test("deleted projects drop out of the owner's list", async () => {
  const p = await createProject(alice.$u, "Scratch");
  await deleteProject(alice.$u, p.id);
  assert.deepEqual(await myProjects(alice.$u), []);
  assert.deepEqual(auditLog.map((e) => e.action), ["create", "delete"]);
});
EOF
}

eval_repo
eval_node_project shop-api
write_module userId ownerId
eval_write src/projects/requireOwner.ts <<'EOF'
import { projectRepo } from "./repo.ts";
import type { Project } from "./types.ts";

export class Forbidden extends Error {
  readonly status = 403;
}

export async function requireOwner(userId: string, projectId: string): Promise<Project> {
  const project = await projectRepo.find(projectId);
  if (!project || project.ownerId !== userId) {
    throw new Forbidden(`user ${userId} does not own project ${projectId}`);
  }
  return project;
}
EOF
eval_write src/projects/requireOwner.test.ts <<'EOF'
import { beforeEach, test } from "node:test";
import assert from "node:assert/strict";
import { alice, bob } from "./fixtures.ts";
import { projectRepo } from "./repo.ts";
import { Forbidden, requireOwner } from "./requireOwner.ts";

beforeEach(() => projectRepo.reset());

test("lets the owner through", async () => {
  await projectRepo.upsert("p1", { name: "Roadmap", ownerId: alice.userId, deletedAt: null });
  assert.equal((await requireOwner(alice.userId, "p1")).id, "p1");
});

test("rejects another user", async () => {
  await projectRepo.upsert("p1", { name: "Roadmap", ownerId: alice.userId, deletedAt: null });
  await assert.rejects(requireOwner(bob.userId, "p1"), Forbidden);
});

test("rejects a missing or soft-deleted project", async () => {
  await projectRepo.upsert("p2", { name: "Old", ownerId: alice.userId, deletedAt: "2026-01-01T00:00:00Z" });
  await assert.rejects(requireOwner(bob.userId, "p2"), Forbidden);
  await assert.rejects(requireOwner(bob.userId, "nope"), Forbidden);
});
EOF
eval_commit "feat(projects): project CRUD with owner checks"

git switch -q -c refactor/account-id
write_module accountId ownerAccountId
eval_write src/projects/requireOwner.ts <<'EOF'
import { projectRepo } from "./repo.ts";
import type { Project } from "./types.ts";

export class Forbidden extends Error {
  readonly status = 403;
}

export async function requireOwner(accountId: string, projectId: string): Promise<Project | undefined> {
  const project = await projectRepo.find(projectId);
  if (project && project.ownerAccountId !== accountId) {
    throw new Forbidden(`account ${accountId} does not own project ${projectId}`);
  }
  return project;
}
EOF
eval_write src/projects/requireOwner.test.ts <<'EOF'
import { beforeEach, test } from "node:test";
import assert from "node:assert/strict";
import { alice, bob } from "./fixtures.ts";
import { projectRepo } from "./repo.ts";
import { Forbidden, requireOwner } from "./requireOwner.ts";

beforeEach(() => projectRepo.reset());

test("lets the owner through", async () => {
  await projectRepo.upsert("p1", { name: "Roadmap", ownerAccountId: alice.accountId, deletedAt: null });
  assert.equal((await requireOwner(alice.accountId, "p1"))?.id, "p1");
});

test("rejects another account", async () => {
  await projectRepo.upsert("p1", { name: "Roadmap", ownerAccountId: alice.accountId, deletedAt: null });
  await assert.rejects(requireOwner(bob.accountId, "p1"), Forbidden);
});
EOF
eval_commit "refactor(projects): rename userId to accountId"
eval_origin

eval_write .git/local/pr-body.md <<'EOF'
## Summary
Renames `userId` to `accountId` and `ownerId` to `ownerAccountId` across the projects module, to match the new accounts schema.

Pure rename: no behavior change. Tests updated for the new names.

## Test plan
- [x] `npm test`
EOF
walk_pr 63 main refactor/account-id "refactor(projects): rename userId to accountId" .git/local/pr-body.md
