#!/usr/bin/env bash
# A claimed Next.js app (bruhs:state in CLAUDE.md and AGENTS.md, Linear on
# linear-perdix) on a clean main branch. The user types /bruhs foo, and foo
# is not a bruhs command; nothing in the repo is called foo either. The
# Linear mocks exist so a premature Linear call would show up.
set -euo pipefail
. "$(cd "$(dirname "$0")" && pwd)/../_lib/helpers.sh"

eval_repo
eval_node_project tidepool next react react-dom tailwindcss
eval_state <<'JSON'
{
  "stack": {"structure": "single", "framework": "nextjs", "styling": ["Tailwind CSS"], "database": [], "testing": ["node:test"], "tooling": []},
  "tooling": {"mcps": ["linear"], "skills": ["superpowers", "feature-dev", "commit-commands", "vercel-react-best-practices"]},
  "integrations": {"linear": {"mcpServer": "linear-perdix", "team": "9ffd07ac-0000-4000-8000-000000000000", "teamName": "Perdix", "project": "9ffd07ac-0000-4000-a000-000000000001", "projectName": "Core"}}
}
JSON
eval_write next.config.ts <<'EOF'
import type { NextConfig } from "next";

export default {} satisfies NextConfig;
EOF
eval_write src/app/page.tsx <<'EOF'
import { tideHeight } from "../lib/tides";

export default function Home() {
  return <main className="p-8">High tide: {tideHeight(6).toFixed(1)} m</main>;
}
EOF
eval_write src/lib/tides.ts <<'EOF'
// Rough semidiurnal tide model: height in metres at hour h.
export function tideHeight(h: number): number {
  return 1.5 + 1.2 * Math.cos((2 * Math.PI * h) / 12.42);
}
EOF
eval_write src/lib/tides.test.ts <<'EOF'
import { test } from "node:test";
import assert from "node:assert/strict";
import { tideHeight } from "./tides.ts";

test("high tide at hour 0", () => {
  assert.ok(Math.abs(tideHeight(0) - 2.7) < 1e-9);
});
EOF
eval_commit "feat: tide chart home page"
eval_origin
