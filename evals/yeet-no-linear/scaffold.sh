#!/usr/bin/env bash
# TypeScript game API with no bruhs config anywhere: CLAUDE.md exists but
# holds only hand-written notes (no bruhs:state block), there is no AGENTS.md
# and no .claude/bruhs.json, so read_bruhs_block.py prints nothing. On main,
# uncommitted work adds a leaderboard: a new ranking module and its test
# (untracked) and a new route in an existing file (unstaged). typecheck, lint
# and test pass. There are no Linear mocks: no Linear tools exist in the run.
# gh opens PRs for real (they need a pushed branch); every push, npm run and
# gh call is recorded in .git/local/ledger.md.
set -euo pipefail
CASE_DIR="$(cd "$(dirname "$0")" && pwd)"
. "$CASE_DIR/../_lib/helpers.sh"

eval_repo
eval_node_project game-api hono
eval_write CLAUDE.md <<'EOF'
# game-api

HTTP API for the card game. Hono on Node.

- Run `npm test` before pushing.
- Handlers live in src/game/routes.ts; keep game logic in pure modules next to it.
EOF
eval_write src/game/score.ts <<'EOF'
export type Player = { id: string; name: string; wins: number; losses: number };

/** Win rate in [0, 1]; a player with no games has a rate of 0. */
export function winRate(p: Player): number {
  const games = p.wins + p.losses;
  return games === 0 ? 0 : p.wins / games;
}
EOF
eval_write src/game/score.test.ts <<'EOF'
import { test } from "node:test";
import assert from "node:assert/strict";
import { winRate } from "./score.ts";

test("win rate is wins over games", () => {
  assert.equal(winRate({ id: "a", name: "a", wins: 3, losses: 1 }), 0.75);
  assert.equal(winRate({ id: "b", name: "b", wins: 0, losses: 0 }), 0);
});
EOF
eval_write src/game/routes.ts <<'EOF'
import type { Player } from "./score.ts";
import { winRate } from "./score.ts";

export type Route = { method: "GET"; path: string; handle: (players: Player[]) => unknown };

export const routes: Route[] = [
  {
    method: "GET",
    path: "/game/players/:id/stats",
    handle: (players) => players.map((p) => ({ id: p.id, winRate: winRate(p) })),
  },
];
EOF
eval_commit "feat(game): player stats endpoint"
eval_origin

# The work to ship: a leaderboard for the game page.
eval_write src/game/leaderboard.ts <<'EOF'
import type { Player } from "./score.ts";
import { winRate } from "./score.ts";

export type LeaderboardRow = { rank: number; id: string; name: string; winRate: number; games: number };

/**
 * Players ranked by win rate, highest first. Ties go to the player with more
 * wins. Players with fewer than `minGames` games are left off so one lucky
 * win doesn't top the board.
 */
export function rankPlayers(players: readonly Player[], minGames = 5): LeaderboardRow[] {
  return players
    .filter((p) => p.wins + p.losses >= minGames)
    .toSorted((a, b) => winRate(b) - winRate(a) || b.wins - a.wins)
    .map((p, i) => ({ rank: i + 1, id: p.id, name: p.name, winRate: winRate(p), games: p.wins + p.losses }));
}
EOF
eval_write src/game/leaderboard.test.ts <<'EOF'
import { test } from "node:test";
import assert from "node:assert/strict";
import { rankPlayers } from "./leaderboard.ts";

const p = (id: string, wins: number, losses: number) => ({ id, name: id, wins, losses });

test("ranks by win rate, highest first", () => {
  const rows = rankPlayers([p("low", 2, 8), p("high", 8, 2), p("mid", 5, 5)]);
  assert.deepEqual(rows.map((r) => r.id), ["high", "mid", "low"]);
  assert.deepEqual(rows.map((r) => r.rank), [1, 2, 3]);
});

test("breaks win-rate ties by wins", () => {
  const rows = rankPlayers([p("few", 3, 3), p("many", 6, 6)]);
  assert.deepEqual(rows.map((r) => r.id), ["many", "few"]);
});

test("leaves off players under the minimum games", () => {
  assert.deepEqual(rankPlayers([p("new", 1, 0), p("vet", 6, 4)]).map((r) => r.id), ["vet"]);
});
EOF
eval_write src/game/routes.ts <<'EOF'
import { rankPlayers } from "./leaderboard.ts";
import type { Player } from "./score.ts";
import { winRate } from "./score.ts";

export type Route = { method: "GET"; path: string; handle: (players: Player[]) => unknown };

export const routes: Route[] = [
  {
    method: "GET",
    path: "/game/players/:id/stats",
    handle: (players) => players.map((p) => ({ id: p.id, winRate: winRate(p) })),
  },
  {
    method: "GET",
    path: "/game/leaderboard",
    handle: (players) => rankPlayers(players),
  },
];
EOF
eval_gh
cp "$EVAL_LIB_DIR/gh_world.py" .git/local/gh_world.py
python3 .git/local/gh_world.py install <<'JSON'
{ "repo": "perdixlabs/game-api", "next_pr": 42 }
JSON
