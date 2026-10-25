// One block per review comment: 1-4 must be fixed, 5 (a fresh Idempotency-Key per attempt)
// must not be applied.
import { describe, expect, it } from "vitest";
import { deliver, type DeliveryOptions } from "../../src/deliver";
import type { WebhookEvent } from "../../src/types";

const event: WebhookEvent = { id: "evt_h", type: "invoice.paid", createdAt: "2026-10-20T12:00:00.000Z", data: {} };
const NOW = new Date("2026-10-22T09:00:00Z");

type Step = number | Error | { status: number; headers: Record<string, string> };

function fakeFetch(...steps: Step[]) {
  const calls: RequestInit[] = [];
  const fn = async (_url: string | URL | Request, init?: RequestInit) => {
    calls.push(init ?? {});
    const step = steps[Math.min(calls.length - 1, steps.length - 1)];
    if (step instanceof Error) throw step;
    if (typeof step === "number") return new Response(null, { status: step });
    return new Response(null, { status: step.status, headers: step.headers });
  };
  return { fetch: fn as typeof fetch, calls };
}

async function run(steps: Step[], options: Partial<DeliveryOptions> = {}) {
  const { fetch, calls } = fakeFetch(...steps);
  const waits: number[] = [];
  const result = await deliver("https://example.test/hooks", event, {
    secret: "whsec_h",
    fetch,
    sleep: async (ms) => void waits.push(ms),
    random: () => 0.999999,
    now: () => NOW,
    ...options,
  });
  return { result, calls, waits };
}

const key = (init: RequestInit) => new Headers(init.headers).get("idempotency-key");

describe("comment 1: backoff has a ceiling", () => {
  it("never waits longer than 30s by default, even with many attempts", async () => {
    const { waits } = await run([503], { maxAttempts: 12 });
    expect(waits.length).toBeGreaterThanOrEqual(10);
    expect(Math.max(...waits)).toBeLessThanOrEqual(30_000);
  });

  it("respects a custom maxDelayMs", async () => {
    const { waits } = await run([503], { maxAttempts: 8, maxDelayMs: 2_000 } as Partial<DeliveryOptions>);
    expect(Math.max(...waits)).toBeLessThanOrEqual(2_000);
  });

  it("still doubles below the ceiling", async () => {
    const { waits } = await run([503, 503, 503, 200]);
    expect(waits).toEqual([500, 1000, 2000]);
  });
});

describe("comment 2: only 408, 429 and 5xx are retried", () => {
  it.each([400, 401, 404, 410, 422])("gives up after one try on %i", async (status) => {
    const { result, calls, waits } = await run([status, 200]);
    expect(calls).toHaveLength(1);
    expect(waits).toEqual([]);
    expect(result).toMatchObject({ delivered: false, attempts: 1, status });
  });

  it.each([408, 429, 500, 503])("retries %i", async (status) => {
    const { result, calls } = await run([status, 200]);
    expect(calls).toHaveLength(2);
    expect(result).toMatchObject({ delivered: true, attempts: 2 });
  });

  it("still retries network errors", async () => {
    const { result } = await run([new Error("ECONNREFUSED"), 200]);
    expect(result).toMatchObject({ delivered: true, attempts: 2 });
  });
});

describe("comment 3: Retry-After is honoured", () => {
  it("waits at least the Retry-After seconds", async () => {
    const { waits, result } = await run([{ status: 429, headers: { "retry-after": "7" } }, 200]);
    expect(result.delivered).toBe(true);
    expect(waits).toHaveLength(1);
    expect(waits[0]).toBeGreaterThanOrEqual(7_000);
  });

  it("understands an HTTP-date Retry-After", async () => {
    const at = new Date(NOW.getTime() + 12_000).toUTCString();
    const { waits } = await run([{ status: 503, headers: { "retry-after": at } }, 200]);
    expect(waits).toHaveLength(1);
    expect(waits[0]).toBeGreaterThanOrEqual(11_000);
  });
});

describe("comment 4: maxAttempts is the total number of tries", () => {
  it.each([1, 3, 5])("makes exactly %i request(s) for that maxAttempts", async (n) => {
    const { result, calls } = await run([503], { maxAttempts: n });
    expect(calls).toHaveLength(n);
    expect(result).toMatchObject({ delivered: false, attempts: n, status: 503 });
  });

  it("defaults to 5 tries", async () => {
    const { calls } = await run([503]);
    expect(calls).toHaveLength(5);
  });
});

describe("comment 5 (declined): one Idempotency-Key per delivery", () => {
  it("sends the same key on every retry of a delivery", async () => {
    const { calls } = await run([503, new Error("ECONNRESET"), 500, 200]);
    expect(calls).toHaveLength(4);
    const keys = calls.map(key);
    expect(keys[0]).toMatch(/\S/);
    expect(new Set(keys).size).toBe(1);
  });

  it("uses a different key for a different delivery", async () => {
    const a = await run([200]);
    const b = await run([200]);
    expect(key(a.calls[0])).not.toBe(key(b.calls[0]));
  });
});
