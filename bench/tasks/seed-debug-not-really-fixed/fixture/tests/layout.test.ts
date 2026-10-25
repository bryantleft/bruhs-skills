import { describe, expect, it } from "vitest";
import { columnsFor } from "../src/layout";

describe("columnsFor", () => {
  it.each([320, 360, 375, 390, 414, 430])("stacks the checkout on a %ipx phone", (width) => {
    expect(columnsFor(width)).toBe(1);
  });

  it.each([768, 1024, 1280, 1920])("puts the cart and summary side by side at %ipx", (width) => {
    expect(columnsFor(width)).toBe(2);
  });
});
