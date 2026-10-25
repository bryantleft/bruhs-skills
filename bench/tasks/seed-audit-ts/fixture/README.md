# orderdesk-api

Small orders API behind the Orderdesk storefront. Express 4 + the built-in `node:sqlite`
driver, no ORM.

## Running

```sh
npm install
npm run build
ADMIN_KEY=... npm start
```

Environment:

| Variable | Default | |
|---|---|---|
| `PORT` | `3000` | |
| `DB_PATH` | `orderdesk.db` | `:memory:` works for local poking around |
| `ADMIN_KEY` | (required) | sent as `x-admin-key` on `/admin/*` |
| `PAYMENTS_URL` | `http://localhost:4010` | payments service base URL |
| `WEBHOOK_URL` | (unset) | order events are POSTed here when set |
| `SESSION_TTL_HOURS` | `72` | |

## API

All `/orders` and `/me` routes need `Authorization: Bearer <token>` from `POST /login`.

- `POST /signup` `{email, name, password}`
- `POST /login` `{email, password}` -> `{token}`
- `GET /me`, `GET /me/stats`
- `GET /products`
- `GET /orders?page=1&pageSize=20&sort=created|total&dir=asc|desc` (pages start at 1)
- `GET /orders/search?q=...` (matches the order note)
- `GET /orders/:id`
- `POST /orders` `{items: [{productId, quantity}], note?}`
- `GET /admin/stats`, `GET /admin/orders/export?since=YYYY-MM-DD`,
  `POST /admin/products/import` (CSV body), `POST /admin/orders/:id/refund`

## Tests

```sh
npm test
```
