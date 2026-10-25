import { describe, expect, it } from "vitest";
import { MAX_PAGE_SIZE, pageMeta, parsePage } from "../src/lib/pagination.js";

describe("parsePage", () => {
  it("defaults to the first page of 20", () => {
    const page = parsePage({});
    expect(page.page).toBe(1);
    expect(page.pageSize).toBe(20);
  });

  it("clamps the page size", () => {
    expect(parsePage({ pageSize: "500" }).pageSize).toBe(MAX_PAGE_SIZE);
    expect(parsePage({ pageSize: "-3" }).pageSize).toBe(20);
  });

  it("ignores junk page numbers", () => {
    expect(parsePage({ page: "abc" }).page).toBe(1);
    expect(parsePage({ page: "2.5" }).page).toBe(1);
  });
});

describe("pageMeta", () => {
  it("counts pages", () => {
    expect(pageMeta({ page: 1, pageSize: 20, offset: 0 }, 41).pages).toBe(3);
    expect(pageMeta({ page: 1, pageSize: 20, offset: 0 }, 0).pages).toBe(1);
  });
});
