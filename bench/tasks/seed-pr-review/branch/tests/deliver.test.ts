import { describe, expect, it } from "vitest";
import { backoffDelay } from "../src/backoff";
import { deliver } from "../src/deliver";
import { verify } from "../src/signature";
import type { WebhookEvent } from "../src/types";

const event: WebhookEvent = {
  id: "evt_123",
  type: "invoice.paid",
  createdAt: "2026-10-20T12:00:00.000Z",
  data: { invoiceId: "in_9", amountCents: 4200 },
};

type Step = number | Error;

/** A fetch that answers with each step in turn (a status code, or throws an error). */
function fakeFetch(...steps: Step[]) {
  const calls: { url: string; init: RequestInit }[] = [];
  const fn = async (url: string | URL | Request, init?: RequestInit) => {
    calls.push({ url: String(url), init: init ?? {} });
    const step = steps[Math.min(calls.length - 1, steps.length - 1)];
    if (step instanceof Error) throw step;
    return new Response(null, { status: step });
  };
  return { fetch: fn as typeof fetch, calls };
}

const noSleep = async () => {};
const header = (init: RequestInit, name: string) => new Headers(init.headers).get(name);

describe("deliver", () => {
  it("POSTs the signed event once when the endpoint accepts it", async () => {
    const { fetch, calls } = fakeFetch(200);
    const now = () => new Date("2026-10-20T12:00:05Z");
    const result = await deliver("https://example.test/hooks", event, { secret: "whsec_1", fetch, sleep: noSleep, now });

    expect(result).toEqual({ delivered: true, attempts: 1, status: 200 });
    expect(calls).toHaveLength(1);
    const { url, init } = calls[0];
    expect(url).toBe("https://example.test/hooks");
    expect(init.method).toBe("POST");
    expect(JSON.parse(String(init.body))).toEqual(event);
    const ts = Number(header(init, "x-hookshot-timestamp"));
    expect(ts).toBe(1_792_497_605);
    expect(verify("whsec_1", header(init, "x-hookshot-signature")!, ts, String(init.body), ts)).toBe(true);
  });

  it("retries a server error and reports the attempt that worked", async () => {
    const { fetch, calls } = fakeFetch(503, 200);
    const result = await deliver("https://example.test/hooks", event, { secret: "s", fetch, sleep: noSleep });
    expect(result).toEqual({ delivered: true, attempts: 2, status: 200 });
    expect(calls).toHaveLength(2);
  });

  it("retries network errors", async () => {
    const { fetch } = fakeFetch(new Error("ECONNRESET"), 204);
    const result = await deliver("https://example.test/hooks", event, { secret: "s", fetch, sleep: noSleep });
    expect(result.delivered).toBe(true);
  });

  it("gives up eventually and reports the last failure", async () => {
    const { fetch } = fakeFetch(500, 502, 503);
    const result = await deliver("https://example.test/hooks", event, { secret: "s", fetch, sleep: noSleep });
    expect(result.delivered).toBe(false);
    expect(result.status).toBe(503);
  });

  it("waits between attempts", async () => {
    const { fetch } = fakeFetch(503, 503, 200);
    const waits: number[] = [];
    await deliver("https://example.test/hooks", event, {
      secret: "s",
      fetch,
      sleep: async (ms) => void waits.push(ms),
      random: () => 0.5,
    });
    expect(waits).toEqual([375, 750]);
  });
});

describe("backoffDelay", () => {
  it("doubles each retry, jittered within the upper half", () => {
    const low = () => 0;
    const high = () => 0.999999;
    expect([1, 2, 3, 4].map((r) => backoffDelay(r, { baseMs: 500, random: low }))).toEqual([250, 500, 1000, 2000]);
    expect([1, 2, 3, 4].map((r) => backoffDelay(r, { baseMs: 500, random: high }))).toEqual([500, 1000, 2000, 4000]);
  });
});
