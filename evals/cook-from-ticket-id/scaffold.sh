#!/usr/bin/env bash
# Next.js + Drizzle app with a settings page and no theme support yet.
# bruhs:state points Linear at linear-perdix, where PERDIX-145 is the
# dark-mode ticket (tests/fixtures/linear-mock/fixtures/PERDIX-145.json).
set -euo pipefail
. "$(cd "$(dirname "$0")" && pwd)/../_lib/helpers.sh"

eval_repo
eval_node_project settings-app next react react-dom drizzle-orm tailwindcss
eval_state <<'JSON'
{
  "stack": {"structure": "single", "framework": "Next.js", "styling": ["Tailwind CSS"], "database": ["drizzle"], "testing": ["node:test"], "tooling": []},
  "tooling": {"mcps": ["linear"], "skills": []},
  "integrations": {"linear": {"mcpServer": "linear-perdix", "team": "PERDIX", "teamName": "Perdix", "project": "core", "projectName": "Core"}}
}
JSON
eval_write src/app/settings/page.tsx <<'EOF'
import { getPreferences } from "../../lib/preferences";

export default async function SettingsPage() {
  const prefs = await getPreferences();
  return (
    <main className="mx-auto max-w-xl p-6">
      <h1 className="text-xl font-semibold">Settings</h1>
      <section className="mt-6">
        <h2 className="font-medium">Notifications</h2>
        <p>{prefs.emailDigest ? "Weekly digest on" : "Weekly digest off"}</p>
      </section>
    </main>
  );
}
EOF
eval_write src/lib/preferences.ts <<'EOF'
export type Preferences = { emailDigest: boolean };

const defaults: Preferences = { emailDigest: true };

export async function getPreferences(): Promise<Preferences> {
  return { ...defaults };
}
EOF
eval_write src/lib/preferences.test.ts <<'EOF'
import { test } from "node:test";
import assert from "node:assert/strict";
import { getPreferences } from "./preferences.ts";

test("defaults to the weekly digest", async () => {
  assert.equal((await getPreferences()).emailDigest, true);
});
EOF
eval_write src/db/schema.ts <<'EOF'
import { boolean, pgTable, text } from "drizzle-orm/pg-core";

export const userPreferences = pgTable("user_preferences", {
  userId: text("user_id").primaryKey(),
  emailDigest: boolean("email_digest").notNull().default(true),
});
EOF
eval_commit "feat: settings page with notification preferences"
eval_origin
eval_gh
