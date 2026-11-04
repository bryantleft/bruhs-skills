#!/usr/bin/env bash
# A project that moved from Astro + Convex to Next.js + Drizzle, still
# carrying the year-old legacy .claude/bruhs.json that describes the old
# stack (framework astro, database convex, styling Tailwind). No bruhs:state
# block and no AGENTS.md. The code now has next.config.ts, drizzle.config.ts
# and tailwind.config.ts, and no astro.config.* or convex/. The user's
# ~/.claude.json lists linear-sonner.
set -euo pipefail
. "$(cd "$(dirname "$0")" && pwd)/../_lib/helpers.sh"

# Servers the user has configured, in the run's own temp HOME only (never a
# real user's home: the same guard helpers.sh uses for shell rc files).
user_mcp_servers() {
    if [ "$(pwd -P)" != "$(cd "$HOME/cwd" 2>/dev/null && pwd -P || true)" ]; then
        echo "scaffold: not under claude plugin eval; ~/.claude.json left alone (would list: $*)" >&2
        return 0
    fi
    python3 - "$HOME/.claude.json" "$@" <<'PY'
import json, sys
from pathlib import Path
path = Path(sys.argv[1])
data = json.loads(path.read_text()) if path.is_file() else {}
servers = data.setdefault("mcpServers", {})
for name in sys.argv[2:]:
    servers[name] = {"type": "stdio", "command": "npx", "args": ["-y", "mcp-server-linear"],
                     "env": {"LINEAR_ACCESS_TOKEN": "lin_api_" + name.split("-", 1)[1]}}
path.write_text(json.dumps(data, indent=2) + "\n")
PY
}

eval_repo
eval_write .claude/bruhs.json <<'EOF'
{
  "integrations": {
    "linear": {
      "mcpServer": "linear-sonner",
      "team": "2e557b80-0000-4000-8000-000000000000",
      "teamName": "Son",
      "project": "2e557b80-0000-4000-a000-000000000001",
      "projectName": "Core"
    }
  },
  "tooling": {"mcps": ["linear"], "skills": ["superpowers"]},
  "stack": {
    "structure": "single",
    "framework": "astro",
    "styling": ["Tailwind CSS"],
    "database": ["convex"],
    "testing": [],
    "tooling": []
  }
}
EOF
eval_write astro.config.mjs <<'EOF'
import { defineConfig } from "astro/config";
export default defineConfig({});
EOF
eval_write convex/schema.ts <<'EOF'
import { defineSchema } from "convex/server";
export default defineSchema({});
EOF
eval_write package.json <<'EOF'
{ "name": "sonner-site", "private": true, "dependencies": { "astro": "*", "convex": "*", "tailwindcss": "*" } }
EOF
eval_commit "feat: sonner site on astro + convex"

# A year later: the move to Next.js + Drizzle.
git rm -q -r astro.config.mjs convex package.json
eval_node_project sonner-site next react react-dom drizzle-orm postgres tailwindcss
eval_write next.config.ts <<'EOF'
import type { NextConfig } from "next";

export default {} satisfies NextConfig;
EOF
eval_write tailwind.config.ts <<'EOF'
export default { content: ["./src/**/*.{ts,tsx}"] };
EOF
eval_write drizzle.config.ts <<'EOF'
import { defineConfig } from "drizzle-kit";

export default defineConfig({ schema: "./src/db/schema.ts", dialect: "postgresql" });
EOF
eval_write src/db/schema.ts <<'EOF'
import { pgTable, text } from "drizzle-orm/pg-core";

export const docs = pgTable("docs", { slug: text("slug").primaryKey(), body: text("body").notNull() });
EOF
eval_write src/app/page.tsx <<'EOF'
export default function Home() {
  return <main className="p-8">Sonner</main>;
}
EOF
eval_write CHANGELOG.md <<'EOF'
# Changelog

## 2.0.0

- Moved the site from Astro to Next.js (App Router).
- Replaced Convex with Drizzle + Postgres.
EOF
eval_commit "feat!: move site from astro + convex to next.js + drizzle"
user_mcp_servers linear-sonner
