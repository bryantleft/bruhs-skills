import { expect, test, type Page } from "@playwright/test";

const phone = (width: number) => ({ viewport: { width, height: 844 }, isMobile: true, hasTouch: true, deviceScaleFactor: 3 });

async function open(page: Page) {
  await page.goto("/");
  await expect(page.getByRole("heading", { name: "Your cart" })).toBeVisible();
  await expect(page.getByRole("button", { name: /^Pay / })).toBeVisible();
}

/** How far the page's content reaches past the screen width (mobile browsers may widen
 * the layout viewport to fit overflowing content, so compare with the device width). */
async function horizontalOverflow(page: Page, width: number): Promise<number> {
  return page.evaluate((w) => Math.max(document.documentElement.scrollWidth, document.body.scrollWidth) - w, width);
}

async function horizontallyInside(page: Page, selector: ReturnType<Page["locator"]>, width: number) {
  const box = await selector.boundingBox();
  expect(box, "element is rendered").not.toBeNull();
  expect(box!.x, "left edge on screen").toBeGreaterThanOrEqual(0);
  expect(box!.x + box!.width, "right edge on screen").toBeLessThanOrEqual(width + 0.5);
}

for (const width of [390, 375, 360]) {
  test.describe(`${width}px phone`, () => {
    test.use(phone(width));

    test("page doesn't scroll sideways", async ({ page }) => {
      await open(page);
      expect(await horizontalOverflow(page, width)).toBeLessThanOrEqual(0);
    });

    test("pay button is fully on screen", async ({ page }) => {
      await open(page);
      await horizontallyInside(page, page.getByRole("button", { name: /^Pay / }), width);
    });
  });
}

test.describe("390px phone layout", () => {
  test.use(phone(390));

  test("order summary is stacked under the cart", async ({ page }) => {
    await open(page);
    const cart = await page.getByRole("heading", { name: "Your cart" }).boundingBox();
    const summary = await page.getByRole("heading", { name: "Order summary" }).boundingBox();
    expect(summary!.y).toBeGreaterThan(cart!.y + cart!.height);
  });

  test("every line price is on screen", async ({ page }) => {
    await open(page);
    const prices = page.getByTestId("line-price");
    await expect(prices).toHaveCount(3);
    for (const price of await prices.all()) await horizontallyInside(page, price, 390);
  });

  test("long product names stay inside their line", async ({ page }) => {
    await open(page);
    for (const line of await page.getByTestId("cart-line").all()) await horizontallyInside(page, line, 390);
  });
});

test.describe("desktop", () => {
  test.use({ viewport: { width: 1280, height: 900 } });

  test("cart and summary are still side by side", async ({ page }) => {
    await open(page);
    const cart = await page.getByRole("heading", { name: "Your cart" }).boundingBox();
    const summary = await page.getByRole("heading", { name: "Order summary" }).boundingBox();
    expect(summary!.x).toBeGreaterThan(cart!.x + cart!.width);
    expect(Math.abs(summary!.y - cart!.y)).toBeLessThan(40);
    expect(await horizontalOverflow(page, 1280)).toBeLessThanOrEqual(0);
  });
});
