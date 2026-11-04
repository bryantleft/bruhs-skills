#!/usr/bin/env bash
# Next.js app on branch feat/add-profile-page with open PR #73: CI green, no
# review threads, no reviews, no .claude/.peep-history/ yet. The PR adds
# src/lib/profile.ts, whose displayName() renders "Ada undefined" for a user
# without a last name (real bug; the shipped test only covers full names).
# memberSinceDays() carries a bare 86_400_000 and a terse variable name: bait
# for naming / magic-number suggestions the lint-territory filter should drop.
set -euo pipefail
HERE="$(cd "$(dirname "$0")" && pwd)"
. "$HERE/../_lib/helpers.sh"

eval_repo
eval_node_project people-app next react react-dom tailwindcss
eval_state <<'JSON'
{
  "stack": {"structure": "single", "framework": "Next.js", "styling": ["Tailwind CSS"], "database": [], "testing": ["node:test"], "tooling": []},
  "tooling": {"mcps": [], "skills": []}
}
JSON
eval_write src/lib/users.ts <<'EOF'
export type User = {
  id: string;
  firstName: string;
  lastName?: string;
  email: string;
  createdAt: string;
};

const users: User[] = [
  { id: "u1", firstName: "Grace", lastName: "Hopper", email: "grace@example.com", createdAt: "2026-01-04T09:00:00Z" },
  { id: "u2", firstName: "Ada", email: "ada@example.com", createdAt: "2026-10-30T12:00:00Z" },
];

export function getUser(id: string): User | undefined {
  return users.find((u) => u.id === id);
}
EOF
eval_write src/app/page.tsx <<'EOF'
export default function Home() {
  return <main className="p-6">People</main>;
}
EOF
eval_commit "feat: user directory"

git switch -q -c feat/add-profile-page
eval_write src/lib/profile.ts <<'EOF'
import type { User } from "./users.ts";

// Name shown in the profile header. Last names are optional at signup.
export function displayName(user: User): string {
  return `${user.firstName} ${user.lastName}`.trim();
}

export function memberSinceDays(user: User, now: Date = new Date()): number {
  const d = now.getTime() - new Date(user.createdAt).getTime();
  return Math.floor(d / 86_400_000);
}

export function initials(user: User): string {
  return displayName(user)
    .split(" ")
    .map((part) => part[0]?.toUpperCase() ?? "")
    .join("");
}
EOF
eval_write src/lib/profile.test.ts <<'EOF'
import { test } from "node:test";
import assert from "node:assert/strict";
import { displayName, memberSinceDays } from "./profile.ts";

const grace = { id: "u1", firstName: "Grace", lastName: "Hopper", email: "g@example.com", createdAt: "2026-01-04T09:00:00Z" };

test("display name joins first and last", () => {
  assert.equal(displayName(grace), "Grace Hopper");
});

test("member since counts whole days", () => {
  assert.equal(memberSinceDays(grace, new Date("2026-01-06T10:00:00Z")), 2);
});
EOF
eval_write 'src/app/profile/[id]/page.tsx' <<'EOF'
import { notFound } from "next/navigation";
import { getUser } from "../../../lib/users";
import { displayName, initials, memberSinceDays } from "../../../lib/profile";

export default async function ProfilePage({ params }: { params: Promise<{ id: string }> }) {
  const { id } = await params;
  const user = getUser(id);
  if (!user) notFound();
  return (
    <main className="mx-auto max-w-xl p-6">
      <div className="flex items-center gap-3">
        <span className="grid size-10 place-items-center rounded-full bg-muted">{initials(user)}</span>
        <h1 className="text-xl font-semibold">{displayName(user)}</h1>
      </div>
      <p className="mt-2 text-sm text-muted-foreground">Member for {memberSinceDays(user)} days</p>
    </main>
  );
}
EOF
eval_commit "feat: add profile page"

eval_origin
eval_gh
eval_gh_fixtures < "$EVAL_LIB_DIR/gh_pr_fixtures.sh"
echo jlee | eval_gh_file me
eval_gh_file repo.json <<'JSON'
{"name": "people-app", "nameWithOwner": "acme/people-app", "owner": {"login": "acme"}, "url": "https://github.com/acme/people-app", "defaultBranchRef": {"name": "main"}, "description": "Internal people directory."}
JSON
eval_gh_file pr-73.json <<'JSON'
{
  "number": 73,
  "title": "feat: add profile page",
  "body": "## What\n\nAdds /profile/[id]: avatar initials, display name and how long the person has been a member.\n\n## Why\n\nThe directory links to people but there's nowhere to land.\n\n## Test plan\n\n- [x] unit tests for displayName and memberSinceDays\n- [x] opened /profile/u1 locally",
  "url": "https://github.com/acme/people-app/pull/73",
  "state": "OPEN",
  "isDraft": false,
  "author": {"login": "jlee"},
  "headRefName": "feat/add-profile-page",
  "baseRefName": "main",
  "reviewDecision": "REVIEW_REQUIRED",
  "mergeable": "MERGEABLE",
  "mergeStateStatus": "BLOCKED",
  "statusCheckRollup": [
    {"__typename": "CheckRun", "name": "typecheck", "status": "COMPLETED", "conclusion": "SUCCESS", "workflowName": "CI", "detailsUrl": "https://github.com/acme/people-app/actions/runs/73/job/1"},
    {"__typename": "CheckRun", "name": "lint", "status": "COMPLETED", "conclusion": "SUCCESS", "workflowName": "CI", "detailsUrl": "https://github.com/acme/people-app/actions/runs/73/job/2"},
    {"__typename": "CheckRun", "name": "test", "status": "COMPLETED", "conclusion": "SUCCESS", "workflowName": "CI", "detailsUrl": "https://github.com/acme/people-app/actions/runs/73/job/3"}
  ],
  "reviews": [],
  "comments": [],
  "labels": [],
  "createdAt": "2026-11-03T09:30:00Z"
}
JSON
echo '[]' | eval_gh_file threads-73.json
echo '[]' | eval_gh_file review-comments-73.json
