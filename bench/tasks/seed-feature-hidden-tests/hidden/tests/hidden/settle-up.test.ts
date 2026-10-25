import { readFileSync } from "node:fs";
import path from "node:path";
import { chromium, type Browser } from "@playwright/test";
import { afterAll, beforeAll, describe, expect, inject, it } from "vitest";

type Payment = { from: string; to: string; amountCents: number };
type RawGroup = {
  id: string;
  members: { id: string; name: string }[];
  expenses: { paidBy: string; amountCents: number; splitAmong: string[] }[];
  repayments?: { from: string; to: string; amountCents: number }[];
};

const baseUrl = inject("baseUrl");
const groups: RawGroup[] = JSON.parse(readFileSync(path.join(__dirname, "groups.json"), "utf8")).groups;

/** Balances computed independently of the app: leftover cents go to the first people in the split. */
function balancesOf(groupId: string): Map<string, number> {
  const g = groups.find((x) => x.id === groupId)!;
  const net = new Map(g.members.map((m) => [m.id, 0]));
  const add = (id: string, c: number) => net.set(id, net.get(id)! + c);
  for (const e of g.expenses) {
    add(e.paidBy, e.amountCents);
    const n = e.splitAmong.length;
    e.splitAmong.forEach((id, i) => add(id, -(Math.floor(e.amountCents / n) + (i < e.amountCents % n ? 1 : 0))));
  }
  for (const r of g.repayments ?? []) {
    add(r.from, r.amountCents);
    add(r.to, -r.amountCents);
  }
  return net;
}

async function settleUp(groupId: string): Promise<{ status: number; body: { payments: Payment[] } }> {
  const res = await fetch(`${baseUrl}/api/groups/${groupId}/settle-up`);
  const text = await res.text();
  let body: { payments: Payment[] };
  try {
    body = JSON.parse(text);
  } catch {
    throw new Error(`settle-up for ${groupId} returned ${res.status}, not JSON: ${text.slice(0, 200)}`);
  }
  return { status: res.status, body };
}

async function payments(groupId: string): Promise<Payment[]> {
  const { status, body } = await settleUp(groupId);
  expect(status).toBe(200);
  expect(Array.isArray(body.payments)).toBe(true);
  return body.payments;
}

const sorted = (ps: Payment[]) =>
  ps.map(({ from, to, amountCents }) => ({ from, to, amountCents })).sort((a, b) => `${a.from}${a.to}`.localeCompare(`${b.from}${b.to}`));

describe("GET /api/groups/:groupId/settle-up", () => {
  it("returns { payments: [{ from, to, amountCents }] } with member ids", async () => {
    const ps = await payments("porto");
    expect(ps.length).toBeGreaterThan(0);
    const ids = new Set(groups.find((g) => g.id === "porto")!.members.map((m) => m.id));
    for (const p of ps) {
      expect(ids.has(p.from), `from ${p.from}`).toBe(true);
      expect(ids.has(p.to), `to ${p.to}`).toBe(true);
      expect(typeof p.amountCents).toBe("number");
    }
  });

  it("uses positive whole cents", async () => {
    for (const p of await payments("porto")) {
      expect(Number.isInteger(p.amountCents), `${p.amountCents}`).toBe(true);
      expect(p.amountCents).toBeGreaterThan(0);
    }
  });

  it("leaves everyone exactly square once the payments are made", async () => {
    const net = balancesOf("porto");
    for (const p of await payments("porto")) {
      net.set(p.from, net.get(p.from)! + p.amountCents);
      net.set(p.to, net.get(p.to)! - p.amountCents);
    }
    expect(Object.fromEntries(net)).toEqual(Object.fromEntries([...net.keys()].map((k) => [k, 0])));
  });

  it("never has someone pay themselves", async () => {
    for (const p of await payments("porto")) expect(p.from).not.toBe(p.to);
  });

  it("leaves out people who are already square", async () => {
    expect(balancesOf("porto").get("m-eli")).toBe(0);
    for (const p of await payments("porto")) {
      expect(p.from).not.toBe("m-eli");
      expect(p.to).not.toBe("m-eli");
    }
  });

  it("needs at most one payment fewer than the people who aren't square", async () => {
    const unsettled = [...balancesOf("porto").values()].filter((c) => c !== 0).length;
    expect((await payments("porto")).length).toBeLessThanOrEqual(unsettled - 1);
  });

  it("pairs people off when debts match exactly, instead of routing money around", async () => {
    // Ana +$10.00, Bo +$3.00, Cal -$3.00, Dee -$10.00 (spread over three expenses)
    expect(sorted(await payments("pairs"))).toEqual([
      { from: "m-cal", to: "m-bo", amountCents: 300 },
      { from: "m-dee", to: "m-ana", amountCents: 1000 },
    ]);
  });

  it("counts money that has already been paid back", async () => {
    expect(sorted(await payments("repaid"))).toEqual([{ from: "m-cal", to: "m-ana", amountCents: 3000 }]);
  });

  it("splits leftover cents the same way the balances do", async () => {
    expect(sorted(await payments("thirds"))).toEqual([
      { from: "m-bo", to: "m-ana", amountCents: 333 },
      { from: "m-cal", to: "m-ana", amountCents: 333 },
    ]);
  });

  it("returns no payments when everyone is already even", async () => {
    expect(await payments("square")).toEqual([]);
  });

  it("returns no payments for a group without expenses", async () => {
    expect(await payments("empty")).toEqual([]);
  });

  it("returns no payments for a one-person group", async () => {
    expect(await payments("solo")).toEqual([]);
  });

  it("404s for a group that doesn't exist", async () => {
    const res = await fetch(`${baseUrl}/api/groups/no-such-group/settle-up`);
    expect(res.status).toBe(404);
  });
});

describe("settle up on the group page", () => {
  let browser: Browser;
  beforeAll(async () => {
    browser = await chromium.launch();
  });
  afterAll(async () => {
    await browser?.close();
  });

  async function pageText(groupId: string): Promise<string> {
    const page = await browser.newPage();
    try {
      const res = await page.goto(`${baseUrl}/groups/${groupId}`, { waitUntil: "networkidle" });
      expect(res?.status()).toBe(200);
      await page.waitForTimeout(300); // anything rendered client-side after load
      return (await page.locator("body").innerText()).replace(/\s+/g, " ");
    } finally {
      await page.close();
    }
  }

  const line = (from: string, to: string, amount: string) =>
    new RegExp(`${from} pays ${to}[\\s:\\-–—]*${amount.replace(/[$.]/g, "\\$&")}`);

  it("shows who pays whom, by name", async () => {
    expect(await pageText("coffee")).toMatch(line("Dan", "Priya", "$12.50"));
  });

  it("shows every payment needed", async () => {
    const text = await pageText("pairs");
    expect(text).toMatch(line("Dee", "Ana", "$10.00"));
    expect(text).toMatch(line("Cal", "Bo", "$3.00"));
  });

  it("formats big amounts like the rest of the page", async () => {
    expect(await pageText("big")).toMatch(line("Dan", "Priya", "$1,234.56"));
  });

  it("shows no payments for a group that's already square", async () => {
    expect(await pageText("square")).not.toMatch(/\b(Ana|Bo|Cal) pays (Ana|Bo|Cal)\b/);
  });
});
