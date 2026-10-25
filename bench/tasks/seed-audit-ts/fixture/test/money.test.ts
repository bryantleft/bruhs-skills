import { describe, expect, it } from "vitest";
import { formatCents, orderTotal, parsePriceCents } from "../src/lib/money.js";

describe("money", () => {
  it("formats cents as dollars", () => {
    expect(formatCents(123456)).toBe("$1,234.56");
    expect(formatCents(5)).toBe("$0.05");
  });

  it("totals line items in integer cents", () => {
    expect(
      orderTotal([
        { unitPriceCents: 1999, quantity: 3 },
        { unitPriceCents: 1, quantity: 1 },
      ]),
    ).toBe(5998);
  });

  it("parses prices without float error", () => {
    expect(parsePriceCents("19.99")).toBe(1999);
    expect(parsePriceCents("$4.5")).toBe(450);
    expect(parsePriceCents("7")).toBe(700);
    expect(() => parsePriceCents("abc")).toThrow();
    expect(() => parsePriceCents("1.234")).toThrow();
  });
});
