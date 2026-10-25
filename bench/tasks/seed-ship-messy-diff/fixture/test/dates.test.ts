import { describe, expect, it } from "vitest";
import { dayKey, endOfDay, formatHours, hoursBetween, parseDay } from "../src/util/dates.js";

describe("dates", () => {
  it("parses calendar days in UTC", () => {
    expect(parseDay("2026-10-01").toISOString()).toBe("2026-10-01T00:00:00.000Z");
    expect(() => parseDay("2026-02-30")).toThrow(/not a real date/);
    expect(() => parseDay("10/01/2026")).toThrow(/expected a date/);
  });

  it("finds the end of a day", () => {
    expect(endOfDay(parseDay("2026-10-01")).toISOString()).toBe("2026-10-01T23:59:59.999Z");
  });

  it("measures and formats hours", () => {
    const h = hoursBetween(new Date("2026-10-01T09:00:00Z"), new Date("2026-10-01T11:15:00Z"));
    expect(h).toBe(2.25);
    expect(formatHours(h)).toBe("2.25");
    expect(dayKey(new Date("2026-10-01T23:00:00Z"))).toBe("2026-10-01");
  });
});
