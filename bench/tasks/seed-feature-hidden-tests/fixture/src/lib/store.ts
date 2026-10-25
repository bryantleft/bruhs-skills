import { readFileSync } from "node:fs";
import path from "node:path";
import type { Group } from "./types";

/** The groups file: $TABBY_DATA, else data/groups.json. Read on every call so edits show up without a restart. */
function dataFile(): string {
  return process.env.TABBY_DATA ?? path.join(process.cwd(), "data", "groups.json");
}

export function listGroups(): Group[] {
  const raw = JSON.parse(readFileSync(/*turbopackIgnore: true*/ dataFile(), "utf8")) as { groups: Group[] };
  return raw.groups.map((g) => ({ ...g, repayments: g.repayments ?? [] }));
}

export function getGroup(id: string): Group | undefined {
  return listGroups().find((g) => g.id === id);
}
