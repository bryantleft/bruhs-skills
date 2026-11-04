#!/usr/bin/env bash
# TypeScript (Next.js) app that has never been claimed: CLAUDE.md exists with
# hand-written notes but no bruhs:state block, there is no AGENTS.md and no
# legacy .claude/bruhs.json, so read_bruhs_block.py prints nothing. No Linear
# server is configured or mocked.
set -euo pipefail
. "$(cd "$(dirname "$0")" && pwd)/../_lib/helpers.sh"

eval_repo
eval_node_project profile-app next react react-dom

eval_write CLAUDE.md <<'EOF'
# profile-app

- Server Components by default; add "use client" only for interactivity.
- User data comes from src/lib/users.ts; don't query the API from components.
EOF

eval_write src/lib/users.ts <<'EOF'
export type User = { readonly id: string; readonly name: string; readonly email: string; readonly joinedAt: Date };

const users: readonly User[] = [
  { id: "u_1", name: "Ada Lovelace", email: "ada@example.com", joinedAt: new Date("2025-01-10") },
];

export async function getUser(id: string): Promise<User | undefined> {
  return users.find((u) => u.id === id);
}
EOF

eval_write src/app/page.tsx <<'EOF'
export default function Home() {
  return <main className="p-6">Welcome</main>;
}
EOF

eval_commit "feat: home page and user lookup"
eval_origin
eval_gh
