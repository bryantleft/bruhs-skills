import { describe, expect, it } from "vitest";
import { GET as getBalances } from "@/app/api/groups/[groupId]/balances/route";
import { GET as listGroups } from "@/app/api/groups/route";

const params = (groupId: string) => ({ params: Promise.resolve({ groupId }) });
const req = (path: string) => new Request(`http://localhost${path}`);

describe("GET /api/groups", () => {
  it("lists groups with their totals", async () => {
    const res = listGroups();
    expect(res.status).toBe(200);
    const body = await res.json();
    expect(body.groups.map((g: { id: string }) => g.id)).toEqual(["cabin", "empty"]);
    expect(body.groups[0].totalCents).toBe(31000);
  });
});

describe("GET /api/groups/:groupId/balances", () => {
  it("returns each member's balance in cents", async () => {
    const res = await getBalances(req("/api/groups/cabin/balances"), params("cabin"));
    expect(res.status).toBe(200);
    expect(await res.json()).toEqual({
      balances: [
        { memberId: "ana", name: "Ana", cents: 14666 },
        { memberId: "ben", name: "Ben", cents: -9333 },
        { memberId: "cy", name: "Cy", cents: -5333 },
      ],
    });
  });

  it("treats a missing repayments list as none", async () => {
    const res = await getBalances(req("/api/groups/empty/balances"), params("empty"));
    expect(await res.json()).toEqual({ balances: [{ memberId: "zed", name: "Zed", cents: 0 }] });
  });

  it("404s for an unknown group", async () => {
    const res = await getBalances(req("/api/groups/nope/balances"), params("nope"));
    expect(res.status).toBe(404);
    expect(await res.json()).toEqual({ error: "group not found" });
  });
});
