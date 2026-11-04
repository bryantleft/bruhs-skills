#!/usr/bin/env bash
# A TypeScript Hono API (zod validation, vitest, Biome) with no bruhs config.
# The user's ~/.claude.json lists MCP servers, but none for Linear (only
# notion and context7), and no other agent config lists one either, so
# claim must take the "No Linear MCP" path. No Linear mocks exist in this case.
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
    servers[name] = {"type": "stdio", "command": "npx", "args": ["-y", packages[name]]}
path.write_text(json.dumps(data, indent=2) + "\n")
PY
}

eval_repo
eval_node_project payments-api hono @hono/node-server @hono/zod-validator zod vitest
eval_write biome.json <<'EOF'
{
  "$schema": "https://biomejs.dev/schemas/1.9.4/schema.json",
  "linter": { "enabled": true, "rules": { "recommended": true } },
  "formatter": { "enabled": true, "indentStyle": "space" }
}
EOF
eval_write vitest.config.ts <<'EOF'
import { defineConfig } from "vitest/config";

export default defineConfig({ test: { include: ["src/**/*.test.ts"] } });
EOF
eval_write tsconfig.json <<'EOF'
{ "compilerOptions": { "strict": true, "module": "ESNext", "moduleResolution": "Bundler", "target": "ES2022" } }
EOF
eval_write src/index.ts <<'EOF'
import { serve } from "@hono/node-server";
import { zValidator } from "@hono/zod-validator";
import { Hono } from "hono";
import { z } from "zod";

const app = new Hono();

const Charge = z.object({ amountCents: z.number().int().positive(), currency: z.string().length(3) });

app.get("/health", (c) => c.json({ ok: true }));
app.post("/charges", zValidator("json", Charge), (c) => c.json({ id: "ch_1", ...c.req.valid("json") }, 201));

serve({ fetch: app.fetch, port: 8787 });
EOF
eval_write Dockerfile <<'EOF'
FROM node:22-slim
WORKDIR /app
COPY . .
CMD ["node", "src/index.ts"]
EOF
eval_commit "feat: payments api with charge endpoint"
user_mcp_servers notion context7
