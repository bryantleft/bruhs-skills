#!/usr/bin/env bash
# Merchant ledger in TypeScript. Invariant: every ledger has the three
# required accounts its schema defines (cash, receivable, revenue). But
# enroll.ts creates only the ledger row; accounts are created lazily by
# post.ts on a ledger's first posting, so ledgers with no postings yet
# (including older ones) have no accounts. The latest commit added
# `missingAccountAsZero` to reconcile.ts and turned it on in nightly.ts so the
# nightly run stops throwing on those ledgers.
# Decoy that is fine: statement.ts treats the schema-optional promo_credit
# account as 0 when absent; the schema says it may not exist.
set -euo pipefail
. "$(cd "$(dirname "$0")" && pwd)/../_lib/helpers.sh"

# eval_state, but writes the "no rules" placeholder when the stack derives no
# rules (sync_bruhs_block.py rejects the empty stdin eval_state pipes it).
eval_repo
eval_node_project merchant-ledger pg-promise
eval_state <<'JSON'
{
  "stack": {"structure": "single", "framework": "node", "language": "typescript", "database": ["postgres"], "testing": ["node:test"]},
  "tooling": {"mcps": [], "skills": []}
}
JSON

eval_write src/ledger/schema.ts <<'EOF'
export type AccountCode = "cash" | "receivable" | "revenue" | "promo_credit";

export type AccountSpec = { code: AccountCode; optional: boolean };

// Every ledger has the required accounts. promo_credit exists only for
// merchants enrolled in promotions.
export const LEDGER_ACCOUNTS: readonly AccountSpec[] = [
  { code: "cash", optional: false },
  { code: "receivable", optional: false },
  { code: "revenue", optional: false },
  { code: "promo_credit", optional: true },
];
EOF

eval_write src/ledger/store.ts <<'EOF'
import type { AccountCode } from "./schema.ts";

export type Ledger = { id: string; merchantId: string; createdAt: Date };
export type Account = { ledgerId: string; code: AccountCode; balanceCents: number };

export interface LedgerStore {
  insertLedger(merchantId: string): Promise<Ledger>;
  findAccounts(ledgerId: string): Promise<Account[]>;
  insertAccount(ledgerId: string, code: AccountCode): Promise<Account>;
  addToBalance(ledgerId: string, code: AccountCode, deltaCents: number): Promise<void>;
  listLedgerIds(): Promise<string[]>;
}
EOF

eval_write src/ledger/enroll.ts <<'EOF'
import type { Ledger, LedgerStore } from "./store.ts";

export async function enrollMerchant(store: LedgerStore, merchantId: string): Promise<Ledger> {
  return store.insertLedger(merchantId);
}
EOF

eval_write src/ledger/post.ts <<'EOF'
import type { AccountCode } from "./schema.ts";
import type { LedgerStore } from "./store.ts";

export type Entry = { ledgerId: string; debit: AccountCode; credit: AccountCode; amountCents: number };

export async function postEntry(store: LedgerStore, entry: Entry): Promise<void> {
  if (!Number.isInteger(entry.amountCents) || entry.amountCents <= 0) {
    throw new Error(`entry on ledger ${entry.ledgerId} must move a positive whole number of cents, got ${entry.amountCents}`);
  }
  const existing = new Set((await store.findAccounts(entry.ledgerId)).map((a) => a.code));
  for (const code of [entry.debit, entry.credit]) {
    if (!existing.has(code)) await store.insertAccount(entry.ledgerId, code);
  }
  await store.addToBalance(entry.ledgerId, entry.debit, entry.amountCents);
  await store.addToBalance(entry.ledgerId, entry.credit, -entry.amountCents);
}
EOF

eval_write src/ledger/reconcile.ts <<'EOF'
import { LEDGER_ACCOUNTS, type AccountCode } from "./schema.ts";
import type { LedgerStore } from "./store.ts";

export type Balances = Partial<Record<AccountCode, number>>;

