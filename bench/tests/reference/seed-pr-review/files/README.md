# hookshot

Sends signed webhooks to customer endpoints.

Every request is a JSON `POST` with:

- `X-Hookshot-Timestamp`: unix seconds when the request was sent
- `X-Hookshot-Signature`: `v1=` + hex HMAC-SHA256 of `"<timestamp>.<body>"` with the
  endpoint's secret (`sign` / `verify` in `src/signature.ts`)
- `Idempotency-Key`: a UUID identifying the delivery (the same on every retry)

Receivers verify the signature and reject timestamps more than 5 minutes old.

## Delivery and retries

`deliver(url, event, { secret })` POSTs the event and retries 408, 429 and 5xx responses
and network errors (any other 4xx fails right away) with exponential backoff: 500ms before
the first retry, doubling each time up to `maxDelayMs` (default 30s), with jitter, and
never sooner than the receiver's `Retry-After`. It gives up after `maxAttempts` tries
(default 5) and returns `{ delivered, attempts, status, error }`.

```sh
npm test
npm run typecheck
```
