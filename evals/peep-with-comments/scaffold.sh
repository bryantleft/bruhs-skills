#!/usr/bin/env bash
# Game app on branch perdix-140-add-leaderboard with open PR #42 (Closes
# PERDIX-140). The PR has 4 unresolved review threads:
#   1. must-fix, lib/db/queries.ts:45: getTopAgents never sorts, so the
#      leaderboard shows the first agents inserted, not the best (real bug,
#      a RED test is easy to write)
#   2. nit, components/game/leaderboard-card.tsx: magic number 10, which is
#      also getTopAgents' default limit
#   3. suggestion, same file: show win rate as a percentage
#   4. question, lib/hooks/use-leaderboard.ts:12: why poll every 5s? (answer:
#      it reuses POLL_MS from lib/game/constants.ts, shared with useGameState)
# The existing test only checks the result length, so it passes on the bug.
set -euo pipefail
HERE="$(cd "$(dirname "$0")" && pwd)"
. "$HERE/../_lib/helpers.sh"

eval_repo
eval_node_project agent-arena next react react-dom
eval_state <<'JSON'
{
  "stack": {"structure": "single", "framework": "Next.js", "styling": ["Tailwind CSS"], "database": [], "testing": ["node:test"], "tooling": []},
  "tooling": {"mcps": ["linear"], "skills": []},
  "integrations": {"linear": {"mcpServer": "linear-perdix", "team": "PERDIX", "teamName": "Perdix", "project": "agent-arena", "projectName": "Agent Arena"}}
}
JSON
eval_write lib/db/store.ts <<'EOF'
// In-memory store standing in for the database in this app's tests and dev mode.
export type AgentStat = { agentId: string; name: string; wins: number; games: number; winRate: number };
export type Match = { id: string; winnerId: string; loserId: string; playedAt: string };

const agentStats: AgentStat[] = [];
const matches: Match[] = [];

export const store = {
  agentStats: (): AgentStat[] => [...agentStats],
  matches: (): Match[] => [...matches],
  insertAgentStat(row: AgentStat): void {
    agentStats.push(row);
  },
  insertMatch(row: Match): void {
    matches.push(row);
  },
  reset(): void {
    agentStats.length = 0;
    matches.length = 0;
  },
};
EOF
eval_write lib/db/queries.ts <<'EOF'
import { store, type AgentStat, type Match } from "./store.ts";

export function getAgent(agentId: string): AgentStat | undefined {
  return store.agentStats().find((a) => a.agentId === agentId);
}

export function getRecentMatches(agentId: string, limit = 20): Match[] {
  return store
    .matches()
    .filter((m) => m.winnerId === agentId || m.loserId === agentId)
    .sort((a, b) => b.playedAt.localeCompare(a.playedAt))
    .slice(0, limit);
}

export function getHeadToHead(a: string, b: string): { aWins: number; bWins: number } {
  let aWins = 0;
  let bWins = 0;
  for (const m of store.matches()) {
    if (m.winnerId === a && m.loserId === b) aWins++;
    if (m.winnerId === b && m.loserId === a) bWins++;
  }
  return { aWins, bWins };
}
EOF
eval_write lib/game/constants.ts <<'EOF'
// How often clients poll game state. Matches finish every few seconds during a
// tournament, so anything slower makes the bracket look frozen.
export const POLL_MS = 5_000;
EOF
eval_write lib/hooks/use-game-state.ts <<'EOF'
import { useQuery } from "@tanstack/react-query";
import { POLL_MS } from "../game/constants.ts";

export function useGameState(gameId: string) {
  return useQuery({
    queryKey: ["game", gameId],
    queryFn: () => fetch(`/api/games/${gameId}`).then((r) => r.json()),
    refetchInterval: POLL_MS,
  });
}
EOF
eval_write lib/db/queries.test.ts <<'EOF'
import { test, beforeEach } from "node:test";
import assert from "node:assert/strict";
import { store } from "./store.ts";
import { getHeadToHead, getRecentMatches } from "./queries.ts";

beforeEach(() => store.reset());

test("recent matches are newest first", () => {
  store.insertMatch({ id: "m1", winnerId: "a", loserId: "b", playedAt: "2026-01-01T00:00:00Z" });
  store.insertMatch({ id: "m2", winnerId: "b", loserId: "a", playedAt: "2026-01-02T00:00:00Z" });
  assert.deepEqual(getRecentMatches("a").map((m) => m.id), ["m2", "m1"]);
});

