import { randomUUID } from "node:crypto";
import { backoffDelay } from "./backoff";
import { sign } from "./signature";
import type { WebhookEvent } from "./types";

export type DeliveryOptions = {
  /** The endpoint's signing secret. */
  secret: string;
  /** Total tries, including the first. Default 5. */
  maxAttempts?: number;
  /** Delay before the first retry; doubles on each retry after that. Default 500ms. */
  baseDelayMs?: number;
  /** Per-request timeout. Default 10s. */
  timeoutMs?: number;
  // injectable for tests
  fetch?: typeof fetch;
  sleep?: (ms: number) => Promise<void>;
  random?: () => number;
  now?: () => Date;
};

export type DeliveryResult = {
  delivered: boolean;
  /** Requests made. */
  attempts: number;
  /** HTTP status of the last response, if there was one. */
  status?: number;
  /** The last network error, if the last attempt didn't get a response. */
  error?: string;
};

const defaultSleep = (ms: number) => new Promise<void>((resolve) => setTimeout(resolve, ms));

/**
 * POST `event` to `url`, signed, retrying failures with exponential backoff. Every attempt
 * is signed with a fresh timestamp, so a retry is never rejected as stale.
 */
export async function deliver(url: string, event: WebhookEvent, options: DeliveryOptions): Promise<DeliveryResult> {
  const {
    secret,
    maxAttempts = 5,
    baseDelayMs = 500,
    timeoutMs = 10_000,
    fetch: doFetch = fetch,
    sleep = defaultSleep,
    random = Math.random,
    now = () => new Date(),
  } = options;
  const body = JSON.stringify(event);
  const idempotencyKey = randomUUID();
  let status: number | undefined;
  let error: string | undefined;

  for (let attempt = 0; attempt <= maxAttempts; attempt++) {
    if (attempt > 0) {
      await sleep(backoffDelay(attempt, { baseMs: baseDelayMs, random }));
    }
    const timestamp = Math.floor(now().getTime() / 1000);
    try {
      const res = await doFetch(url, {
        method: "POST",
        headers: {
          "content-type": "application/json",
          "idempotency-key": idempotencyKey,
          "x-hookshot-timestamp": String(timestamp),
          "x-hookshot-signature": sign(secret, timestamp, body),
        },
        body,
        signal: AbortSignal.timeout(timeoutMs),
      });
      status = res.status;
      error = undefined;
      if (res.ok) {
        return { delivered: true, attempts: attempt + 1, status };
      }
    } catch (e) {
      status = undefined;
      error = e instanceof Error ? e.message : String(e);
    }
  }
  return { delivered: false, attempts: maxAttempts + 1, status, error };
}
