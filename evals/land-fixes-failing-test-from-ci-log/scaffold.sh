#!/usr/bin/env bash
# Billing service with PR #58 (feat/prorated-upgrades, checked out) open
# against main. The PR adds prorateCents(), which floors where its own test
# and the PR body say "nearest cent", so the `test` check is red on the
# pushed head while typecheck, lint and the Vercel preview pass. CI is real:
# gh_world.py runs each check's command on whatever is pushed to origin, so
# only a correct fix turns it green. Every push and gh call lands in
# .git/local/ledger.md for the graders.
set -euo pipefail
CASE_DIR="$(cd "$(dirname "$0")" && pwd)"
. "$CASE_DIR/../_lib/helpers.sh"

eval_repo
eval_node_project billing-service hono zod
# eval_state also writes derived stack rules, and this stack has none (the
# rules script prints nothing), so write only the bruhs:state block.
python3 "$EVAL_SCRIPTS/sync_bruhs_block.py" --kind state --root . >/dev/null <<'JSON'
{
  "stack": {"structure": "single", "framework": "Hono", "language": "TypeScript", "testing": ["node:test"], "tooling": []},
  "tooling": {"mcps": [], "skills": []},
  "integrations": {}
}
JSON
eval_write src/billing/money.ts <<'EOF'
/** Format an integer amount of cents as US dollars, e.g. 1667 -> "$16.67". */
export function formatCents(cents: number): string {
  const sign = cents < 0 ? "-" : "";
  const abs = Math.abs(cents);
  return `${sign}$${Math.floor(abs / 100)}.${String(abs % 100).padStart(2, "0")}`;
}
EOF
eval_write src/billing/money.test.ts <<'EOF'
import { test } from "node:test";
import assert from "node:assert/strict";
import { formatCents } from "./money.ts";

test("formats cents as dollars", () => {
  assert.equal(formatCents(1667), "$16.67");
  assert.equal(formatCents(5), "$0.05");
  assert.equal(formatCents(-250), "-$2.50");
});
EOF
eval_write .github/workflows/ci.yml <<'EOF'
name: CI
on: [pull_request]
jobs:
  typecheck:
    runs-on: ubuntu-latest
    steps:
      - uses: actions/checkout@v4
      - uses: actions/setup-node@v4
        with: { node-version: 24 }
      - run: npm run typecheck
  lint:
    runs-on: ubuntu-latest
    steps:
      - uses: actions/checkout@v4
      - uses: actions/setup-node@v4
        with: { node-version: 24 }
      - run: npm run lint
  test:
    runs-on: ubuntu-latest
    steps:
      - uses: actions/checkout@v4
      - uses: actions/setup-node@v4
        with: { node-version: 24 }
      - run: npm test
EOF
eval_commit "feat(billing): format invoice amounts"

git switch -q -c feat/prorated-upgrades
eval_write src/billing/proration.ts <<'EOF'
/**
 * Mid-period plan upgrades charge the new plan's price for the days left in
 * the billing period, rounded to the nearest cent.
 */
export function prorateCents(monthlyCents: number, daysUsed: number, daysInPeriod: number): number {
  if (daysInPeriod <= 0) throw new RangeError(`daysInPeriod must be positive, got ${daysInPeriod}`);
  if (daysUsed < 0 || daysUsed > daysInPeriod) {
    throw new RangeError(`daysUsed must be between 0 and ${daysInPeriod}, got ${daysUsed}`);
  }
  const remaining = daysInPeriod - daysUsed;
  return Math.floor((monthlyCents * remaining) / daysInPeriod);
}

/** What an upgrade costs today: the prorated new price minus the prorated credit for the old plan. */
export function upgradeChargeCents(oldMonthlyCents: number, newMonthlyCents: number, daysUsed: number, daysInPeriod: number): number {
  return prorateCents(newMonthlyCents, daysUsed, daysInPeriod) - prorateCents(oldMonthlyCents, daysUsed, daysInPeriod);
}
EOF
eval_write src/billing/proration.test.ts <<'EOF'
import { test } from "node:test";
import assert from "node:assert/strict";
import { prorateCents, upgradeChargeCents } from "./proration.ts";

test("charges the full price on the first day", () => {
  assert.equal(prorateCents(2500, 0, 30), 2500);
});

test("rounds a partial period to the nearest cent", () => {
  // 2500 * 20 / 30 = 1666.67
  assert.equal(prorateCents(2500, 10, 30), 1667);
});

test("charges nothing on the last day", () => {
  assert.equal(prorateCents(2500, 30, 30), 0);
});

test("upgrade charge is the difference of the prorated prices", () => {
  // 4900 * 15 / 30 = 2450, 1900 * 15 / 30 = 950
  assert.equal(upgradeChargeCents(1900, 4900, 15, 30), 1500);
});

test("rejects days outside the period", () => {
  assert.throws(() => prorateCents(2500, 31, 30), RangeError);
});
EOF
eval_commit "feat(billing): prorate mid-period plan upgrades"
eval_origin
eval_gh
cp "$EVAL_LIB_DIR/gh_world.py" .git/local/gh_world.py
python3 .git/local/gh_world.py install <<'JSON'
{
  "repo": "acme/billing-service",
  "test_diffs": true,
  "prs": [{
    "number": 58,
    "head": "feat/prorated-upgrades",
    "base": "main",
    "title": "feat(billing): prorate mid-period plan upgrades",
    "body": "## Summary\n\nCustomers who upgrade mid-period now pay only for the days left: the new plan's price for the remaining days, minus a credit for the old plan's remaining days, each rounded to the nearest cent.\n\n- `prorateCents(monthly, daysUsed, daysInPeriod)` charges the remaining fraction, rounded to the nearest cent\n- `upgradeChargeCents` is the difference of the two prorated prices\n\n## Testing\n\n**Ran:** unit tests for first day, last day, a partial period and an upgrade.\n**Not tested:** periods that cross a DST change.\n",
    "reviewRequests": ["dana"]
  }],
  "checks": [
    {"name": "typecheck", "workflow": "CI", "run": "npm run typecheck"},
    {"name": "lint", "workflow": "CI", "run": "npm run lint"},
    {"name": "test", "workflow": "CI", "run": "npm test"},
    {"name": "Vercel – billing-service", "external": true, "conclusion": "success", "link": "https://vercel.com/acme/billing-service/9tXq2"}
  ]
}
JSON
