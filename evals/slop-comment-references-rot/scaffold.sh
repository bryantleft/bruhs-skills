#!/usr/bin/env bash
# Rewards ledger in TypeScript. main has LedgerEvent, a sibling subclass
# RewardReversed (precedent, not justification) and Ledger.post(), which
# already rejects non-positive amounts and keys on event.type.
# Branch feat/referral-rewards (checked out, pushed) adds src/rewards/grant.ts
# and src/jobs/promo-batch.ts with comments that rot ('covers R4 from the
# plan', 'per Sam in #backend', 'see ledger.ts line 88' (ledger.ts is ~30
# lines), 'temporary, remove after 2027-02'), a process note ('every new
# reward type also needs a row in reward_kinds'), a preset-only subclass
# RewardGranted, and an uncommented `if (req.kind === "promo") return;` above
# a switch that has a promo case (the nightly promo batch posts promo grants
# through eventsFor(); granting here would double-credit).
# Decoy: `// TODO(ENG-123): ...` tracks open work and is fine.
set -euo pipefail
. "$(cd "$(dirname "$0")" && pwd)/../_lib/helpers.sh"

# eval_state, but writes the "no rules" placeholder when the stack derives no
# rules (sync_bruhs_block.py rejects the empty stdin eval_state pipes it).
eval_repo
eval_node_project rewards-service
eval_state <<'JSON'
{
  "stack": {"structure": "single", "framework": "node", "language": "typescript", "testing": ["node:test"]},
  "tooling": {"mcps": [], "skills": []}
}
JSON

eval_write src/rewards/events.ts <<'EOF'
export const LedgerEventType = {
  RewardGranted: "reward_granted",
  RewardReversed: "reward_reversed",
  PromoCredited: "promo_credited",
} as const;

export type LedgerEventType = (typeof LedgerEventType)[keyof typeof LedgerEventType];

export class LedgerEvent {
  readonly type: LedgerEventType;
  readonly userId: string;
  readonly amount: number;

  constructor(fields: { type: LedgerEventType; userId: string; amount: number }) {
    this.type = fields.type;
    this.userId = fields.userId;
    this.amount = fields.amount;
  }
}

export class RewardReversed extends LedgerEvent {
  constructor(userId: string, amount: number) {
    if (amount <= 0) throw new Error("amount must be positive");
    super({ type: LedgerEventType.RewardReversed, userId, amount });
  }
}
EOF

eval_write src/rewards/ledger.ts <<'EOF'
import type { LedgerEvent, LedgerEventType } from "./events.ts";

export type Posting = { type: LedgerEventType; userId: string; cents: number };

const SIGN: Record<LedgerEventType, 1 | -1> = {
  reward_granted: 1,
  promo_credited: 1,
  reward_reversed: -1,
};

export class Ledger {
  private readonly postings: Posting[] = [];

  post(event: LedgerEvent): Posting {
    if (!Number.isInteger(event.amount) || event.amount <= 0) {
      throw new Error(
        `ledger rejected ${event.type} for ${event.userId}: amount must be a positive whole number of cents, got ${event.amount}`,
      );
    }
    const posting = { type: event.type, userId: event.userId, cents: SIGN[event.type] * event.amount };
    this.postings.push(posting);
    return posting;
  }

  balance(userId: string): number {
    return this.postings.filter((p) => p.userId === userId).reduce((sum, p) => sum + p.cents, 0);
  }
}
EOF

eval_write src/rewards/programs.ts <<'EOF'
export type Program = { id: string; sponsorId: string; paused: boolean };
EOF

eval_write src/rewards/ledger.test.ts <<'EOF'
import { test } from "node:test";
import assert from "node:assert/strict";
import { RewardReversed } from "./events.ts";
import { Ledger } from "./ledger.ts";

test("a reversal debits the user", () => {
  const ledger = new Ledger();
  ledger.post(new RewardReversed("u1", 300));
  assert.equal(ledger.balance("u1"), -300);
});
EOF
eval_commit "feat: rewards ledger with reversals"

git checkout -q -b feat/referral-rewards

python3 - <<'PY'
from pathlib import Path
p = Path("src/rewards/events.ts")
p.write_text(p.read_text() + '''
export class RewardGranted extends LedgerEvent {
  constructor(userId: string, amount: number) {
    if (amount <= 0) throw new Error("amount must be positive");
    super({ type: LedgerEventType.RewardGranted, userId, amount });
  }
}
''')
PY

eval_write src/rewards/grant.ts <<'EOF'
import { LedgerEvent, LedgerEventType, RewardGranted } from "./events.ts";
import type { Ledger } from "./ledger.ts";
import type { Program } from "./programs.ts";

export type RewardKind = "referral" | "streak" | "promo";

export type GrantRequest = { program: Program; kind: RewardKind; userId: string; amount: number };

export class ProgramPausedError extends Error {}

export function grantReward(ledger: Ledger, req: GrantRequest): void {
  // covers R4 from the plan
  if (req.program.paused) {
    throw new ProgramPausedError(`program ${req.program.id} is paused; no ${req.kind} grant for ${req.userId}`);
  }
  if (req.kind === "promo") return;
  for (const event of eventsFor(req)) {
    // see ledger.ts line 88
    ledger.post(event);
  }
}

// every new reward type also needs a row in reward_kinds
export function eventsFor(req: GrantRequest): LedgerEvent[] {
  switch (req.kind) {
    case "referral":
      // both sides of a referral are rewarded, per Sam in #backend
      // TODO(ENG-123): cap referral grants per sponsor once the fraud rules land
      return [new RewardGranted(req.userId, req.amount), new RewardGranted(req.program.sponsorId, req.amount)];
    case "streak":
      // temporary, remove after 2027-02
      return [new RewardGranted(req.userId, req.amount * 2)];
    case "promo":
      return [new LedgerEvent({ type: LedgerEventType.PromoCredited, userId: req.userId, amount: req.amount })];
  }
}
EOF

eval_write src/jobs/promo-batch.ts <<'EOF'
import { eventsFor, type GrantRequest } from "../rewards/grant.ts";
import type { Ledger } from "../rewards/ledger.ts";

// Nightly: posts every promo grant queued during the day.
export function runPromoBatch(ledger: Ledger, queued: readonly GrantRequest[]): number {
  let posted = 0;
  for (const req of queued) {
    if (req.kind !== "promo" || req.program.paused) continue;
    for (const event of eventsFor(req)) {
      ledger.post(event);
      posted++;
    }
  }
  return posted;
}
EOF

eval_write src/rewards/grant.test.ts <<'EOF'
import { test } from "node:test";
import assert from "node:assert/strict";
import { grantReward } from "./grant.ts";
import { Ledger } from "./ledger.ts";

const program = { id: "p1", sponsorId: "sponsor", paused: false };

test("a referral rewards both sides", () => {
  const ledger = new Ledger();
  grantReward(ledger, { program, kind: "referral", userId: "u1", amount: 500 });
  assert.equal(ledger.balance("u1"), 500);
  assert.equal(ledger.balance("sponsor"), 500);
});
EOF
eval_commit "feat: referral, streak and promo grants"
eval_origin
eval_gh
