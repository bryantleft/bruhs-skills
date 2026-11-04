#!/usr/bin/env bash
# A claimed Next.js app (bruhs:state in CLAUDE.md and AGENTS.md, Linear on
# linear-perdix) on main, mid-feature: three tracked files have uncommitted,
# unstaged edits adding a feet/metres unit toggle. No feature branch, no
# stash, no Linear ticket for the work. /bruhs with no arguments should show
# the menu and leave the working tree exactly as it is.
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

# Work in progress, not staged: a feet/metres toggle across three files.
eval_write src/lib/tides.ts <<'EOF'
// Rough semidiurnal tide model: height at hour h, in metres or feet.
export type Unit = "m" | "ft";

const FEET_PER_METRE = 3.28084;

export function tideHeight(h: number, unit: Unit = "m"): number {
  const metres = 1.5 + 1.2 * Math.cos((2 * Math.PI * h) / 12.42);
  return unit === "ft" ? metres * FEET_PER_METRE : metres;
}
EOF
eval_write src/app/page.tsx <<'EOF'
import { tideHeight, type Unit } from "../lib/tides";

export default function Home({ searchParams }: { searchParams: { unit?: Unit } }) {
  const unit = searchParams.unit ?? "m";
  // TODO: toggle button
  return <main className="p-8">High tide: {tideHeight(6, unit).toFixed(1)} {unit}</main>;
}
EOF
eval_write src/lib/tides.test.ts <<'EOF'
import { test } from "node:test";
import assert from "node:assert/strict";
import { tideHeight } from "./tides.ts";

test("high tide at hour 0", () => {
  assert.ok(Math.abs(tideHeight(0) - 2.7) < 1e-9);
});

test("feet", () => {
  assert.ok(Math.abs(tideHeight(0, "ft") - 2.7 * 3.28084) < 1e-9);
});
EOF