test("head to head counts both directions", () => {
  store.insertMatch({ id: "m1", winnerId: "a", loserId: "b", playedAt: "2026-01-01T00:00:00Z" });
  store.insertMatch({ id: "m2", winnerId: "a", loserId: "b", playedAt: "2026-01-02T00:00:00Z" });
  assert.deepEqual(getHeadToHead("a", "b"), { aWins: 2, bWins: 0 });
});
EOF
eval_commit "feat: agent stats store and match queries"

# --- the PR branch ----------------------------------------------------------
git switch -q -c perdix-140-add-leaderboard
cat >> lib/db/queries.ts <<'EOF'

export function getWinRate(agentId: string): number {
  const agent = getAgent(agentId);
  if (!agent || agent.games === 0) return 0;
  return agent.wins / agent.games;
}

export function getAgentCount(): number {
  return store.agentStats().length;
}

export function hasPlayed(agentId: string): boolean {
  return getRecentMatches(agentId, 1).length > 0;
}

export function getTotalMatches(): number {
  return store.matches().length;
}

export function getTopAgents(limit = 10): AgentStat[] {
  const rows = store.agentStats();
  return rows.slice(0, limit);
}
EOF
perl -pi -e 's/import { getHeadToHead, getRecentMatches } from/import { getHeadToHead, getRecentMatches, getTopAgents } from/' lib/db/queries.test.ts
cat >> lib/db/queries.test.ts <<'EOF'

test("top agents respects the limit", () => {
  for (let i = 0; i < 12; i++) {
    store.insertAgentStat({ agentId: `a${i}`, name: `Agent ${i}`, wins: i, games: 12, winRate: i / 12 });
  }
  assert.equal(getTopAgents().length, 10);
});
EOF
eval_write lib/hooks/use-leaderboard.ts <<'EOF'
import { useQuery } from "@tanstack/react-query";
import type { AgentStat } from "../db/store.ts";
import { POLL_MS } from "../game/constants.ts";

async function fetchLeaderboard(): Promise<AgentStat[]> {
  const res = await fetch("/api/leaderboard");
  if (!res.ok) throw new Error(`leaderboard request failed: ${res.status}`);
  return res.json();
}

export function useLeaderboard() {
  return useQuery({ queryKey: ["leaderboard"], queryFn: fetchLeaderboard, refetchInterval: POLL_MS });
}
EOF
eval_write components/game/leaderboard-card.tsx <<'EOF'
import { useLeaderboard } from "../../lib/hooks/use-leaderboard";

export function LeaderboardCard() {
  const { data: agents = [], isLoading } = useLeaderboard();
  if (isLoading) return <div className="h-64 animate-pulse rounded-lg bg-muted" />;

  const topAgents = agents.slice(0, 10);

  return (
    <section className="rounded-lg border p-4">
      <h2 className="mb-3 font-semibold">Leaderboard</h2>
      <ol className="space-y-1">
        {topAgents.map((agent, i) => (
          <li key={agent.agentId} className="flex justify-between">
            <span>
              {i + 1}. {agent.name}
            </span>
            <span className="tabular-nums">{agent.winRate.toFixed(3)}</span>
          </li>
        ))}
      </ol>
    </section>
  );
}
EOF
eval_write app/api/leaderboard/route.ts <<'EOF'
import { getTopAgents } from "../../../lib/db/queries.ts";

export function GET(): Response {
  return Response.json(getTopAgents());
}
EOF
eval_commit "feat: add leaderboard to game page"

L_QUERY="$(grep -n 'return rows.slice(0, limit);' lib/db/queries.ts | cut -d: -f1)"
L_TEN="$(grep -n 'agents.slice(0, 10)' components/game/leaderboard-card.tsx | cut -d: -f1)"
L_RATE="$(grep -n 'toFixed(3)' components/game/leaderboard-card.tsx | cut -d: -f1)"
L_POLL="$(grep -n 'refetchInterval: POLL_MS' lib/hooks/use-leaderboard.ts | cut -d: -f1)"
[ "$L_QUERY" = 45 ] && [ "$L_POLL" = 12 ] || { echo "scaffold: line numbers drifted ($L_QUERY, $L_POLL)" >&2; exit 1; }

