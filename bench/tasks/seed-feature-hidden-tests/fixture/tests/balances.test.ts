import { describe, expect, it } from "vitest";
import { computeBalances, totalSpent } from "@/lib/balances";
import type { Group } from "@/lib/types";

const group = (overrides: Partial<Group>): Group => ({
  id: "g",
  name: "G",
  members: [
    { id: "a", name: "A" },
    { id: "b", name: "B" },
    { id: "c", name: "C" },
  ],
  expenses: [],
  repayments: [],
  ...overrides,
});

const cents = (g: Group) => Object.fromEntries(computeBalances(g).map((b) => [b.memberId, b.cents]));

describe("computeBalances", () => {
  it("credits the payer and debits everyone in the split", () => {
    const g = group({
      expenses: [{ id: "e", description: "x", paidBy: "a", amountCents: 900, date: "", splitAmong: ["a", "b", "c"] }],
    });
    expect(cents(g)).toEqual({ a: 600, b: -300, c: -300 });
  });

  it("handles a payer who isn't part of the split", () => {
    const g = group({
      expenses: [{ id: "e", description: "x", paidBy: "c", amountCents: 1000, date: "", splitAmong: ["a", "b"] }],
    });
    expect(cents(g)).toEqual({ a: -500, b: -500, c: 1000 });
  });

  it("counts repayments", () => {
    const g = group({
      expenses: [{ id: "e", description: "x", paidBy: "a", amountCents: 900, date: "", splitAmong: ["a", "b", "c"] }],
      repayments: [{ id: "r", from: "b", to: "a", amountCents: 300, date: "" }],
    });
    expect(cents(g)).toEqual({ a: 300, b: 0, c: -300 });
  });

  it("always sums to zero, including leftover cents", () => {
    const g = group({
      expenses: [
        { id: "e1", description: "x", paidBy: "a", amountCents: 1000, date: "", splitAmong: ["a", "b", "c"] },
        { id: "e2", description: "y", paidBy: "b", amountCents: 4199, date: "", splitAmong: ["a", "b", "c"] },
      ],
    });
    expect(computeBalances(g).reduce((s, b) => s + b.cents, 0)).toBe(0);
  });

  it("rejects expenses from people who aren't in the group", () => {
    const g = group({
      expenses: [{ id: "e", description: "x", paidBy: "zz", amountCents: 100, date: "", splitAmong: ["a"] }],
    });
    expect(() => computeBalances(g)).toThrow(/unknown member zz/);
  });
});

describe("totalSpent", () => {
  it("adds up every expense, ignoring repayments", () => {
    const g = group({
      expenses: [
        { id: "e1", description: "x", paidBy: "a", amountCents: 1000, date: "", splitAmong: ["a"] },
        { id: "e2", description: "y", paidBy: "b", amountCents: 250, date: "", splitAmong: ["a", "b"] },
      ],
      repayments: [{ id: "r", from: "b", to: "a", amountCents: 300, date: "" }],
    });
    expect(totalSpent(g)).toBe(1250);
  });
});
