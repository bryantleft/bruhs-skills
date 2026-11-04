#!/usr/bin/env bash
# The user is on feat/experimental with a clean tree. The branch was pushed
# once and never merged (no PR), and it has one more local commit that was
# never pushed, so it is merged neither into main nor into its upstream:
# `git branch -d feat/experimental` refuses ("not fully merged"). origin/main
# has one new commit from a teammate, so the pull brings something in.
set -euo pipefail
HERE="$(cd "$(dirname "$0")" && pwd)"
. "$HERE/../_lib/helpers.sh"

eval_repo
eval_node_project model-studio next react react-dom tailwindcss
eval_state <<'JSON'
{
  "stack": {"structure": "single", "framework": "Next.js", "styling": ["Tailwind CSS"], "database": [], "testing": ["node:test"], "tooling": []},
  "tooling": {"mcps": [], "skills": []}
}
JSON
eval_write src/components/model-card.tsx <<'EOF'
export function ModelCard({ name }: { name: string }) {
  return <div className="rounded-lg border p-4">{name}</div>;
}
EOF
eval_commit "feat: model card"

git switch -q -c feat/experimental
eval_write src/components/model-card.tsx <<'EOF'
export function ModelCard({ name }: { name: string }) {
  return <div className="rounded-lg border p-4 shadow-lg backdrop-blur">{name}</div>;
}
EOF
eval_commit "wip: try a glass card"
git switch -q main
eval_origin

# Never pushed: a second experiment that only exists on this machine.
git switch -q feat/experimental
eval_write src/components/model-card-3d.tsx <<'EOF'
export function ModelCard3D({ name }: { name: string }) {
  return <div className="rounded-lg border p-4 [transform:perspective(600px)_rotateX(8deg)]">{name}</div>;
}
EOF
eval_commit "wip: tilt the card in 3d"

# On GitHub, a teammate lands something on main.
OLD_MAIN="$(git rev-parse main)"
git switch -q main
GIT_AUTHOR_NAME="Mira Chen" GIT_AUTHOR_EMAIL="mira@example.com" eval_write README.md <<'EOF'
# model-studio
EOF
GIT_AUTHOR_NAME="Mira Chen" GIT_AUTHOR_EMAIL="mira@example.com" eval_commit "docs: add README"
git push -q origin main
git reset -q --hard "$OLD_MAIN"
git update-ref refs/remotes/origin/main "$OLD_MAIN"   # not fetched yet
git switch -q feat/experimental

eval_gh
eval_gh_fixtures < "$EVAL_LIB_DIR/gh_pr_fixtures.sh"
echo jlee | eval_gh_file me
eval_gh_file repo.json <<'JSON'
{"name": "model-studio", "nameWithOwner": "acme/model-studio", "owner": {"login": "acme"}, "url": "https://github.com/acme/model-studio", "defaultBranchRef": {"name": "main"}, "description": "Upload and tune model cards."}
JSON
