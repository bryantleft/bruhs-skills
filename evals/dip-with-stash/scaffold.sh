#!/usr/bin/env bash
# The user is on perdix-140-add-dark-mode with a clean tree; its PR #91 was
# squash-merged into main on GitHub (not fetched locally yet), and the remote
# branch still exists and is tracked, so `git branch -d` succeeds.
# `git stash list` has two entries:
#   stash@{0}: On main: bruhs: stashed before add-dark-mode   (cook stashed
#              an unrelated README edit before starting the feature)
#   stash@{1}: On main: try serif headings                   (the user's own,
#              not bruhs')
# Both apply cleanly on the new main.
set -euo pipefail
HERE="$(cd "$(dirname "$0")" && pwd)"
. "$HERE/../_lib/helpers.sh"

BRANCH=perdix-140-add-dark-mode

eval_repo
eval_node_project settings-app next react react-dom tailwindcss
eval_state <<'JSON'
{
  "stack": {"structure": "single", "framework": "Next.js", "styling": ["Tailwind CSS"], "database": [], "testing": ["node:test"], "tooling": []},
  "tooling": {"mcps": ["linear"], "skills": []},
  "integrations": {"linear": {"mcpServer": "linear-perdix", "team": "PERDIX", "teamName": "Perdix", "project": "settings-app", "projectName": "Settings App"}}
}
JSON
eval_write README.md <<'EOF'
# settings-app

User settings.
EOF
eval_write src/app/globals.css <<'EOF'
h1 { font-family: system-ui, sans-serif; }
EOF
eval_write src/app/settings/page.tsx <<'EOF'
export default function SettingsPage() {
  return <main className="mx-auto max-w-xl p-6"><h1 className="text-xl font-semibold">Settings</h1></main>;
}
EOF
eval_commit "feat: settings page"

# The user's own experiment, stashed long ago.
perl -pi -e 's/system-ui, sans-serif/Georgia, serif/' src/app/globals.css
git stash push -q -m "try serif headings"
# cook's Step 4 Setup stashed an unrelated README edit before the feature.
printf '\n## Development\n\nRun `npm run dev` and open /settings.\n' >> README.md
git stash push -q -m "bruhs: stashed before add-dark-mode"

git switch -q -c "$BRANCH"
eval_write src/app/settings/theme-toggle.tsx <<'EOF'
"use client";
import { useEffect, useState } from "react";

export function ThemeToggle() {
  const [dark, setDark] = useState(false);
  useEffect(() => document.documentElement.classList.toggle("dark", dark), [dark]);
  return <button onClick={() => setDark((d) => !d)}>{dark ? "Light mode" : "Dark mode"}</button>;
}
EOF
eval_commit "feat(settings): dark mode toggle"
git switch -q main
eval_origin

# On GitHub: PR #91 is squash-merged.
OLD_MAIN="$(git rev-parse main)"
git merge -q --squash "$BRANCH" >/dev/null 2>&1
git commit -q -m "feat(settings): add dark mode (#91)" -m "Closes PERDIX-140"
git push -q origin main
git reset -q --hard "$OLD_MAIN"
git update-ref refs/remotes/origin/main "$OLD_MAIN"   # not fetched yet
git switch -q "$BRANCH"

eval_gh
eval_gh_fixtures < "$EVAL_LIB_DIR/gh_pr_fixtures.sh"
echo jlee | eval_gh_file me
eval_gh_file repo.json <<'JSON'
{"name": "settings-app", "nameWithOwner": "acme/settings-app", "owner": {"login": "acme"}, "url": "https://github.com/acme/settings-app", "defaultBranchRef": {"name": "main"}, "description": "User settings."}
JSON
eval_gh_file pr-91.json <<JSON
{
  "number": 91,
  "title": "feat(settings): add dark mode",
  "body": "Adds a theme toggle to /settings.\n\nCloses PERDIX-140",
  "url": "https://github.com/acme/settings-app/pull/91",
  "state": "MERGED",
  "mergedAt": "2026-11-03T09:58:00Z",
  "isDraft": false,
  "author": {"login": "jlee"},
  "headRefName": "$BRANCH",
  "baseRefName": "main",
  "reviewDecision": "APPROVED",
  "mergeable": "UNKNOWN",
  "mergeStateStatus": "UNKNOWN",
  "statusCheckRollup": [],
  "reviews": [],
  "comments": [],
  "labels": [],
  "createdAt": "2026-11-02T10:00:00Z"
}
JSON
echo '[]' | eval_gh_file threads-91.json
