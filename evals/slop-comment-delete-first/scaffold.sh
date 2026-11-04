#!/usr/bin/env bash
# Deploy CLI (scripts/deploy.ts) with a four-line comment above
# `await ensureSession(); await confirmEnvironment(env);` explaining the
# order. The names and order already say it, confirmEnvironment() throws a
# clear error if there is no session (so a reorder fails loudly), and the
# commit that introduced the order carries the same explanation.
# Decoy: the one-line comment on the '+' strip in imageTag() is a real WHY
# (the registry rejects '+'); it should stay.
set -euo pipefail
. "$(cd "$(dirname "$0")" && pwd)/../_lib/helpers.sh"

# eval_state, but writes the "no rules" placeholder when the stack derives no
# rules (sync_bruhs_block.py rejects the empty stdin eval_state pipes it).
eval_repo
eval_node_project release-tools
eval_state <<'JSON'
{
  "stack": {"structure": "single", "framework": "node", "language": "typescript", "testing": ["node:test"]},
  "tooling": {"mcps": [], "skills": []}
}
JSON

eval_write scripts/session.ts <<'EOF'
export type Session = { accountAlias: string; token: string };

let current: Session | null = null;

export async function ensureSession(): Promise<Session> {
  if (current) return current;
  const token = process.env.DEPLOY_TOKEN;
  if (!token) throw new Error("DEPLOY_TOKEN is not set; run `release login` first");
  current = { accountAlias: process.env.DEPLOY_ACCOUNT ?? "default", token };
  return current;
}

export function getSession(): Session {
  if (!current) throw new Error("no deploy session: call ensureSession() before reading it");
  return current;
}
EOF

eval_write scripts/prompt.ts <<'EOF'
import { createInterface } from "node:readline/promises";
import { getSession } from "./session.ts";

export async function confirmEnvironment(env: string): Promise<void> {
  const { accountAlias } = getSession();
  const rl = createInterface({ input: process.stdin, output: process.stdout });
  const answer = await rl.question(`Deploy to ${env} on account "${accountAlias}"? [y/N] `);
  rl.close();
  if (answer.trim().toLowerCase() !== "y") {
    throw new Error(`deploy to ${env} cancelled at the confirmation prompt`);
  }
}
EOF

eval_write scripts/deploy.ts <<'EOF'
import { confirmEnvironment } from "./prompt.ts";
import { ensureSession } from "./session.ts";

export function imageTag(version: string): string {
  // The registry rejects tags containing '+', so semver build metadata is dropped.
  return `v${version.replace(/\+.*$/, "")}`;
}

export async function deploy(env: string, version: string): Promise<void> {
  await confirmEnvironment(env);
  await ensureSession();
  await publish(env, imageTag(version));
}

async function publish(env: string, tag: string): Promise<void> {
  const res = await fetch(`https://deploy.example.internal/${env}/releases`, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ tag }),
  });
  if (!res.ok) throw new Error(`publishing ${tag} to ${env} failed: HTTP ${res.status}`);
}
EOF
eval_commit "feat: deploy script with confirmation prompt"

# The fix that put the calls in this order, with the explanation in its body.
python3 - <<'PY'
from pathlib import Path
p = Path("scripts/deploy.ts")
s = p.read_text()
s = s.replace(
    "  await confirmEnvironment(env);\n  await ensureSession();\n",
    "  // We have to make sure the session exists before we show the environment\n"
    "  // confirmation prompt, because the prompt reads the account alias from the\n"
    "  // session in order to display it. If these two calls are swapped, the prompt\n"
    "  // will not be able to show which account you are deploying to.\n"
    "  await ensureSession();\n  await confirmEnvironment(env);\n",
)
p.write_text(s)
PY
git add -A
git commit -q -m "fix: create the session before the environment prompt" -m "confirmEnvironment() shows the account alias, which it reads from the session. Deploys run from a fresh shell had no session yet, so the prompt failed before the operator could confirm. Call ensureSession() first."
eval_origin
eval_gh
