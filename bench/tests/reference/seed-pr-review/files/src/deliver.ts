import { randomUUID } from "node:crypto";
import { backoffDelay, DEFAULT_MAX_DELAY_MS } from "./backoff";
import { sign } from "./signature";
import type { WebhookEvent } from "./types";

export type DeliveryOptions = {
  /** The endpoint's signing secret. */
  secret: string;
  /** Total tries, including the first. Default 5. */
  maxAttempts?: number;
  /** Delay before the first retry; doubles on each retry after that. Default 500ms. */
  baseDelayMs?: number;
  /** Ceiling for the backoff delay. Default 30s. */
  maxDelayMs?: number;
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

/** 408, 429 and 5xx may succeed later; any other 4xx will fail the same way again. */
function retryable(status: number): boolean {
  return status === 408 || status === 429 || status >= 500;
}

/** Retry-After as milliseconds from `now`: delta-seconds or an HTTP date. */
function retryAfterMs(value: string | null, now: Date): number | undefined {
  if (!value) return undefined;
  const trimmed = value.trim();
  if (/^\d+$/.test(trimmed)) return Number(trimmed) * 1000;
  const at = Date.parse(trimmed);
  return Number.isNaN(at) ? undefined : Math.max(0, at - now.getTime());
}

/**
 * POST `event` to `url`, signed, retrying failures with exponential backoff. Every attempt
 * is signed with a fresh timestamp, so a retry is never rejected as stale, and carries the
 * same Idempotency-Key, so the receiver can tell a retry from a new delivery.
 */
export async function deliver(url: string, event: WebhookEvent, options: DeliveryOptions): Promise<DeliveryResult> {
  const {
    secret,
    maxAttempts = 5,
    baseDelayMs = 500,
    maxDelayMs = DEFAULT_MAX_DELAY_MS,
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
  let attempts = 0;
  let minWaitMs: number | undefined;

  while (attempts < maxAttempts) {
    if (attempts > 0) {
      const backoff = backoffDelay(attempts, { baseMs: baseDelayMs, maxMs: maxDelayMs, random });
      await sleep(Math.max(backoff, minWaitMs ?? 0));
    }
    attempts++;
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
        return { delivered: true, attempts, status };
      }
      if (!retryable(res.status)) break;
      minWaitMs = retryAfterMs(res.headers.get("retry-after"), now());
    } catch (e) {
      status = undefined;
      error = e instanceof Error ? e.message : String(e);
      minWaitMs = undefined;
    }
  }
  return { delivered: false, attempts, status, error };
}
