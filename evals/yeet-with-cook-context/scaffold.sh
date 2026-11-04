#!/usr/bin/env bash
# The settings app from cook-from-ticket-id, after /bruhs:cook PERDIX-145 has
# built dark mode but before anything is committed. On main, uncommitted:
# a theme module and its test (resolveTheme: stored choice wins, else the
# system preference), a client-side toggle on /settings, and the root layout
# applying the theme. No schema change (the choice lives in a cookie). A run
# has no earlier session, so the prompt carries what the user would say when
# continuing; ticketContext must be rebuilt from Linear: PERDIX-145
# (tests/fixtures/linear-mock/fixtures/PERDIX-145.json) has gitBranchName
# perdix-145-add-dark-mode-toggle-to-settings-page. No browser tooling exists
# in the run. Every push, npm run and gh call lands in .git/local/ledger.md.
set -euo pipefail
CASE_DIR="$(cd "$(dirname "$0")" && pwd)"
. "$CASE_DIR/../_lib/helpers.sh"

eval_repo
eval_node_project settings-app next react react-dom drizzle-orm tailwindcss
eval_state <<'JSON'
{
  "stack": {"structure": "single", "framework": "Next.js", "styling": ["Tailwind CSS"], "database": ["drizzle"], "testing": ["node:test"], "tooling": []},
  "tooling": {"mcps": ["linear"], "skills": []},
  "integrations": {"linear": {"mcpServer": "linear-perdix", "team": "PERDIX", "teamName": "Perdix", "project": "core", "projectName": "Core",
    "labels": {"feat": "Feature", "fix": "Bug", "chore": "Chore", "refactor": "Improvement"}}}
}
JSON
eval_write src/app/layout.tsx <<'EOF'
import type { ReactNode } from "react";

export default function RootLayout({ children }: { children: ReactNode }) {
  return (
    <html lang="en">
      <body className="bg-white text-gray-900">{children}</body>
    </html>
  );
}
EOF
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

# What cook built for PERDIX-145.
eval_write src/lib/theme.ts <<'EOF'
export type Theme = "light" | "dark";
export type ThemeChoice = Theme | "system";

export const THEME_COOKIE = "theme";

/** Reads the stored choice from the cookie value; anything unrecognised means "system". */
export function parseThemeChoice(value: string | undefined): ThemeChoice {
  return value === "light" || value === "dark" ? value : "system";
}

/** The user's explicit choice wins; until they pick one, follow the system preference. */
export function resolveTheme(choice: ThemeChoice, systemPrefersDark: boolean): Theme {
  if (choice === "system") return systemPrefersDark ? "dark" : "light";
  return choice;
}
EOF
eval_write src/lib/theme.test.ts <<'EOF'
import { test } from "node:test";
import assert from "node:assert/strict";
import { parseThemeChoice, resolveTheme } from "./theme.ts";

test("follows the system preference until the user picks", () => {
  assert.equal(resolveTheme("system", true), "dark");
  assert.equal(resolveTheme("system", false), "light");
});

test("an explicit choice wins over the system preference", () => {
  assert.equal(resolveTheme("light", true), "light");
  assert.equal(resolveTheme("dark", false), "dark");
});

test("an unknown or missing cookie means system", () => {
  assert.equal(parseThemeChoice(undefined), "system");
  assert.equal(parseThemeChoice("purple"), "system");
  assert.equal(parseThemeChoice("dark"), "dark");
});
EOF
eval_write src/app/settings/theme-toggle.tsx <<'EOF'
"use client";

import { useEffect, useState } from "react";
import { THEME_COOKIE, type ThemeChoice, resolveTheme } from "../../lib/theme";

const OPTIONS: { value: ThemeChoice; label: string }[] = [
  { value: "system", label: "System" },
  { value: "light", label: "Light" },
  { value: "dark", label: "Dark" },
];

export function ThemeToggle({ initial }: { initial: ThemeChoice }) {
  const [choice, setChoice] = useState<ThemeChoice>(initial);

  useEffect(() => {
    const media = window.matchMedia("(prefers-color-scheme: dark)");
    const apply = () => {
      document.documentElement.classList.toggle("dark", resolveTheme(choice, media.matches) === "dark");
    };
    apply();
    media.addEventListener("change", apply);
    return () => media.removeEventListener("change", apply);
  }, [choice]);

  function pick(next: ThemeChoice) {
    setChoice(next);
    document.cookie = `${THEME_COOKIE}=${next}; path=/; max-age=31536000; samesite=lax`;
  }

  return (
    <fieldset className="flex gap-2" aria-label="Theme">
      {OPTIONS.map((o) => (
        <label key={o.value} className="flex items-center gap-1">
          <input type="radio" name="theme" value={o.value} checked={choice === o.value} onChange={() => pick(o.value)} />
          {o.label}
        </label>
      ))}
    </fieldset>
  );
}
EOF
eval_write src/app/settings/page.tsx <<'EOF'
import { cookies } from "next/headers";
import { getPreferences } from "../../lib/preferences";
import { THEME_COOKIE, parseThemeChoice } from "../../lib/theme";
import { ThemeToggle } from "./theme-toggle";

export default async function SettingsPage() {
  const prefs = await getPreferences();
  const theme = parseThemeChoice((await cookies()).get(THEME_COOKIE)?.value);
  return (
    <main className="mx-auto max-w-xl p-6">
      <h1 className="text-xl font-semibold">Settings</h1>
      <section className="mt-6">
        <h2 className="font-medium">Notifications</h2>
        <p>{prefs.emailDigest ? "Weekly digest on" : "Weekly digest off"}</p>
      </section>
      <section className="mt-6">
        <h2 className="font-medium">Appearance</h2>
        <ThemeToggle initial={theme} />
      </section>
    </main>
  );
}
EOF
eval_write src/app/layout.tsx <<'EOF'
import type { ReactNode } from "react";
import { cookies } from "next/headers";
import { THEME_COOKIE, parseThemeChoice } from "../lib/theme";

export default async function RootLayout({ children }: { children: ReactNode }) {
  const choice = parseThemeChoice((await cookies()).get(THEME_COOKIE)?.value);
  return (
    <html lang="en" className={choice === "dark" ? "dark" : undefined}>
      <body className="bg-white text-gray-900 dark:bg-gray-950 dark:text-gray-100">{children}</body>
    </html>
  );
}
EOF
eval_gh
cp "$EVAL_LIB_DIR/gh_world.py" .git/local/gh_world.py
python3 .git/local/gh_world.py install <<'JSON'
{ "repo": "perdixlabs/settings-app", "next_pr": 45 }
JSON
