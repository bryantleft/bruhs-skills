#!/usr/bin/env node
import { parseArgs } from "node:util";
import { loadEntries } from "./entries.js";
import { renderCsv } from "./format/csv.js";
import { renderTable } from "./format/table.js";
import { buildReport, type GroupBy } from "./report.js";
import { parseDay } from "./util/dates.js";

const USAGE = `usage: tally report <log.json> [--from YYYY-MM-DD] [--to YYYY-MM-DD] [--by project|day] [--format table|csv]`;

const RENDERERS = { table: renderTable, csv: renderCsv };
type Format = keyof typeof RENDERERS;

export async function main(argv: string[]): Promise<string> {
  const { values, positionals } = parseArgs({
    args: argv,
    allowPositionals: true,
    options: {
      from: { type: "string" },
      to: { type: "string" },
      by: { type: "string", default: "project" },
      format: { type: "string", default: "table" },
    },
  });
  console.log("DEBUG report opts", values);
  const [command, logPath] = positionals;
  if (command !== "report" || !logPath) {
    throw new Error(USAGE);
  }
  if (values.by !== "project" && values.by !== "day") {
    throw new Error(`--by must be "project" or "day"`);
  }
  if (!Object.hasOwn(RENDERERS, values.format)) {
    throw new Error(`--format must be "table" or "csv"`);
  }
  const report = buildReport(await loadEntries(logPath), {
    from: values.from ? parseDay(values.from) : undefined,
    to: values.to ? parseDay(values.to) : undefined,
    groupBy: values.by as GroupBy,
  });
  return RENDERERS[values.format as Format](report);
}

if (import.meta.url === `file://${process.argv[1]}`) {
  main(process.argv.slice(2)).then(
    (out) => process.stdout.write(out),
    (err: Error) => {
      process.stderr.write(`${err.message}\n`);
      process.exit(1);
    },
  );
}
