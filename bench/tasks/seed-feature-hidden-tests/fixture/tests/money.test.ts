import { describe, expect, it } from "vitest";
import { formatCents, splitCents } from "@/lib/money";

describe("formatCents", () => {
  it("formats dollars with cents and thousands separators", () => {
    expect(formatCents(0)).toBe("$0.00");
    expect(formatCents(1250)).toBe("$12.50");
    expect(formatCents(123456)).toBe("$1,234.56");
  });

  it("puts the sign before the dollar sign", () => {
    expect(formatCents(-300)).toBe("-$3.00");
  });
});

describe("splitCents", () => {
  it("splits evenly when it can", () => {
    expect(splitCents(900, 3)).toEqual([300, 300, 300]);
  });

  it("gives the leftover cents to the first shares", () => {
    expect(splitCents(1000, 3)).toEqual([334, 333, 333]);
    expect(splitCents(2350, 4)).toEqual([588, 588, 587, 587]);
  });

  it("always adds back up to the total", () => {
    for (const [total, parts] of [[1, 3], [4199, 4], [13725, 4], [99, 7]]) {
      expect(splitCents(total, parts).reduce((a, b) => a + b, 0)).toBe(total);
    }
  });

  it("rejects fractional cents and empty splits", () => {
    expect(() => splitCents(10.5, 2)).toThrow(RangeError);
    expect(() => splitCents(100, 0)).toThrow(RangeError);
  });
});
