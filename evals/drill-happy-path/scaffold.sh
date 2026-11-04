#!/usr/bin/env bash
# pnpm monorepo with a Next.js + Vitest app in apps/web. The root
# .github/workflows/ci.yml runs lint, typecheck, test --coverage and build
# for apps/web; typecheck has `continue-on-error: true` (added by a commit
# that promised to undo it). apps/web/vitest.config.ts gates coverage at 40%
# of TOTAL lines (history: 60 -> 50 -> 40, each lowered to keep CI green) and
# excludes all .tsx and src/components/** from coverage. eslint.config.mjs
# ignores tests/ entirely; tests/checkout.test.ts has a commented-out test
# and `expect(true).toBe(true)`. src/lib/pricing.test.ts only asserts
# toBeDefined(). No acceptance-spec runner, no mutation runner.
# docs/adrs/0007-app-must-not-import-from-marketing.md states a layer rule
# with no enforcer, and src/app/(app)/dashboard/page.tsx already violates it.
# Decoy that is fine: the Lighthouse step is continue-on-error by decision,
# documented in docs/adrs/0009-lighthouse-is-advisory.md.
set -euo pipefail
. "$(cd "$(dirname "$0")" && pwd)/../_lib/helpers.sh"

eval_repo
eval_state <<'JSON'
{
  "stack": {"structure": "monorepo", "framework": "nextjs", "language": "typescript", "styling": ["tailwind"], "testing": ["vitest"]},
  "tooling": {"mcps": [], "skills": []}
}
JSON

eval_write package.json <<'EOF'
{
  "name": "shop",
  "private": true,
  "packageManager": "pnpm@9.12.0",
  "scripts": {
    "lint": "pnpm -r lint",
    "typecheck": "pnpm -r typecheck",
    "test": "pnpm -r test"
  }
}
EOF

eval_write pnpm-workspace.yaml <<'EOF'
packages:
  - "apps/*"
EOF

eval_write .gitignore <<'EOF'
node_modules/
.next/
coverage/
EOF

eval_write apps/web/package.json <<'EOF'
{
  "name": "@shop/web",
  "private": true,
  "scripts": {
    "dev": "next dev",
    "build": "next build",
    "lint": "eslint .",
    "typecheck": "tsc --noEmit",
    "test": "vitest run",
    "lighthouse:ci": "lhci autorun"
  },
  "dependencies": {
    "next": "16.0.0",
    "react": "19.2.0",
    "react-dom": "19.2.0"
  },
  "devDependencies": {
    "@lhci/cli": "0.14.0",
    "@vitest/coverage-v8": "3.2.0",
    "eslint": "9.12.0",
    "typescript": "5.6.3",
    "vitest": "3.2.0"
  }
}
EOF

eval_write apps/web/tsconfig.json <<'EOF'
{
  "compilerOptions": {
    "strict": true,
    "noEmit": true,
    "jsx": "preserve",
    "module": "esnext",
    "moduleResolution": "bundler",
    "paths": { "@/*": ["./src/*"] }
  },
  "include": ["src", "tests"]
}
EOF

eval_write apps/web/eslint.config.mjs <<'EOF'
import next from "eslint-config-next";

export default [
  { ignores: ["tests/**", ".next/**"] },
  ...next,
];
EOF

eval_write apps/web/vitest.config.ts <<'EOF'
import { defineConfig } from "vitest/config";

export default defineConfig({
  test: {
    include: ["src/**/*.test.ts", "tests/**/*.test.ts"],
    coverage: {
      provider: "v8",
      include: ["src/**"],
      exclude: ["**/*.tsx", "src/components/**"],
      thresholds: { lines: 60 },
    },
  },
});
EOF

eval_write apps/web/src/lib/cart.ts <<'EOF'
export type CartLine = { sku: string; unitCents: number; quantity: number };

export function addLine(lines: readonly CartLine[], line: CartLine): CartLine[] {
  const existing = lines.find((l) => l.sku === line.sku);
  if (!existing) return [...lines, line];
  return lines.map((l) => (l.sku === line.sku ? { ...l, quantity: l.quantity + line.quantity } : l));
}

export function subtotalCents(lines: readonly CartLine[]): number {
  return lines.reduce((sum, l) => sum + l.unitCents * l.quantity, 0);
}
EOF

eval_write apps/web/src/lib/cart.test.ts <<'EOF'
import { describe, expect, it } from "vitest";
import { addLine, subtotalCents } from "./cart";

describe("cart", () => {
  it("merges quantities for the same sku", () => {
    const lines = addLine([{ sku: "a", unitCents: 500, quantity: 1 }], { sku: "a", unitCents: 500, quantity: 2 });
    expect(lines).toEqual([{ sku: "a", unitCents: 500, quantity: 3 }]);
  });

  it("sums line totals", () => {
    expect(subtotalCents([{ sku: "a", unitCents: 500, quantity: 3 }, { sku: "b", unitCents: 250, quantity: 2 }])).toBe(2000);
  });
});
EOF

eval_write apps/web/src/lib/pricing.ts <<'EOF'
import { subtotalCents, type CartLine } from "./cart";

export type Quote = { subtotalCents: number; discountCents: number; shippingCents: number; totalCents: number };

export function quote(lines: readonly CartLine[], coupon?: { percentOff: number }): Quote {
  const subtotal = subtotalCents(lines);
  const discount = coupon ? Math.round((subtotal * coupon.percentOff) / 100) : 0;
  const shipping = subtotal - discount >= 5000 ? 0 : 799;
  return { subtotalCents: subtotal, discountCents: discount, shippingCents: shipping, totalCents: subtotal - discount + shipping };
}
EOF

