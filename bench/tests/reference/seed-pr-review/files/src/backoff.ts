export type BackoffOptions = {
  /** Delay before the first retry, before jitter. */
  baseMs: number;
  /** Upper bound on any delay. Default 30s. */
  maxMs?: number;
  /** Returns [0, 1); injectable for tests. */
  random?: () => number;
};

export const DEFAULT_MAX_DELAY_MS = 30_000;

/**
 * Delay before retry number `retry` (1 = the first retry): `baseMs * 2^(retry - 1)`, capped
 * at `maxMs`, with "equal jitter" (half of it fixed, half random) so endpoints that failed
 * together don't all get retried at the same instant.
 */
export function backoffDelay(
  retry: number,
  { baseMs, maxMs = DEFAULT_MAX_DELAY_MS, random = Math.random }: BackoffOptions,
): number {
  const exp = Math.min(baseMs * 2 ** (retry - 1), maxMs);
  return Math.round(exp / 2 + random() * (exp / 2));
}
