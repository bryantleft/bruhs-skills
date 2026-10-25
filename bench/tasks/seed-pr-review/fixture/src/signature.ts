import { createHmac, timingSafeEqual } from "node:crypto";

/** Header value for a payload sent at `timestamp` (unix seconds): `v1=<hex hmac-sha256>`. */
export function sign(secret: string, timestamp: number, body: string): string {
  const mac = createHmac("sha256", secret).update(`${timestamp}.${body}`).digest("hex");
  return `v1=${mac}`;
}

/**
 * What receivers run (and what our docs show): the signature matches and the timestamp is
 * within `toleranceS` of `nowS`, so a captured request can't be replayed later.
 */
export function verify(
  secret: string,
  header: string,
  timestamp: number,
  body: string,
  nowS: number,
  toleranceS = 300,
): boolean {
  if (Math.abs(nowS - timestamp) > toleranceS) return false;
  const expected = Buffer.from(sign(secret, timestamp, body));
  const actual = Buffer.from(header);
  return expected.length === actual.length && timingSafeEqual(expected, actual);
}
