import { describe, expect, it } from "vitest";
import { isValidEmail, maskKey, slugify } from "../src/settings";

describe("slugify", () => {
  it("lowercases and hyphenates", () => {
    expect(slugify("Lantern Press")).toBe("lantern-press");
  });

  it("drops accents and stray punctuation", () => {
    expect(slugify("  Café & Co. ")).toBe("cafe-co");
  });
});

describe("maskKey", () => {
  it("keeps the prefix and the last four characters", () => {
    expect(maskKey("qk_live_7Hc2pX9vLmQ4rT8wZs1NbE6yUa3dKf0j")).toBe("qk_live_••••••••Kf0j");
  });
});

describe("isValidEmail", () => {
  it("accepts a normal address and rejects junk", () => {
    expect(isValidEmail("maya@lanternpress.co")).toBe(true);
    expect(isValidEmail("maya@")).toBe(false);
  });
});
