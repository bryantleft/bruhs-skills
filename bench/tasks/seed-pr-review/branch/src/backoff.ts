export type BackoffOptions = {
  /** Delay before the first retry, before jitter. */
  baseMs: number;
  /** Returns [0, 1); injectable for tests. */
  random?: () => number;
};

/**
 * Delay before retry number `retry` (1 = the first retry): `baseMs * 2^(retry - 1)`, with
 * "equal jitter" (half of it fixed, half random) so endpoints that failed together don't
 * all get retried at the same instant.
 */
export function backoffDelay(retry: number, { baseMs, random = Math.random }: BackoffOptions): number {
  const exp = baseMs * 2 ** (retry - 1);
  return Math.round(exp / 2 + random() * (exp / 2));
}
