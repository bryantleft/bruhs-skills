# hookshot

Sends signed webhooks to customer endpoints.

Every request is a JSON `POST` with:

- `X-Hookshot-Timestamp`: unix seconds when the request was sent
- `X-Hookshot-Signature`: `v1=` + hex HMAC-SHA256 of `"<timestamp>.<body>"` with the
  endpoint's secret (`sign` / `verify` in `src/signature.ts`)
- `Idempotency-Key`: a UUID identifying the delivery

Receivers verify the signature and reject timestamps more than 5 minutes old.

## Delivery and retries

`deliver(url, event, { secret })` POSTs the event and retries failures (non-2xx responses
and network errors) with exponential backoff: 500ms before the first retry, doubling each
time, with jitter. It gives up after `maxAttempts` (default 5) and returns
`{ delivered, attempts, status, error }`.

```sh
npm test
npm run typecheck
```
