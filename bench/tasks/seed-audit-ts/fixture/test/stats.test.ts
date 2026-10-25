import { describe, expect, it } from "vitest";
import { summarize, topBy } from "../src/lib/stats.js";

describe("summarize", () => {
  it("handles no orders", () => {
    expect(summarize([])).toEqual({ orders: 0, revenueCents: 0, averageCents: 0, medianCents: 0 });
  });

  it("sums revenue and averages", () => {
    const s = summarize([300, 100, 200]);
    expect(s.orders).toBe(3);
    expect(s.revenueCents).toBe(600);
    expect(s.averageCents).toBe(200);
    expect(s.medianCents).toBe(200);
  });
});

describe("topBy", () => {
  it("keeps the n largest", () => {
    const rows = [{ v: 1 }, { v: 5 }, { v: 3 }];
    expect(topBy(rows, (r) => r.v, 2)).toEqual([{ v: 5 }, { v: 3 }]);
  });
});
