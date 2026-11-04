#!/usr/bin/env bash
# A single-package Next.js app (Tailwind, shadcn/ui components, Drizzle,
# Biome) that bruhs has never seen: no bruhs:state block, no
# .claude/bruhs.json, no turbo.json or pnpm-workspace.yaml. The user's
# Claude Code config (~/.claude.json) lists one Linear workspace server,
# linear-perdix, plus context7.
# mocks: "mcpServer": "linear-perdix"
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
packages = {"notion": "@notionhq/notion-mcp-server", "context7": "@upstash/context7-mcp"}
for name in sys.argv[2:]:
    if name.startswith("linear-"):
        servers[name] = {"type": "stdio", "command": "npx", "args": ["-y", "mcp-server-linear"],
                         "env": {"LINEAR_ACCESS_TOKEN": "lin_api_" + name.split("-", 1)[1]}}
    else:
        servers[name] = {"type": "stdio", "command": "npx", "args": ["-y", packages[name]]}
path.write_text(json.dumps(data, indent=2) + "\n")
PY
}

eval_repo
eval_node_project gambit next react react-dom drizzle-orm postgres tailwindcss \
    @radix-ui/react-slot class-variance-authority clsx tailwind-merge
eval_write next.config.ts <<'EOF'
import type { NextConfig } from "next";

const nextConfig: NextConfig = {};

export default nextConfig;
EOF
eval_write tailwind.config.ts <<'EOF'
import type { Config } from "tailwindcss";

export default {
  content: ["./src/**/*.{ts,tsx}", "./components/**/*.{ts,tsx}"],
  theme: { extend: {} },
} satisfies Config;
EOF
eval_write drizzle.config.ts <<'EOF'
import { defineConfig } from "drizzle-kit";

export default defineConfig({
  schema: "./src/db/schema.ts",
  dialect: "postgresql",
  dbCredentials: { url: process.env.DATABASE_URL ?? "" },
});
EOF
eval_write biome.json <<'EOF'
{
  "$schema": "https://biomejs.dev/schemas/1.9.4/schema.json",
  "linter": { "enabled": true, "rules": { "recommended": true } },
  "formatter": { "enabled": true, "indentStyle": "space", "indentWidth": 2 }
}
EOF
eval_write components.json <<'EOF'
{
  "style": "new-york",
  "tailwind": { "config": "tailwind.config.ts", "css": "src/app/globals.css", "cssVariables": true },
  "aliases": { "components": "@/components", "ui": "@/components/ui", "utils": "@/lib/utils" }
}
EOF
eval_write components/ui/button.tsx <<'EOF'
import { Slot } from "@radix-ui/react-slot";
import type { ButtonHTMLAttributes } from "react";
import { cn } from "@/lib/utils";

type ButtonProps = ButtonHTMLAttributes<HTMLButtonElement> & { asChild?: boolean };

export function Button({ asChild, className, ...props }: ButtonProps) {
  const Comp = asChild ? Slot : "button";
  return <Comp className={cn("rounded-md px-4 py-2 text-sm font-medium", className)} {...props} />;
}
EOF
eval_write lib/utils.ts <<'EOF'
import { clsx, type ClassValue } from "clsx";
import { twMerge } from "tailwind-merge";

export function cn(...inputs: ClassValue[]) {
  return twMerge(clsx(inputs));
}
EOF
eval_write src/app/page.tsx <<'EOF'
import { Button } from "@/components/ui/button";

export default function Home() {
  return (
    <main className="p-8">
      <h1 className="text-2xl font-semibold">Gambit</h1>
      <Button>New game</Button>
    </main>
  );
}
EOF
eval_write src/db/schema.ts <<'EOF'
import { pgTable, text, timestamp } from "drizzle-orm/pg-core";

export const games = pgTable("games", {
  id: text("id").primaryKey(),
  createdAt: timestamp("created_at").notNull().defaultNow(),
});
EOF
eval_write README.md <<'EOF'
# Gambit

Chess openings trainer. `npm run dev` to start.
EOF
eval_commit "feat: gambit app skeleton"
user_mcp_servers linear-perdix context7
