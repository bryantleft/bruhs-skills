import { describe, expect, it } from "vitest";
import { PLANS, formatPrice, yearlyCents } from "../src/plans";

describe("formatPrice", () => {
  it("formats whole and fractional dollars", () => {
    expect(formatPrice(2400)).toBe("$24");
    expect(formatPrice(2450)).toBe("$24.50");
  });

  it("says Free for zero", () => {
    expect(formatPrice(0)).toBe("Free");
  });
});

describe("plans", () => {
  it("are priced 0 / 24 / 99 a month", () => {
    expect(PLANS.map((p) => p.monthlyCents)).toEqual([0, 2400, 9900]);
  });

  it("bill yearly as ten months", () => {
    expect(yearlyCents(2400)).toBe(24000);
  });
});
