# hookshot

Sends signed webhooks to customer endpoints.

Every request is a JSON `POST` with:

- `X-Hookshot-Timestamp`: unix seconds when the request was sent
- `X-Hookshot-Signature`: `v1=` + hex HMAC-SHA256 of `"<timestamp>.<body>"` with the
  endpoint's secret (`sign` / `verify` in `src/signature.ts`)

Receivers verify the signature and reject timestamps more than 5 minutes old.

```sh
npm test
npm run typecheck
```
