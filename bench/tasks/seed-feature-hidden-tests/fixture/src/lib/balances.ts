import { splitCents } from "./money";
import type { Group } from "./types";

export type Balance = {
  memberId: string;
  name: string;
  /** > 0: the group owes them; < 0: they owe the group. */
  cents: number;
};

/**
 * Where each member stands once every expense and repayment is counted. The balances of
 * a group always add up to zero.
 */
export function computeBalances(group: Group): Balance[] {
  const net = new Map(group.members.map((m) => [m.id, 0]));
  const add = (memberId: string, cents: number) => {
    const current = net.get(memberId);
    if (current === undefined) {
      throw new Error(`group ${group.id}: unknown member ${memberId}`);
    }
    net.set(memberId, current + cents);
  };

  for (const expense of group.expenses) {
    add(expense.paidBy, expense.amountCents);
    const shares = splitCents(expense.amountCents, expense.splitAmong.length);
    expense.splitAmong.forEach((memberId, i) => add(memberId, -shares[i]));
  }
  for (const repayment of group.repayments) {
    add(repayment.from, repayment.amountCents);
    add(repayment.to, -repayment.amountCents);
  }

  return group.members.map((m) => ({ memberId: m.id, name: m.name, cents: net.get(m.id) ?? 0 }));
}

export function totalSpent(group: Group): number {
  return group.expenses.reduce((sum, e) => sum + e.amountCents, 0);
}
