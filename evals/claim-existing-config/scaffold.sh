#!/usr/bin/env bash
# A Next.js + Drizzle app that bruhs already claimed: CLAUDE.md and AGENTS.md
# hold a bruhs:state block wired to linear-sonner (team SON, project Eval
# App), plus fields the user added by hand (stack.libraries, a custom
# "refactor" label). Since then the user added Convex (convex/ and the convex
# dependency), which the state block doesn't know about yet: the reason they
# are running claim again.
set -euo pipefail
. "$(cd "$(dirname "$0")" && pwd)/../_lib/helpers.sh"

eval_repo
eval_node_project leaderboard next react react-dom drizzle-orm postgres tailwindcss zod effect
eval_write next.config.ts <<'EOF'
import type { NextConfig } from "next";

export default {} satisfies NextConfig;
EOF
eval_write drizzle.config.ts <<'EOF'
import { defineConfig } from "drizzle-kit";

export default defineConfig({ schema: "./src/db/schema.ts", dialect: "postgresql" });
EOF
eval_write src/db/schema.ts <<'EOF'
import { integer, pgTable, text } from "drizzle-orm/pg-core";

export const scores = pgTable("scores", {
  player: text("player").primaryKey(),
  points: integer("points").notNull().default(0),
});
EOF
eval_write CLAUDE.md <<'EOF'
# Leaderboard

Weekly leaderboard for the Sonner community.

## House rules

- Scores are integers; never store them as floats.
- Keep server actions in src/app/actions/.
EOF
eval_state <<'JSON'
{
  "integrations": {
    "linear": {
      "mcpServer": "linear-sonner",
      "team": "2e557b80-0000-4000-8000-000000000000",
      "teamName": "Son",
      "project": "2e557b80-0000-4000-a000-000000000001",
      "projectName": "Core",
      "labels": {"feat": "Feature", "fix": "Bug", "chore": "Chore", "refactor": "Tech Debt"}
    }
  },
  "tooling": {"mcps": ["linear"], "skills": ["superpowers", "feature-dev", "commit-commands", "vercel-react-best-practices"]},
  "stack": {
    "structure": "single",
    "framework": "nextjs",
    "styling": ["Tailwind CSS"],
    "database": ["drizzle-postgres"],
    "libraries": ["zod", "effect"],
    "testing": [],
    "tooling": []
  }
}
JSON
eval_commit "feat: leaderboard on drizzle, claimed by bruhs"

# The new piece: Convex for live score updates.
node_add_convex() {
    python3 - <<'PY'
import json
from pathlib import Path
p = Path("package.json")
pkg = json.loads(p.read_text())
pkg["dependencies"]["convex"] = "*"
p.write_text(json.dumps(pkg, indent=2) + "\n")
PY
}
node_add_convex
eval_write convex/scores.ts <<'EOF'
import { query } from "./_generated/server";

export const top = query({
  handler: async (ctx) => ctx.db.query("scores").order("desc").take(10),
});
EOF
eval_write convex/schema.ts <<'EOF'
import { defineSchema, defineTable } from "convex/server";
import { v } from "convex/values";

export default defineSchema({
  scores: defineTable({ player: v.string(), points: v.number() }),
});
EOF
eval_commit "feat: live scores with convex"