export async function reconcile(store: LedgerStore, ledgerId: string): Promise<Balances> {
  const accounts = new Map((await store.findAccounts(ledgerId)).map((a) => [a.code, a]));
  const balances: Balances = {};
  for (const spec of LEDGER_ACCOUNTS) {
    if (spec.optional) continue;
    const account = accounts.get(spec.code);
    if (!account) {
      throw new Error(`ledger ${ledgerId} has no ${spec.code} account`);
    }
    balances[spec.code] = account.balanceCents;
  }
  const net = Object.values(balances).reduce((sum, cents) => sum + cents, 0);
  if (net !== 0) {
    throw new Error(`ledger ${ledgerId} is out of balance by ${net} cents across ${Object.keys(balances).join(", ")}`);
  }
  return balances;
}
EOF

eval_write src/ledger/nightly.ts <<'EOF'
import { reconcile } from "./reconcile.ts";
import type { LedgerStore } from "./store.ts";

export async function reconcileAll(store: LedgerStore): Promise<{ checked: number }> {
  const ids = await store.listLedgerIds();
  for (const id of ids) {
    await reconcile(store, id);
  }
  return { checked: ids.length };
}
EOF

eval_write src/ledger/statement.ts <<'EOF'
import type { LedgerStore } from "./store.ts";

export type Statement = { ledgerId: string; revenueCents: number; promoCreditCents: number };

export async function buildStatement(store: LedgerStore, ledgerId: string): Promise<Statement> {
  const accounts = new Map((await store.findAccounts(ledgerId)).map((a) => [a.code, a.balanceCents]));
  const revenue = accounts.get("revenue");
  if (revenue === undefined) {
    throw new Error(`ledger ${ledgerId} has no revenue account; cannot build a statement`);
  }
  // promo_credit is optional in the schema: merchants outside promotions have none.
  return { ledgerId, revenueCents: -revenue, promoCreditCents: accounts.get("promo_credit") ?? 0 };
}
EOF

eval_write src/ledger/reconcile.test.ts <<'EOF'
import { test } from "node:test";
import assert from "node:assert/strict";
import { reconcile } from "./reconcile.ts";
import type { Account, LedgerStore } from "./store.ts";

function storeWith(accounts: Account[]): LedgerStore {
  return {
    insertLedger: async () => { throw new Error("unused"); },
    findAccounts: async () => accounts,
    insertAccount: async () => { throw new Error("unused"); },
    addToBalance: async () => {},
    listLedgerIds: async () => ["l1"],
  };
}

test("a balanced ledger reconciles", async () => {
  const store = storeWith([
    { ledgerId: "l1", code: "cash", balanceCents: 500 },
    { ledgerId: "l1", code: "receivable", balanceCents: 0 },
    { ledgerId: "l1", code: "revenue", balanceCents: -500 },
  ]);
  assert.deepEqual(await reconcile(store, "l1"), { cash: 500, receivable: 0, revenue: -500 });
});
EOF
eval_commit "feat: merchant ledgers with nightly reconciliation"

# The recent change: tolerate missing accounts instead of fixing the writers.
python3 - <<'PY'
from pathlib import Path
p = Path("src/ledger/reconcile.ts")
s = p.read_text()
s = s.replace(
    "export async function reconcile(store: LedgerStore, ledgerId: string): Promise<Balances> {",
    "export type ReconcileOptions = { missingAccountAsZero?: boolean };\n\n"
    "export async function reconcile(\n  store: LedgerStore,\n  ledgerId: string,\n  options: ReconcileOptions = {},\n): Promise<Balances> {",
)
s = s.replace(
    "    if (!account) {\n",
    "    if (!account) {\n"
    "      if (options.missingAccountAsZero) {\n"
    "        balances[spec.code] = 0;\n"
    "        continue;\n"
    "      }\n",
)
p.write_text(s)
p = Path("src/ledger/nightly.ts")
p.write_text(p.read_text().replace("await reconcile(store, id);", "await reconcile(store, id, { missingAccountAsZero: true });"))
t = Path("src/ledger/reconcile.test.ts")
t.write_text(t.read_text() + '''
test("missingAccountAsZero treats absent accounts as zero", async () => {
  assert.deepEqual(await reconcile(storeWith([]), "l1", { missingAccountAsZero: true }), {
    cash: 0,
    receivable: 0,
    revenue: 0,
  });
});
''')
PY
git add -A
git commit -q -m "fix: stop nightly reconcile failing on ledgers without accounts" -m "Accounts are created on a ledger's first posting, so ledgers that have never posted (and some older ones) have no accounts and reconcile() threw for every one of them, failing the nightly run. Add missingAccountAsZero and use it in the nightly job."
eval_origin
eval_gh
