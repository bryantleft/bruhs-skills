import type { Entry } from "./entries.js";
import { dayKey, endOfDay, hoursBetween } from "./util/dates.js";

export type GroupBy = "project" | "day";

export interface ReportRow {
  key: string;
  hours: number;
  entries: number;
}

export interface Report {
  groupBy: GroupBy;
  rows: ReportRow[];
  totalHours: number;
  totalEntries: number;
}

export interface ReportOptions {
  from?: Date;
  to?: Date;
  groupBy?: GroupBy;
}

export function buildReport(entries: Entry[], options: ReportOptions = {}): Report {
  const groupBy = options.groupBy ?? "project";
  const until = options.to ? endOfDay(options.to) : undefined;
  const selected = entries.filter(
    (e) => (!options.from || e.start >= options.from) && (!until || e.start <= until),
  );

  const groups = new Map<string, ReportRow>();
  for (const entry of selected) {
    const key = groupBy === "project" ? entry.project : dayKey(entry.start);
    const row = groups.get(key) ?? { key, hours: 0, entries: 0 };
    row.hours += hoursBetween(entry.start, entry.end);
    row.entries += 1;
    groups.set(key, row);
  }

  const rows = [...groups.values()].sort((a, b) =>
    groupBy === "day" ? a.key.localeCompare(b.key) : b.hours - a.hours,
  );
  return {
    groupBy,
    rows,
    totalHours: rows.reduce((sum, r) => sum + r.hours, 0),
    totalEntries: selected.length,
  };
}