eval_write apps/web/src/lib/pricing.test.ts <<'EOF'
import { expect, it } from "vitest";
import { quote } from "./pricing";

it("quotes a cart", () => {
  const result = quote([{ sku: "a", unitCents: 2500, quantity: 2 }], { percentOff: 10 });
  expect(result).toBeDefined();
  expect(result.totalCents).toBeGreaterThan(0);
});
EOF

eval_write apps/web/tests/checkout.test.ts <<'EOF'
import { expect, it } from "vitest";
import { quote } from "../src/lib/pricing";

it("checkout total", () => {
  const q = quote([{ sku: "a", unitCents: 1000, quantity: 1 }]);
  expect(true).toBe(true);
  void q;
});

// it("free shipping at $50 after discount", () => {
//   const q = quote([{ sku: "a", unitCents: 5000, quantity: 1 }], { percentOff: 10 });
//   expect(q.shippingCents).toBe(799);
// });
EOF

eval_write apps/web/src/marketing/PricingTable.tsx <<'EOF'
export function PricingTable({ plans }: { plans: { name: string; priceCents: number }[] }) {
  return (
    <table>
      <tbody>
        {plans.map((p) => (
          <tr key={p.name}>
            <td>{p.name}</td>
            <td>${(p.priceCents / 100).toFixed(2)}</td>
          </tr>
        ))}
      </tbody>
    </table>
  );
}
EOF

eval_write "apps/web/src/app/(marketing)/pricing/page.tsx" <<'EOF'
import { PricingTable } from "@/marketing/PricingTable";

export default function PricingPage() {
  return <PricingTable plans={[{ name: "Starter", priceCents: 900 }, { name: "Pro", priceCents: 2900 }]} />;
}
EOF

eval_write "apps/web/src/app/(app)/checkout/page.tsx" <<'EOF'
import { quote } from "@/lib/pricing";

export default function CheckoutPage() {
  const q = quote([{ sku: "starter", unitCents: 900, quantity: 1 }]);
  return <p>Total: ${(q.totalCents / 100).toFixed(2)}</p>;
}
EOF

eval_write docs/adrs/0007-app-must-not-import-from-marketing.md <<'EOF'
# 7. The signed-in app must not import from marketing

Status: accepted

Marketing pages change weekly, are owned by the growth team and ship
experiments behind flags. The signed-in app under `apps/web/src/app/(app)`
must not import from `apps/web/src/marketing` or `apps/web/src/app/(marketing)`,
so a marketing change can never break checkout or the dashboard. Shared UI goes
in `src/components`.
EOF

eval_write docs/adrs/0009-lighthouse-is-advisory.md <<'EOF'
# 9. Lighthouse in CI is advisory

Status: accepted

Lighthouse scores on CI runners vary by ±8 points run to run, so a threshold
fails PRs for noise. The Lighthouse step reports scores on every PR but does not
fail the build (`continue-on-error: true`). Performance regressions are caught by
the weekly RUM review instead.
EOF

eval_write .github/workflows/ci.yml <<'EOF'
name: ci

on:
  pull_request:
  push:
    branches: [main]

jobs:
  web:
    runs-on: ubuntu-latest
    defaults:
      run:
        working-directory: apps/web
    steps:
      - uses: actions/checkout@v4
      - uses: pnpm/action-setup@v4
      - uses: actions/setup-node@v4
        with:
          node-version: 22
          cache: pnpm
      - run: pnpm install --frozen-lockfile
      - name: Lint
        run: pnpm lint
      - name: Typecheck
        run: pnpm typecheck
      - name: Test
        run: pnpm test --coverage
      - name: Build
        run: pnpm build
      - name: Lighthouse report
        # Advisory by decision: docs/adrs/0009-lighthouse-is-advisory.md
        run: pnpm lighthouse:ci
        continue-on-error: true
EOF
eval_commit "feat: shop web app with cart, pricing and CI"

eval_write "apps/web/src/app/(app)/dashboard/page.tsx" <<'EOF'
import { PricingTable } from "@/marketing/PricingTable";

export default function DashboardPage() {
  return (
    <main>
      <h1>Your plan</h1>
      <PricingTable plans={[{ name: "Pro", priceCents: 2900 }]} />
    </main>
  );
}
EOF
eval_commit "feat: show plans on the dashboard"

sed -i.bak 's/thresholds: { lines: 60 }/thresholds: { lines: 50 }/' apps/web/vitest.config.ts && rm apps/web/vitest.config.ts.bak
eval_commit "chore: lower coverage threshold to 50 to unblock release"

python3 - <<'PY'
from pathlib import Path
p = Path(".github/workflows/ci.yml")
p.write_text(p.read_text().replace(
    "        run: pnpm typecheck\n",
    "        run: pnpm typecheck\n        continue-on-error: true\n",
))
PY
git add -A
git commit -q -m "ci: don't block merges on typecheck while we fix the backlog" -m "Temporary. Remove continue-on-error once the strict-mode errors are fixed."

sed -i.bak 's/thresholds: { lines: 50 }/thresholds: { lines: 40 }/' apps/web/vitest.config.ts && rm apps/web/vitest.config.ts.bak
eval_commit "chore: lower coverage threshold to 40, keep CI green"

eval_origin
eval_gh
