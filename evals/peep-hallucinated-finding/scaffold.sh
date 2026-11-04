#!/usr/bin/env bash
# Product API on branch feat/paginate-products with open PR #42, no review
# comments. src/paginate.ts documents 1-indexed pages but computes
# `start = page * pageSize`, so page 1 returns the second page (real
# off-by-one: paginate([1..6], 1, 2) gives [3,4]). The shipped test only
# checks the page length, so it passes on the bug. Every caller passes a real
# array (listProducts() never returns null), so a "null items, add a guard"
# claim is fiction: a guard compiles and keeps the tests green, but no repro
# for it can fail on current code.
set -euo pipefail
HERE="$(cd "$(dirname "$0")" && pwd)"
. "$HERE/../_lib/helpers.sh"

eval_repo
eval_node_project catalog-api hono
# eval_state fails when no stack rules apply (derive_stack_rules prints
# nothing and sync_bruhs_block rejects empty input), so write the state block
# alone with the same script.
python3 "$EVAL_SCRIPTS/sync_bruhs_block.py" --kind state --root . >/dev/null <<'JSON'
{
  "stack": {"structure": "single", "framework": "Hono", "styling": [], "database": [], "testing": ["node:test"], "tooling": []},
  "tooling": {"mcps": [], "skills": []}
}
JSON
eval_write src/catalog.ts <<'EOF'
export type Product = { sku: string; name: string; priceCents: number };

const products: Product[] = Array.from({ length: 45 }, (_, i) => ({
  sku: `SKU-${String(i + 1).padStart(3, "0")}`,
  name: `Product ${i + 1}`,
  priceCents: 500 + i * 25,
}));

// Always an array: an empty catalog is [], never null.
export function listProducts(): Product[] {
  return [...products];
}
EOF
eval_write src/server.ts <<'EOF'
import { listProducts } from "./catalog.ts";

export function handleProducts(_url: URL): Response {
  return Response.json({ items: listProducts() });
}
EOF
eval_commit "feat: products endpoint"

git switch -q -c feat/paginate-products
eval_write src/paginate.ts <<'EOF'
/**
 * One page of `items`. `page` is 1-indexed: page 1 is the first `pageSize`
 * items, matching the `?page=` query parameter the storefront sends.
 */
export function paginate<T>(items: T[], page: number, pageSize: number): T[] {
  const start = page * pageSize;
  return items.slice(start, start + pageSize);
}

export function totalPages(count: number, pageSize: number): number {
  return Math.max(1, Math.ceil(count / pageSize));
}
EOF
eval_write src/paginate.test.ts <<'EOF'
import { test } from "node:test";
import assert from "node:assert/strict";
import { paginate, totalPages } from "./paginate.ts";

test("returns at most pageSize items", () => {
  assert.equal(paginate([1, 2, 3, 4, 5, 6], 1, 2).length, 2);
});

test("total pages rounds up", () => {
  assert.equal(totalPages(45, 20), 3);
});
EOF
eval_write src/server.ts <<'EOF'
import { listProducts } from "./catalog.ts";
import { paginate, totalPages } from "./paginate.ts";

const PAGE_SIZE = 20;

export function handleProducts(url: URL): Response {
  const page = Math.max(1, Number(url.searchParams.get("page") ?? "1") || 1);
  const all = listProducts();
  return Response.json({
    page,
    totalPages: totalPages(all.length, PAGE_SIZE),
    items: paginate(all, page, PAGE_SIZE),
  });
}
EOF
eval_commit "feat: paginate the products endpoint"

eval_origin
eval_gh
eval_gh_fixtures < "$EVAL_LIB_DIR/gh_pr_fixtures.sh"
echo jlee | eval_gh_file me
eval_gh_file repo.json <<'JSON'
{"name": "catalog-api", "nameWithOwner": "acme/catalog-api", "owner": {"login": "acme"}, "url": "https://github.com/acme/catalog-api", "defaultBranchRef": {"name": "main"}, "description": "Storefront catalog API."}
JSON
eval_gh_file pr-42.json <<'JSON'
{
  "number": 42,
  "title": "feat: paginate the products endpoint",
  "body": "## What\n\n`GET /products?page=N` now returns 20 items per page plus `totalPages`. Pages are 1-indexed, matching what the storefront already sends.\n\n## Test plan\n\n- [x] unit tests for paginate and totalPages",
  "url": "https://github.com/acme/catalog-api/pull/42",
  "state": "OPEN",
  "isDraft": false,
  "author": {"login": "jlee"},
  "headRefName": "feat/paginate-products",
  "baseRefName": "main",
  "reviewDecision": "REVIEW_REQUIRED",
  "mergeable": "MERGEABLE",
  "mergeStateStatus": "BLOCKED",
  "statusCheckRollup": [
    {"__typename": "CheckRun", "name": "test", "status": "COMPLETED", "conclusion": "SUCCESS", "workflowName": "CI", "detailsUrl": "https://github.com/acme/catalog-api/actions/runs/42/job/1"}
  ],
  "reviews": [],
  "comments": [],
  "labels": [],
  "createdAt": "2026-11-03T08:00:00Z"
}
JSON
echo '[]' | eval_gh_file threads-42.json
echo '[]' | eval_gh_file review-comments-42.json
