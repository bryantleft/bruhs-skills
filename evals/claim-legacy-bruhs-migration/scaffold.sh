#!/usr/bin/env bash
# A Next.js + Tailwind + shadcn app configured by an old bruhs: its state
# lives only in a legacy .claude/bruhs.json (linear-sonner, team SON,
# project "Core", state "zustand"). CLAUDE.md is hand-written (product
# vision, commands, rules) with no bruhs:state or bruhs:rules block, and
# there is no AGENTS.md. The legacy file holds things re-detection can't
# recover: the Linear ids, a custom "refactor" label, and stack.state
# "zustand" (not in package.json yet), so a run that re-detects instead of
# migrating loses them.
set -euo pipefail
. "$(cd "$(dirname "$0")" && pwd)/../_lib/helpers.sh"

eval_repo
eval_node_project sonner-web next react react-dom tailwindcss @radix-ui/react-slot clsx tailwind-merge
eval_write next.config.ts <<'EOF'
import type { NextConfig } from "next";

export default {} satisfies NextConfig;
EOF
eval_write tailwind.config.ts <<'EOF'
export default { content: ["./src/**/*.{ts,tsx}"] };
EOF
eval_write src/components/ui/button.tsx <<'EOF'
import type { ButtonHTMLAttributes } from "react";

export function Button(props: ButtonHTMLAttributes<HTMLButtonElement>) {
  return <button className="rounded-md px-4 py-2" {...props} />;
}
EOF
eval_write CLAUDE.md <<'EOF'
# Sonner Web

## Product vision

Sonner is a toast library people actually enjoy. This site is its docs and
playground: every example must be copy-pasteable and run as shown.

## Commands

- `pnpm dev` — docs site on :3000
- `pnpm test` — unit tests

## Rules

- Never ship an example that isn't exercised by a test.
- Toast durations are in milliseconds everywhere; never mix in seconds.
EOF
eval_write .claude/bruhs.json <<'EOF'
{
  "integrations": {
    "linear": {
      "mcpServer": "linear-sonner",
      "team": "2e557b80-0000-4000-8000-000000000000",
      "teamName": "Son",
      "project": "2e557b80-0000-4000-a000-000000000001",
      "projectName": "Core",
      "labels": { "feat": "Feature", "fix": "Bug", "chore": "Chore", "refactor": "Polish" }
    }
  },
  "tooling": {
    "mcps": ["linear"],
    "skills": ["superpowers", "shadcn"]
  },
  "stack": {
    "structure": "single",
    "framework": "nextjs",
    "styling": ["Tailwind CSS", "shadcn/ui"],
    "database": [],
    "state": "zustand",
    "testing": ["vitest"],
    "tooling": []
  }
}
EOF
eval_commit "feat: docs site"
