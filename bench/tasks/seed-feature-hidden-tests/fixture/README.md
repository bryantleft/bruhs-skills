# tabby

Tracks shared expenses for trips and flats: who paid for what, and where everyone stands.

Groups live in `data/groups.json` (or the file in `$TABBY_DATA`). The file is read on every
request, so edits show up without a restart.

- Amounts are integer cents everywhere.
- An expense is split evenly between `splitAmong`; leftover cents go to the first people
  listed (`splitCents` in `src/lib/money.ts`).
- A repayment is money one member already sent another.
- A balance > 0 means the group owes that person; < 0 means they owe the group.

## API

- `GET /api/groups`: every group with its total spend
- `GET /api/groups/<id>/balances`: `{ balances: [{ memberId, name, cents }] }`, 404 for an
  unknown group

## Scripts

```sh
npm run dev         # http://localhost:3000
npm test            # vitest
npm run typecheck
npm run lint
npm run build
```
