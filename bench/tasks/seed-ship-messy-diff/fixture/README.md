# tally

Summarize a time-tracking log from the command line.

```sh
npm install
npm run tally -- report examples/october.json --from 2026-10-01 --to 2026-10-31
```

```
project     hours  entries
----------  -----  -------
billing     12.25        5
onboarding   6.25        3
----------  -----  -------
total       18.50        8
```

## Log format

A JSON array of entries:

```json
[{ "start": "2026-10-02T09:00:00Z", "end": "2026-10-02T11:30:00Z", "project": "billing", "note": "invoices" }]
```

## Commands

`tally report <log> [--from YYYY-MM-DD] [--to YYYY-MM-DD] [--by project|day]`

- `--from` / `--to` are inclusive calendar days (UTC).
- `--by` groups rows by project (default) or by day.

## Development

```sh
npm test
npm run typecheck
```
