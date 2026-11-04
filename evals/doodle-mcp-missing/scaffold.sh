#!/usr/bin/env bash
# Same world as doodle-pr-mode: Next.js app "arena" on branch
# perdix-140-add-leaderboard, open as PR #42 against main, with a stub gh that
# answers the PR calls (so a run that skips the MCP check would get data).
# Unlike doodle-pr-mode there is no tldraw MCP: the case ships no
# mocks/tldraw/, so neither mcp__tldraw__create_diagram nor
# mcp__tldraw-render__create_diagram exists, and bruhs:state lists no MCPs.
set -euo pipefail
. "$(cd "$(dirname "$0")" && pwd)/../_lib/helpers.sh"

eval_repo
eval_node_project arena next react react-dom drizzle-orm
eval_state <<'JSON'
{
  "stack": {"structure": "single", "framework": "nextjs", "language": "typescript", "database": ["drizzle-postgres"], "testing": ["node:test"]},
  "tooling": {"mcps": [], "skills": []}
}
JSON

eval_write src/db/schema.ts <<'EOF'
import { integer, pgTable, text } from "drizzle-orm/pg-core";

export const players = pgTable("players", {
  id: text("id").primaryKey(),
  handle: text("handle").notNull(),
  totalPoints: integer("total_points").notNull().default(0),
});
EOF

eval_write src/lib/scores.ts <<'EOF'
export function rankByPoints<T extends { points: number }>(rows: readonly T[]): (T & { rank: number })[] {
  return [...rows].sort((a, b) => b.points - a.points).map((row, i) => ({ ...row, rank: i + 1 }));
}
EOF

eval_write src/components/Header.tsx <<'EOF'
export function Header({ title }: { title: string }) {
  return <header className="border-b p-4 text-lg font-semibold">{title}</header>;
}
EOF

eval_write src/legacy/top-players.ts <<'EOF'
import { players } from "../db/schema";

export const TOP_PLAYERS_TABLE = players;

export function topPlayersLabel(count: number): string {
  return `Top ${count} players of all time`;
}
EOF

eval_write src/app/page.tsx <<'EOF'
import { Header } from "../components/Header";
import { topPlayersLabel } from "../legacy/top-players";

export default function Home() {
  return (
    <main>
      <Header title="Arena" />
      <p>{topPlayersLabel(10)}</p>
    </main>
  );
}
EOF
eval_commit "feat: arena home with all-time top players"

git checkout -q -b perdix-140-add-leaderboard

eval_write src/db/schema.ts <<'EOF'
import { integer, pgTable, text } from "drizzle-orm/pg-core";

export const players = pgTable("players", {
  id: text("id").primaryKey(),
  handle: text("handle").notNull(),
  totalPoints: integer("total_points").notNull().default(0),
  weeklyPoints: integer("weekly_points").notNull().default(0),
});
EOF

eval_write src/leaderboard/query.ts <<'EOF'
import { desc } from "drizzle-orm";
import { players } from "../db/schema";
import { rankByPoints } from "../lib/scores";

export type LeaderboardRow = { handle: string; points: number; rank: number };

export async function weeklyLeaderboard(db: { select: Function }): Promise<LeaderboardRow[]> {
  const rows = await db.select({ handle: players.handle, points: players.weeklyPoints }).from(players).orderBy(desc(players.weeklyPoints));
  return rankByPoints(rows);
}
EOF

eval_write src/leaderboard/Leaderboard.tsx <<'EOF'
import type { LeaderboardRow } from "./query";

export function Leaderboard({ rows }: { rows: LeaderboardRow[] }) {
  return (
    <ol className="divide-y">
      {rows.map((row) => (
        <li key={row.handle} className="flex justify-between p-2">
          <span>
            {row.rank}. {row.handle}
          </span>
          <span>{row.points}</span>
        </li>
      ))}
    </ol>
  );
}
EOF

eval_write src/app/api/leaderboard/route.ts <<'EOF'
import { weeklyLeaderboard } from "../../../leaderboard/query";

export async function GET(): Promise<Response> {
  const { db } = await import("../../../db/client");
  return Response.json(await weeklyLeaderboard(db));
}
EOF

eval_write src/db/client.ts <<'EOF'
import { drizzle } from "drizzle-orm/node-postgres";

export const db = drizzle(process.env.DATABASE_URL ?? "");
EOF

eval_write src/app/page.tsx <<'EOF'
import { Header } from "../components/Header";
import { Leaderboard } from "../leaderboard/Leaderboard";

export default function Home() {
  return (
    <main>
      <Header title="Arena" />
      <Leaderboard rows={[]} />
    </main>
  );
}
EOF

git rm -q src/legacy/top-players.ts
eval_commit "feat: weekly leaderboard replaces all-time top players"
eval_origin

# gh fixtures generated from the real branch diff.
eval_gh
mkdir -p .git/local/gh
git diff main...HEAD > .git/local/gh/pr-42.diff
git diff --name-only main...HEAD > .git/local/gh/pr-42.names
python3 - "$(git rev-parse main)" "$(git rev-parse HEAD)" <<'PY'
import json, subprocess, sys
base, head = sys.argv[1], sys.argv[2]
status_map = {"A": "added", "M": "modified", "D": "removed", "R": "renamed"}
rows = []
numstat = {}
for line in subprocess.check_output(["git", "diff", "--numstat", f"{base}...{head}"], text=True).splitlines():
    add, dele, path = line.split("\t")
    numstat[path] = (int(add), int(dele))
