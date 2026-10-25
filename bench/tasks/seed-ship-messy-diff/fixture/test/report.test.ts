import { describe, expect, it } from "vitest";
import { parseEntries } from "../src/entries.js";
import { buildReport } from "../src/report.js";
import { parseDay } from "../src/util/dates.js";

const entries = parseEntries([
  { start: "2026-10-01T09:00:00Z", end: "2026-10-01T11:00:00Z", project: "billing" },
  { start: "2026-10-01T13:00:00Z", end: "2026-10-01T14:00:00Z", project: "onboarding" },
  { start: "2026-10-03T09:00:00Z", end: "2026-10-03T12:00:00Z", project: "onboarding" },
  { start: "2026-10-05T09:00:00Z", end: "2026-10-05T09:30:00Z", project: "billing" },
]);

describe("buildReport", () => {
  it("groups by project, biggest first", () => {
    const report = buildReport(entries);
    expect(report.rows.map((r) => [r.key, r.hours, r.entries])).toEqual([
      ["onboarding", 4, 2],
      ["billing", 2.5, 2],
    ]);
    expect(report.totalHours).toBe(6.5);
    expect(report.totalEntries).toBe(4);
  });

  it("groups by day in date order", () => {
    const report = buildReport(entries, { groupBy: "day" });
    expect(report.rows.map((r) => r.key)).toEqual(["2026-10-01", "2026-10-03", "2026-10-05"]);
  });

  it("filters by inclusive day range", () => {
    const report = buildReport(entries, { from: parseDay("2026-10-03"), to: parseDay("2026-10-05") });
    expect(report.totalEntries).toBe(2);
    expect(report.totalHours).toBe(3.5);
  });
});

describe("parseEntries", () => {
  it("rejects bad entries", () => {
    expect(() => parseEntries({})).toThrow(/array/);
    expect(() => parseEntries([{ start: "x", end: "y", project: "p" }])).toThrow(/invalid start/);
    expect(() =>
      parseEntries([{ start: "2026-10-01T10:00:00Z", end: "2026-10-01T09:00:00Z", project: "p" }]),
    ).toThrow(/end is not after start/);
  });
});
