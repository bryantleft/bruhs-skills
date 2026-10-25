import { describe, expect, it } from "vitest";
import { sign, verify } from "../src/signature";

const body = JSON.stringify({ id: "evt_1", type: "invoice.paid" });

describe("sign / verify", () => {
  it("round-trips", () => {
    const header = sign("whsec_test", 1_760_000_000, body);
    expect(header).toMatch(/^v1=[0-9a-f]{64}$/);
    expect(verify("whsec_test", header, 1_760_000_000, body, 1_760_000_010)).toBe(true);
  });

  it("rejects a different secret or body", () => {
    const header = sign("whsec_test", 1_760_000_000, body);
    expect(verify("whsec_other", header, 1_760_000_000, body, 1_760_000_000)).toBe(false);
    expect(verify("whsec_test", header, 1_760_000_000, `${body} `, 1_760_000_000)).toBe(false);
  });

  it("rejects stale timestamps", () => {
    const header = sign("whsec_test", 1_760_000_000, body);
    expect(verify("whsec_test", header, 1_760_000_000, body, 1_760_000_301)).toBe(false);
  });
});
