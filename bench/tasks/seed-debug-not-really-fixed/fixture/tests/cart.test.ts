import { describe, expect, it } from "vitest";
import { SAMPLE_CART, formatCents, totals, type CartItem } from "../src/cart";

const item = (priceCents: number, quantity = 1): CartItem => ({
  sku: `sku-${priceCents}`,
  name: "Thing",
  variant: "",
  priceCents,
  quantity,
  image: "",
});

describe("totals", () => {
  it("adds up the sample cart", () => {
    expect(totals(SAMPLE_CART)).toEqual({
      subtotalCents: 89390,
      shippingCents: 0,
      taxCents: 7375,
      totalCents: 96765,
    });
  });

  it("charges shipping under the free-shipping threshold", () => {
    expect(totals([item(2500, 2)]).shippingCents).toBe(895);
  });

  it("is all zero for an empty cart", () => {
    expect(totals([])).toEqual({ subtotalCents: 0, shippingCents: 0, taxCents: 0, totalCents: 0 });
  });
});

describe("formatCents", () => {
  it("formats dollars", () => {
    expect(formatCents(96765)).toBe("$967.65");
    expect(formatCents(395)).toBe("$3.95");
  });
});
