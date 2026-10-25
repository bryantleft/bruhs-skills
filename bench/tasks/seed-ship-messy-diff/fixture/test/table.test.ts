import { describe, expect, it } from "vitest";
import { renderTable } from "../src/format/table.js";

describe("renderTable", () => {
  it("aligns columns and adds a total", () => {
    const out = renderTable({
      groupBy: "project",
      rows: [
        { key: "billing", hours: 12.5, entries: 5 },
        { key: "onboarding", hours: 6.25, entries: 3 },
      ],
      totalHours: 18.75,
      totalEntries: 8,
    });
    expect(out).toBe(
      [
        "project     hours  entries",
        "----------  -----  -------",
        "billing     12.50        5",
        "onboarding   6.25        3",
        "----------  -----  -------",
        "total       18.75        8",
        "",
      ].join("\n"),
    );
  });
});
