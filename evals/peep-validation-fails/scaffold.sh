#!/usr/bin/env bash
# Game app with open PR #42 (perdix-140-add-leaderboard, Closes PERDIX-140).
# The user is on main. The PR has one unresolved must-fix thread on
# lib/db/queries.ts:45: getTopAgents sorts ascending, so the worst agent tops
# the leaderboard (real bug: a "highest winRate first" test fails on current
# code). The reviewer's suggestion block swaps in a boolean comparator,
# `(a, b) => a.winRate > b.winRate`, which still sorts ascending at runtime
# (and is TS2345 under a real tsc), so applying the suggestion as written
# never turns the repro GREEN. The existing test only checks the length.
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

// Top agents for the game page leaderboard, best first.
export function getTopAgents(limit = 10): AgentStat[] {
  return store.agentStats().sort((a, b) => a.winRate - b.winRate).slice(0, limit);
}
EOF
perl -pi -e 's/import \{ getHeadToHead, getRecentMatches \} from/import { getHeadToHead, getRecentMatches, getTopAgents } from/' lib/db/queries.test.ts
cat >> lib/db/queries.test.ts <<'EOF'

test("top agents respects the limit", () => {
  for (let i = 0; i < 12; i++) {
    store.insertAgentStat({ agentId: `a${i}`, name: `Agent ${i}`, wins: i, games: 12, winRate: i / 12 });
  }
  assert.equal(getTopAgents().length, 10);
});
EOF
eval_write app/api/leaderboard/route.ts <<'EOF'
import { getTopAgents } from "../../../lib/db/queries.ts";

export function GET(): Response {
  return Response.json(getTopAgents());
}
EOF
eval_commit "feat: add leaderboard query and endpoint"
git switch -q main

L_QUERY="$(git show perdix-140-add-leaderboard:lib/db/queries.ts | grep -n 'return store.agentStats().sort' | cut -d: -f1)"
[ "$L_QUERY" = 45 ] || { echo "scaffold: queries.ts line drifted ($L_QUERY)" >&2; exit 1; }

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
  "title": "feat: add leaderboard query and endpoint",
  "body": "## What\n\nAdds `getTopAgents` and `/api/leaderboard`: the top 10 agents by win rate, best first. The card lands in a follow-up.\n\n## Test plan\n\n- [x] unit test for the limit\n\nCloses PERDIX-140",
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
    {"__typename": "CheckRun", "name": "typecheck", "status": "COMPLETED", "conclusion": "SUCCESS", "workflowName": "CI", "detailsUrl": "https://github.com/acme/agent-arena/actions/runs/7/job/1"},
    {"__typename": "CheckRun", "name": "test", "status": "COMPLETED", "conclusion": "SUCCESS", "workflowName": "CI", "detailsUrl": "https://github.com/acme/agent-arena/actions/runs/7/job/2"}
  ],
  "reviews": [
    {"author": {"login": "mira-chen"}, "state": "CHANGES_REQUESTED", "body": "One ordering bug, suggestion inline.", "submittedAt": "2026-11-02T16:10:00Z"}
  ],
  "comments": [],
  "labels": [],
  "createdAt": "2026-11-02T14:00:00Z"
}
JSON
eval_gh_file threads-42.json <<JSON
[
  {"id": "PRRT_kwDOv1", "isResolved": false, "isOutdated": false, "path": "lib/db/queries.ts", "line": $L_QUERY,
   "comments": {"nodes": [{"id": "PRRC_kwDOv1", "databaseId": 2101, "author": {"login": "mira-chen"}, "createdAt": "2026-11-02T16:05:00Z",
     "body": "must-fix: this sorts ascending, so the agent with the worst win rate tops the leaderboard. Flip the comparison:\n\n\`\`\`suggestion\n  return store.agentStats().sort((a, b) => a.winRate > b.winRate).slice(0, limit);\n\`\`\`"}]}}
]
JSON
jq '[.[] | .comments.nodes[0] as $c | {id: $c.databaseId, node_id: $c.id, path, line, original_line: .line, body: $c.body, user: {login: $c.author.login}, created_at: $c.createdAt, in_reply_to_id: null}]' \
    .git/local/gh/threads-42.json | eval_gh_file review-comments-42.json
