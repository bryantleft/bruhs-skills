#!/usr/bin/env bash
# Leaderboard game app on main, up to date with origin, with a clean working
# tree: nothing staged, unstaged or untracked. Ignored build output (dist/)
# and a local .env sit on disk so a listing isn't empty, but git status shows
# nothing to ship. bruhs:state points Linear at linear-perdix. gh answers PR
# calls (there are none) and every push and gh call is recorded in
# .git/local/ledger.md.
set -euo pipefail
CASE_DIR="$(cd "$(dirname "$0")" && pwd)"
. "$CASE_DIR/../_lib/helpers.sh"

eval_repo
eval_node_project game-app next react react-dom
eval_state <<'JSON'
{
  "stack": {"structure": "single", "framework": "Next.js", "styling": [], "database": [], "testing": ["node:test"], "tooling": []},
  "tooling": {"mcps": ["linear"], "skills": []},
  "integrations": {"linear": {"mcpServer": "linear-perdix", "team": "PERDIX", "teamName": "Perdix", "project": "core", "projectName": "Core",
    "labels": {"feat": "Feature", "fix": "Bug", "chore": "Chore", "refactor": "Improvement"}}}
}
JSON
eval_write src/game/score.ts <<'EOF'
export type Player = { name: string; wins: number; losses: number };

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
  assert.equal(winRate({ name: "a", wins: 3, losses: 1 }), 0.75);
  assert.equal(winRate({ name: "b", wins: 0, losses: 0 }), 0);
});
EOF
printf 'dist/\n.env\n' >> .gitignore
eval_commit "feat(game): compute player win rates"
mkdir -p dist
echo "// build output" > dist/score.js
echo "NEXT_PUBLIC_API_URL=http://localhost:3000" > .env
eval_origin
eval_gh
cp "$EVAL_LIB_DIR/gh_world.py" .git/local/gh_world.py
python3 .git/local/gh_world.py install <<'JSON'
{ "repo": "perdixlabs/gambit", "next_pr": 47 }
JSON
