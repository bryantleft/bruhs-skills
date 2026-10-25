import type { Balance } from "./balances";

export type Payment = {
  from: string;
  to: string;
  amountCents: number;
};

/**
 * Payments that leave everyone at zero. Exact matches (one person owes precisely what
 * another is owed) are paired first; the rest goes largest debtor -> largest creditor,
 * which takes at most (people not square - 1) payments.
 */
export function settleUp(balances: Balance[]): Payment[] {
  const debtors = balances.filter((b) => b.cents < 0).map((b) => ({ id: b.memberId, cents: -b.cents }));
  const creditors = balances.filter((b) => b.cents > 0).map((b) => ({ id: b.memberId, cents: b.cents }));
  const payments: Payment[] = [];

  for (const d of debtors) {
    const match = creditors.find((c) => c.cents === d.cents);
    if (match) {
      payments.push({ from: d.id, to: match.id, amountCents: d.cents });
      d.cents = 0;
      match.cents = 0;
    }
  }

  for (;;) {
    const d = debtors.filter((x) => x.cents > 0).sort((a, b) => b.cents - a.cents)[0];
    const c = creditors.filter((x) => x.cents > 0).sort((a, b) => b.cents - a.cents)[0];
    if (!d || !c) break;
    const amount = Math.min(d.cents, c.cents);
    payments.push({ from: d.id, to: c.id, amountCents: amount });
    d.cents -= amount;
    c.cents -= amount;
  }
  return payments;
}
