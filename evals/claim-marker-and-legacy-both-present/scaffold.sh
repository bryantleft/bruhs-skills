#!/usr/bin/env bash
# Hybrid state: CLAUDE.md and AGENTS.md hold a current bruhs:state block
# (Next.js, linear-perdix, team PERDIX), and a stale legacy
# .claude/bruhs.json from an older install is still on disk, disagreeing
# with it everywhere (Astro, linear-sonner, team SON). The marker block is
# the source of truth; the legacy file is dormant.
set -euo pipefail
. "$(cd "$(dirname "$0")" && pwd)/../_lib/helpers.sh"

eval_repo
eval_node_project gambit next react react-dom tailwindcss
eval_write next.config.ts <<'EOF'
import type { NextConfig } from "next";

export default {} satisfies NextConfig;
EOF
eval_write tailwind.config.ts <<'EOF'
export default { content: ["./src/**/*.{ts,tsx}"] };
EOF
eval_write src/app/page.tsx <<'EOF'
export default function Home() {
  return <main className="p-8">Gambit</main>;
}
EOF
eval_write CLAUDE.md <<'EOF'
# Gambit

Chess openings trainer.
EOF
eval_state <<'JSON'
{
  "integrations": {
    "linear": {
      "mcpServer": "linear-perdix",
      "team": "9ffd07ac-0000-4000-8000-000000000000",
      "teamName": "Perdix",
      "project": "9ffd07ac-0000-4000-a000-000000000001",
      "projectName": "Core"
    }
  },
  "tooling": {"mcps": ["linear"], "skills": ["superpowers", "feature-dev", "commit-commands", "vercel-react-best-practices"]},
  "stack": {"structure": "single", "framework": "nextjs", "styling": ["Tailwind CSS"], "database": [], "testing": [], "tooling": []}
}
JSON
eval_commit "feat: gambit on next.js, claimed by bruhs"
# Left behind by an older bruhs and never cleaned up (the project was on
# Astro and the Sonner workspace back then).
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
  "stack": {"structure": "single", "framework": "astro", "styling": ["Tailwind CSS"], "database": ["convex"], "testing": [], "tooling": []}
}
EOF
eval_commit "chore: old bruhs config"
