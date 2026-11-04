#!/usr/bin/env bash
# An empty directory (git repo with only an empty root commit: no
# package.json, turbo.json or pnpm-workspace.yaml) where the user wants a new
# standalone Next.js project, my-app. The user's ~/.claude.json lists one
# Linear workspace, linear-bnle (team BNLE). A run has no network, so
# `pnpm create next-app` cannot succeed here.
# mocks: "mcpServer": "linear-bnle"
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
user_mcp_servers linear-bnle