eval_origin
eval_gh
eval_gh_fixtures < "$EVAL_LIB_DIR/gh_pr_fixtures.sh"
echo jlee | eval_gh_file me
eval_gh_file repo.json <<'JSON'
{"name": "agent-arena", "nameWithOwner": "acme/agent-arena", "owner": {"login": "acme"}, "url": "https://github.com/acme/agent-arena", "defaultBranchRef": {"name": "main"}, "description": "Agents play each other; humans watch the bracket."}
JSON
eval_gh_file pr-42.json <<'JSON'
{
  "number": 42,
  "title": "feat: add leaderboard to game page",
  "body": "## What\n\nAdds a leaderboard card to the game page: the top 10 agents by win rate, refreshed while a tournament runs.\n\n## Why\n\nSpectators can't tell who's winning without opening every agent's profile.\n\n## How\n\n`getTopAgents` in lib/db/queries.ts feeds `/api/leaderboard`; `useLeaderboard` polls it on the same interval as game state.\n\n## Test plan\n\n- [x] unit test for the limit\n- [ ] checked the card on a live tournament\n\nCloses PERDIX-140",
  "url": "https://github.com/acme/agent-arena/pull/42",
  "state": "OPEN",
  "isDraft": false,
  "author": {"login": "jlee"},
  "headRefName": "perdix-140-add-leaderboard",
  "baseRefName": "main",
  "reviewDecision": "CHANGES_REQUESTED",
  "mergeable": "MERGEABLE",
  "mergeStateStatus": "BLOCKED",
  "statusCheckRollup": [
    {"__typename": "CheckRun", "name": "typecheck", "status": "COMPLETED", "conclusion": "SUCCESS", "workflowName": "CI", "detailsUrl": "https://github.com/acme/agent-arena/actions/runs/1/job/1"},
    {"__typename": "CheckRun", "name": "lint", "status": "COMPLETED", "conclusion": "SUCCESS", "workflowName": "CI", "detailsUrl": "https://github.com/acme/agent-arena/actions/runs/1/job/2"},
    {"__typename": "CheckRun", "name": "test", "status": "COMPLETED", "conclusion": "SUCCESS", "workflowName": "CI", "detailsUrl": "https://github.com/acme/agent-arena/actions/runs/1/job/3"}
  ],
  "reviews": [
    {"author": {"login": "mira-chen"}, "state": "CHANGES_REQUESTED", "body": "Ordering bug in the query, plus a question on polling.", "submittedAt": "2026-11-02T16:10:00Z"},
    {"author": {"login": "jon-park"}, "state": "COMMENTED", "body": "", "submittedAt": "2026-11-02T17:02:00Z"}
  ],
  "comments": [],
  "labels": [],
  "closingIssuesReferences": [],
  "createdAt": "2026-11-02T14:00:00Z"
}
JSON
eval_gh_file threads-42.json <<JSON
[
  {"id": "PRRT_kwDOq1", "isResolved": false, "isOutdated": false, "path": "lib/db/queries.ts", "line": $L_QUERY,
   "comments": {"nodes": [{"id": "PRRC_kwDOq1", "databaseId": 1801, "author": {"login": "mira-chen"}, "createdAt": "2026-11-02T16:05:00Z",
     "body": "This returns rows in whatever order the store holds them, so the card shows the first ten agents ever inserted, not the top ten. Please sort by winRate descending before the limit."}]}},
  {"id": "PRRT_kwDOq2", "isResolved": false, "isOutdated": false, "path": "components/game/leaderboard-card.tsx", "line": $L_TEN,
   "comments": {"nodes": [{"id": "PRRC_kwDOq2", "databaseId": 1802, "author": {"login": "jon-park"}, "createdAt": "2026-11-02T16:58:00Z",
     "body": "nit: magic number 10 here and again as getTopAgents' default limit. Consider one constant so they can't drift."}]}},
  {"id": "PRRT_kwDOq3", "isResolved": false, "isOutdated": false, "path": "components/game/leaderboard-card.tsx", "line": $L_RATE,
   "comments": {"nodes": [{"id": "PRRC_kwDOq3", "databaseId": 1803, "author": {"login": "jon-park"}, "createdAt": "2026-11-02T17:00:00Z",
     "body": "Might be nicer to show this as a percentage (73%) rather than 0.734. Optional."}]}},
  {"id": "PRRT_kwDOq4", "isResolved": false, "isOutdated": false, "path": "lib/hooks/use-leaderboard.ts", "line": $L_POLL,
   "comments": {"nodes": [{"id": "PRRC_kwDOq4", "databaseId": 1804, "author": {"login": "mira-chen"}, "createdAt": "2026-11-02T16:07:00Z",
     "body": "Why refetch every 5 seconds? Seems aggressive for a leaderboard."}]}}
]
JSON
jq '[.[] | .comments.nodes[0] as $c | {id: $c.databaseId, node_id: $c.id, path, line, original_line: .line, body: $c.body, user: {login: $c.author.login}, created_at: $c.createdAt, in_reply_to_id: null}]' \
    .git/local/gh/threads-42.json | eval_gh_file review-comments-42.json
