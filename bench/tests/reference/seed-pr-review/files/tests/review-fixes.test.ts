import { describe, expect, it } from "vitest";
import { backoffDelay } from "../src/backoff";
import { deliver } from "../src/deliver";
import type { WebhookEvent } from "../src/types";

const event: WebhookEvent = { id: "evt_r", type: "invoice.paid", createdAt: "2026-10-20T12:00:00.000Z", data: {} };

function fetchSeq(...responses: Response[]) {
  let i = 0;
  const calls: RequestInit[] = [];
  const fn = async (_url: string | URL | Request, init?: RequestInit) => {
    calls.push(init ?? {});
    return responses[Math.min(i++, responses.length - 1)].clone();
  };
  return { fetch: fn as typeof fetch, calls };
}

describe("review fixes", () => {
  it("caps the backoff", () => {
    expect(backoffDelay(10, { baseMs: 500, random: () => 0.999999 })).toBe(30_000);
    expect(backoffDelay(10, { baseMs: 500, maxMs: 1_000, random: () => 0 })).toBe(500);
  });

  it("doesn't retry a 404", async () => {
    const { fetch, calls } = fetchSeq(new Response(null, { status: 404 }));
    const result = await deliver("https://x.test", event, { secret: "s", fetch, sleep: async () => {} });
    expect(result).toEqual({ delivered: false, attempts: 1, status: 404 });
    expect(calls).toHaveLength(1);
  });

  it("waits for Retry-After", async () => {
    const waits: number[] = [];
    const { fetch } = fetchSeq(new Response(null, { status: 429, headers: { "retry-after": "5" } }), new Response(null, { status: 200 }));
    await deliver("https://x.test", event, { secret: "s", fetch, sleep: async (ms) => void waits.push(ms) });
    expect(waits[0]).toBeGreaterThanOrEqual(5_000);
  });

  it("makes exactly maxAttempts requests", async () => {
    const { fetch, calls } = fetchSeq(new Response(null, { status: 503 }));
    const result = await deliver("https://x.test", event, { secret: "s", fetch, sleep: async () => {}, maxAttempts: 3 });
    expect(calls).toHaveLength(3);
    expect(result.attempts).toBe(3);
  });

  it("keeps one Idempotency-Key across retries", async () => {
    const { fetch, calls } = fetchSeq(new Response(null, { status: 503 }), new Response(null, { status: 200 }));
    await deliver("https://x.test", event, { secret: "s", fetch, sleep: async () => {} });
    const keys = calls.map((c) => new Headers(c.headers).get("idempotency-key"));
    expect(keys[0]).toBe(keys[1]);
  });
});
