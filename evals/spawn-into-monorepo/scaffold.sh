#!/usr/bin/env bash
# The Turborepo + pnpm monorepo "gambit": apps/web (Next.js, Tailwind,
# Drizzle, Better Auth) and packages/ui. bruhs already claimed it: the
# bruhs:state block (CLAUDE.md + AGENTS.md) is the monorepo form
# (stack.frameworks array) with Linear on linear-perdix (team PERDIX,
# project Core). The landmine: pnpm-workspace.yaml lists apps/web by
# name instead of apps/*, so a new apps/api is not part of the workspace
# until the file is extended. ~/.claude.json lists linear-perdix. No
# network, so `pnpm create hono` cannot succeed here.
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
eval_write package.json <<'EOF'
{
  "name": "gambit",
  "private": true,
  "packageManager": "pnpm@9.15.0",
  "scripts": {
    "build": "turbo run build",
    "dev": "turbo run dev",
    "lint": "turbo run lint",
    "typecheck": "turbo run typecheck",
    "test": "turbo run test"
  },
  "devDependencies": { "turbo": "^2.3.0", "@biomejs/biome": "^1.9.4" }
}
EOF
eval_write turbo.json <<'EOF'
{
  "$schema": "https://turbo.build/schema.json",
  "tasks": {
    "build": { "dependsOn": ["^build"], "outputs": [".next/**", "!.next/cache/**", "dist/**"] },
    "dev": { "cache": false, "persistent": true },
    "lint": {},
    "typecheck": { "dependsOn": ["^typecheck"] },
    "test": {}
  }
}
EOF
eval_write pnpm-workspace.yaml <<'EOF'
packages:
  - "apps/web"
  - "packages/*"
EOF
eval_write biome.json <<'EOF'
{ "$schema": "https://biomejs.dev/schemas/1.9.4/schema.json", "linter": { "enabled": true, "rules": { "recommended": true } } }
EOF
eval_write .gitignore <<'EOF'
node_modules/
.next/
.turbo/
dist/
EOF
eval_write apps/web/package.json <<'EOF'
{
  "name": "@gambit/web",
  "private": true,
  "scripts": { "dev": "next dev", "build": "next build", "lint": "biome check .", "typecheck": "tsc --noEmit" },
  "dependencies": {
    "@gambit/ui": "workspace:*",
    "better-auth": "^1.2.0",
    "drizzle-orm": "^0.38.0",
    "next": "^15.1.0",
    "react": "^19.0.0",
    "react-dom": "^19.0.0",
    "zod": "^3.24.0"
  },
  "devDependencies": { "tailwindcss": "^4.0.0", "typescript": "^5.7.0" }
}
EOF
eval_write apps/web/next.config.ts <<'EOF'
import type { NextConfig } from "next";

export default { transpilePackages: ["@gambit/ui"] } satisfies NextConfig;
EOF
eval_write apps/web/src/app/page.tsx <<'EOF'
import { Button } from "@gambit/ui/button";

export default function Home() {
  return <main className="p-8"><Button>Play</Button></main>;
}
EOF
eval_write packages/ui/package.json <<'EOF'
{ "name": "@gambit/ui", "private": true, "exports": { "./button": "./src/button.tsx" }, "dependencies": { "react": "^19.0.0" } }
EOF
eval_write packages/ui/src/button.tsx <<'EOF'
import type { ButtonHTMLAttributes } from "react";

export function Button(props: ButtonHTMLAttributes<HTMLButtonElement>) {
  return <button className="rounded-md px-4 py-2" {...props} />;
}
EOF
eval_write CLAUDE.md <<'EOF'
# Gambit

Chess openings trainer. Turborepo + pnpm; run everything from the root.
EOF
eval_state <<'JSON'
{
  "integrations": {
    "linear": {
      "mcpServer": "linear-perdix",
      "team": "9ffd07ac-0000-4000-8000-000000000000",
      "teamName": "Perdix",
      "project": "9ffd07ac-0000-4000-a000-000000000001",
      "projectName": "Core",
      "labels": {"feat": "Feature", "fix": "Bug", "chore": "Chore", "refactor": "Improvement"}
    }
  },
  "tooling": {"mcps": ["linear"], "skills": ["superpowers", "feature-dev", "commit-commands", "vercel-react-best-practices", "better-auth-best-practices"]},
  "stack": {
    "structure": "monorepo",
    "frameworks": ["Next.js"],
    "styling": ["Tailwind CSS"],
    "database": ["drizzle-postgres"],
    "auth": "better-auth",
    "libraries": ["zod"],
    "testing": [],
    "tooling": ["Turborepo", "biome"]
  }
}
JSON
eval_commit "feat: gambit monorepo with web app and ui package"
user_mcp_servers linear-perdix
