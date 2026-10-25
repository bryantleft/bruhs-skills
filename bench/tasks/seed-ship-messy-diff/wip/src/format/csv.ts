import type { Report } from "../report.js";
import { formatHours } from "../util/dates.js";

function cell(value: string): string {
  return /[",\r\n]/.test(value) ? `"${value.replace(/"/g, '""')}"` : value;
}

/** RFC 4180 CSV: a header row, then one row per group. No total row, so it sums cleanly. */
export function renderCsv(report: Report): string {
  const rows = [
    [report.groupBy, "hours", "entries"],
    ...report.rows.map((r) => [r.key, formatHours(r.hours), String(r.entries)]),
  ];
  return rows.map((row) => row.map(cell).join(",")).join("\r\n") + "\r\n";
}
