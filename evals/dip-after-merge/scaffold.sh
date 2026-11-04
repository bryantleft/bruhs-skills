#!/usr/bin/env bash
# Next.js app. The user is on perdix-139-make-model-form-image-upload-fully-rounded
# with a clean tree and no stashes. Its PR #87 was squash-merged on GitHub 30
# seconds ago: origin/main now has a teammate's commit plus the squash commit,
# but the local clone hasn't fetched yet (local main and origin/main are
# behind). The remote feature branch still exists, and the local branch tracks
# it, so `git branch -d` succeeds (with git's "merged to upstream, not HEAD"
# warning). No PRs are stacked on the branch.
set -euo pipefail
HERE="$(cd "$(dirname "$0")" && pwd)"
. "$HERE/../_lib/helpers.sh"

BRANCH=perdix-139-make-model-form-image-upload-fully-rounded

eval_repo
eval_node_project model-studio next react react-dom tailwindcss
eval_state <<'JSON'
{
  "stack": {"structure": "single", "framework": "Next.js", "styling": ["Tailwind CSS"], "database": [], "testing": ["node:test"], "tooling": []},
  "tooling": {"mcps": ["linear"], "skills": []},
  "integrations": {"linear": {"mcpServer": "linear-perdix", "team": "PERDIX", "teamName": "Perdix", "project": "model-studio", "projectName": "Model Studio"}}
}
JSON
eval_write src/components/model-form.tsx <<'EOF'
export function ModelForm() {
  return (
    <form className="space-y-4">
      <label className="block">
        <span>Model image</span>
        <input type="file" accept="image/*" className="mt-1 block w-full rounded-md border p-2" />
      </label>
      <button className="rounded-md bg-black px-4 py-2 text-white">Save</button>
    </form>
  );
}
EOF
eval_commit "feat: model form"

git switch -q -c "$BRANCH"
perl -pi -e 's/mt-1 block w-full rounded-md border p-2/mt-1 block w-full rounded-full border p-2 file:rounded-full/' src/components/model-form.tsx
eval_commit "feat(model-form): fully round the image upload"
perl -pi -e 's/rounded-md bg-black/rounded-full bg-black/' src/components/model-form.tsx
eval_commit "feat(model-form): round the save button to match"

git switch -q main
eval_origin

# On GitHub: a teammate's commit lands, then PR #87 is squash-merged.
OLD_MAIN="$(git rev-parse main)"
GIT_AUTHOR_NAME="Mira Chen" GIT_AUTHOR_EMAIL="mira@example.com" eval_write README.md <<'EOF'
# model-studio

Upload and tune model cards.
EOF
GIT_AUTHOR_NAME="Mira Chen" GIT_AUTHOR_EMAIL="mira@example.com" eval_commit "docs: add README"
git merge -q --squash "$BRANCH" >/dev/null 2>&1
git commit -q -m "feat(model-form): make image upload fully rounded (#87)" -m "Closes PERDIX-139"
git push -q origin main
git reset -q --hard "$OLD_MAIN"
git update-ref refs/remotes/origin/main "$OLD_MAIN"   # not fetched yet
git switch -q "$BRANCH"

eval_gh
eval_gh_fixtures < "$EVAL_LIB_DIR/gh_pr_fixtures.sh"
echo jlee | eval_gh_file me
eval_gh_file repo.json <<'JSON'
{"name": "model-studio", "nameWithOwner": "acme/model-studio", "owner": {"login": "acme"}, "url": "https://github.com/acme/model-studio", "defaultBranchRef": {"name": "main"}, "description": "Upload and tune model cards."}
JSON
MERGED_AT="$(date -u -v-30S +%Y-%m-%dT%H:%M:%SZ 2>/dev/null || date -u -d '30 seconds ago' +%Y-%m-%dT%H:%M:%SZ)"
eval_gh_file pr-87.json <<JSON
{
  "number": 87,
  "title": "feat(model-form): make image upload fully rounded",
  "body": "Rounds the file input and the save button.\n\nCloses PERDIX-139",
  "url": "https://github.com/acme/model-studio/pull/87",
  "state": "MERGED",
  "mergedAt": "$MERGED_AT",
  "mergeCommit": {"oid": "$(git --git-dir=.git/local/origin.git rev-parse main)"},
  "isDraft": false,
  "author": {"login": "jlee"},
  "headRefName": "$BRANCH",
  "baseRefName": "main",
  "reviewDecision": "APPROVED",
  "mergeable": "UNKNOWN",
  "mergeStateStatus": "UNKNOWN",
  "statusCheckRollup": [],
  "reviews": [{"author": {"login": "mira-chen"}, "state": "APPROVED", "body": "", "submittedAt": "$MERGED_AT"}],
  "comments": [],
  "labels": [],
  "createdAt": "2026-11-02T10:00:00Z"
}
JSON
echo '[]' | eval_gh_file threads-87.json
