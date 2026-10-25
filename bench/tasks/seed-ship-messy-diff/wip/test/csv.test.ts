import { describe, expect, it } from "vitest";
import { main } from "../src/cli.js";
import { renderCsv } from "../src/format/csv.js";

describe("renderCsv", () => {
  it("writes a header and one row per group", () => {
    const out = renderCsv({
      groupBy: "project",
      rows: [
        { key: "billing", hours: 12.5, entries: 5 },
        { key: "onboarding", hours: 6.25, entries: 3 },
      ],
      totalHours: 18.75,
      totalEntries: 8,
    });
    expect(out).toBe("project,hours,entries\r\nbilling,12.50,5\r\nonboarding,6.25,3\r\n");
  });

  it("quotes cells with commas, quotes and newlines", () => {
    const out = renderCsv({
      groupBy: "project",
      rows: [{ key: 'ops, "infra"', hours: 1, entries: 1 }],
      totalHours: 1,
      totalEntries: 1,
    });
    expect(out.split("\r\n")[1]).toBe('"ops, ""infra""",1.00,1');
  });
});

describe("tally report --format", () => {
  it("prints csv", async () => {
    const out = await main(["report", "examples/october.json", "--format", "csv", "--by", "day"]);
    expect(out.split("\r\n")[0]).toBe("day,hours,entries");
    expect(out.split("\r\n")[1]).toBe("2026-10-01,3.25,2");
  });

  it("rejects unknown formats", async () => {
    await expect(main(["report", "examples/october.json", "--format", "xml"])).rejects.toThrow(
      /--format/,
    );
  });
});
