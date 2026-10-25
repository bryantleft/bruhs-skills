import type { Report } from "../report.js";
import { formatHours } from "../util/dates.js";

function pad(text: string, width: number, align: "left" | "right"): string {
  return align === "left" ? text.padEnd(width) : text.padStart(width);
}

export function renderTable(report: Report): string {
  const header = [report.groupBy, "hours", "entries"];
  const body = report.rows.map((r) => [r.key, formatHours(r.hours), String(r.entries)]);
  const footer = ["total", formatHours(report.totalHours), String(report.totalEntries)];
  const all = [header, ...body, footer];
  const widths = header.map((_, col) => Math.max(...all.map((row) => row[col].length)));
  const line = (row: string[]) =>
    row.map((cell, col) => pad(cell, widths[col], col === 0 ? "left" : "right")).join("  ");
  const rule = widths.map((w) => "-".repeat(w)).join("  ");
  return [line(header), rule, ...body.map(line), rule, line(footer)].join("\n") + "\n";
}
