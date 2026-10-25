import { readFile } from "node:fs/promises";

export interface Entry {
  start: Date;
  end: Date;
  project: string;
  note: string;
}

interface RawEntry {
  start?: unknown;
  end?: unknown;
  project?: unknown;
  note?: unknown;
}

function toDate(value: unknown, field: string, index: number): Date {
  const date = typeof value === "string" ? new Date(value) : new Date(NaN);
  if (Number.isNaN(date.getTime())) {
    throw new Error(`entry ${index}: invalid ${field}`);
  }
  return date;
}

export function parseEntries(raw: unknown): Entry[] {
  if (!Array.isArray(raw)) {
    throw new Error("log must be a JSON array of entries");
  }
  return raw.map((item: RawEntry, index) => {
    const start = toDate(item.start, "start", index);
    const end = toDate(item.end, "end", index);
    if (end <= start) {
      throw new Error(`entry ${index}: end is not after start`);
    }
    if (typeof item.project !== "string" || item.project === "") {
      throw new Error(`entry ${index}: project is required`);
    }
    return {
      start,
      end,
      project: item.project,
      note: typeof item.note === "string" ? item.note : "",
    };
  });
}

export async function loadEntries(path: string): Promise<Entry[]> {
  const text = await readFile(path, "utf8");
  return parseEntries(JSON.parse(text));
}
