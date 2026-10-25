import { describe, expect, it } from "vitest";
import { settleUp } from "@/lib/settle";

const b = (cents: Record<string, number>) =>
  Object.entries(cents).map(([memberId, c]) => ({ memberId, name: memberId, cents: c }));

describe("settleUp", () => {
  it("is empty when everyone is square", () => {
    expect(settleUp(b({ a: 0, b: 0 }))).toEqual([]);
  });

  it("pairs exact matches", () => {
    expect(settleUp(b({ a: 1000, b: 300, c: -300, d: -1000 }))).toEqual([
      { from: "c", to: "b", amountCents: 300 },
      { from: "d", to: "a", amountCents: 1000 },
    ]);
  });

  it("zeroes every balance", () => {
    const balances = b({ a: 700, b: 451, c: -333, d: -818, e: 0 });
    const net = new Map(balances.map((x) => [x.memberId, x.cents]));
    for (const p of settleUp(balances)) {
      net.set(p.from, net.get(p.from)! + p.amountCents);
      net.set(p.to, net.get(p.to)! - p.amountCents);
    }
    expect([...net.values()].every((c) => c === 0)).toBe(true);
  });
});
