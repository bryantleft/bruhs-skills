# feat(report): add `--format csv` to `tally report`

## What

`tally report` gets a `--format table|csv` option (default `table`, so nothing changes for
existing use).

`--format csv` prints RFC 4180 CSV for spreadsheets:

- a header row (`project,hours,entries` or `day,hours,entries`), then one row per group;
- no total row, so the column sums cleanly;
- cells containing commas, quotes or newlines are quoted, with `"` doubled;
- CRLF line endings.

Unknown formats fail with `--format must be "table" or "csv"`.

## Changes

- `src/format/csv.ts`: new `renderCsv(report)`.
- `src/cli.ts`: `--format` option, picks the renderer.
- `README.md`: documents the flag.
- `test/csv.test.ts`: renderer output and quoting, `--format csv` end to end, unknown format.

## Testing

`npm test` and `npm run typecheck` pass.

```sh
npm run -s tally -- report examples/october.json --format csv
```