for line in subprocess.check_output(["git", "diff", "--name-status", f"{base}...{head}"], text=True).splitlines():
    code, path = line.split("\t")[0], line.split("\t")[-1]
    add, dele = numstat[path]
    patch = subprocess.check_output(["git", "diff", f"{base}...{head}", "--", path], text=True)
    patch = patch[patch.index("@@"):] if "@@" in patch else ""
    rows.append({
        "sha": subprocess.check_output(["git", "rev-parse", f"{head if code != 'D' else base}:{path}"], text=True).strip(),
        "filename": path,
        "status": status_map[code[0]],
        "additions": add,
        "deletions": dele,
        "changes": add + dele,
        "blob_url": f"https://github.com/perdix-labs/arena/blob/{head}/{path}",
        "patch": patch,
    })
json.dump(rows, open(".git/local/gh/pr-42-files.json", "w"), indent=2)
pr = {
    "number": 42,
    "title": "PERDIX-140: Weekly leaderboard",
    "body": "Replaces the all-time top players list with a weekly leaderboard.\n\nFixes PERDIX-140",
    "state": "OPEN",
    "isDraft": False,
    "url": "https://github.com/perdix-labs/arena/pull/42",
    "headRefName": "perdix-140-add-leaderboard",
    "baseRefName": "main",
    "headRefOid": head,
    "baseRefOid": base,
    "author": {"login": "jlee"},
    "additions": sum(r["additions"] for r in rows),
    "deletions": sum(r["deletions"] for r in rows),
    "changedFiles": len(rows),
    "files": [{"path": r["filename"], "additions": r["additions"], "deletions": r["deletions"]} for r in rows],
}
json.dump(pr, open(".git/local/gh/pr-42.json", "w"), indent=2)
rest = {
    "number": 42, "state": "open", "title": pr["title"], "html_url": pr["url"],
    "head": {"ref": pr["headRefName"], "sha": head}, "base": {"ref": "main", "sha": base},
    "user": {"login": "jlee"}, "changed_files": len(rows),
}
json.dump(rest, open(".git/local/gh/pulls-42.json", "w"), indent=2)
json.dump({"nameWithOwner": "perdix-labs/arena", "name": "arena", "owner": {"login": "perdix-labs"},
           "url": "https://github.com/perdix-labs/arena", "defaultBranchRef": {"name": "main"}},
          open(".git/local/gh/repo.json", "w"), indent=2)
json.dump({"login": "jlee", "name": "Jordan Lee"}, open(".git/local/gh/user.json", "w"))
PY

eval_gh_fixtures <<'SH'
# Print a canned JSON file, applying --jq/-q like gh does.
emit_json() {
    local file="$1" expr="" prev=""
    shift
    for arg in "$@"; do
        case "$prev" in --jq|-q) expr="$arg" ;; esac
        case "$arg" in --jq=*) expr="${arg#--jq=}" ;; esac
        prev="$arg"
    done
    if [ -n "$expr" ]; then jq -r "$expr" "$file"; else cat "$file"; fi
}
gh_fixture() {
    case "$*" in
        "pr view"*|"pr list"*|"pr status"*)
            local a
            for a in "$@"; do
                case "${a#\#}" in
                    42|*/pull/42) ;;
                    *[!0-9]*|"") ;;
                    *) echo "GraphQL: Could not resolve to a PullRequest with the number of ${a#\#}." >&2; return 1 ;;
                esac
            done
            if [ "$1 $2" = "pr list" ]; then
                local tmp; tmp="$(mktemp)"; jq '[.]' "$EVAL_FIXTURES/pr-42.json" > "$tmp"; emit_json "$tmp" "$@"; rm -f "$tmp"
            else
                emit_json "$EVAL_FIXTURES/pr-42.json" "$@"
            fi ;;
        "pr diff"*"--name-only"*) cat "$EVAL_FIXTURES/pr-42.names" ;;
        "pr diff"*) cat "$EVAL_FIXTURES/pr-42.diff" ;;
        "api"*"pulls/42/files"*) emit_json "$EVAL_FIXTURES/pr-42-files.json" "$@" ;;
        "api"*"pulls/42"*) emit_json "$EVAL_FIXTURES/pulls-42.json" "$@" ;;
        "repo view"*) emit_json "$EVAL_FIXTURES/repo.json" "$@" ;;
        "api user"*) emit_json "$EVAL_FIXTURES/user.json" "$@" ;;
        "gist create"*) echo "https://gist.github.com/jlee/8c1f0e4b2a9d4c7e9b3f6a5d2e1c0b9a" ;;
        "pr comment 42"*|"pr comment https://github.com/perdix-labs/arena/pull/42"*|"pr comment --body"*|"pr comment -b"*)
            echo "https://github.com/perdix-labs/arena/pull/42#issuecomment-2471100042" ;;
        *) return 127 ;;
    esac
}
SH
