import { afterEach, describe, expect, it, vi } from "vitest";
import { TtlCache } from "../src/lib/cache.js";

describe("TtlCache", () => {
  afterEach(() => {
    vi.useRealTimers();
  });

  it("returns values until they expire", () => {
    vi.useFakeTimers();
    const cache = new TtlCache<number>(1000);
    cache.set("a", 1);
    expect(cache.get("a")).toBe(1);
    vi.advanceTimersByTime(999);
    expect(cache.get("a")).toBe(1);
    vi.advanceTimersByTime(1);
    expect(cache.get("a")).toBeUndefined();
  });

  it("deletes entries", () => {
    const cache = new TtlCache<string>(1000);
    cache.set("k", "v");
    cache.delete("k");
    expect(cache.get("k")).toBeUndefined();
  });
});
