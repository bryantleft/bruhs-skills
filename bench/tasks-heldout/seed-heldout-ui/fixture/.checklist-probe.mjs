// Builds nothing: the item's shell script runs `vite build` first. Serves dist/ with
// `vite preview` (the project's own vite config) on a free port, runs check(), exits 0/1.
import { chromium } from "@playwright/test";
import { preview } from "vite";
import net from "node:net";

const port = await new Promise((resolve) => {
  const s = net.createServer().listen(0, "127.0.0.1", () => {
    const p = s.address().port;
    s.close(() => resolve(p));
  });
});
const server = await preview({ logLevel: "error", preview: { host: "127.0.0.1", port, strictPort: true, open: false } });
const url = `http://127.0.0.1:${port}/`;
const browser = await chromium.launch();
let ok = false;
try {
  ok = await check(browser, url);
} finally {
  await browser.close();
  await server.close();
}
process.exit(ok ? 0 : 1);

async function open(browser, url, options = {}) {
  const page = await browser.newPage({ viewport: { width: 1440, height: 900 }, ...options });
  await page.goto(url, { waitUntil: "networkidle" });
  return page;
}

/** document.title + the page's rendered text, <details> opened (collapsed text counts). */
async function pageText(page, selector) {
  return page.evaluate((sel) => {
    document.querySelectorAll("details").forEach((d) => (d.open = true));
    const root = (sel && document.querySelector(sel)) || document.body;
    return { title: document.title, text: root.innerText };
  }, selector);
}
// Tab to each keyboard stop in turn (fresh load each time); a stop has a visible focus
// indicator when the screen with it focused differs from the screen after blur().
// Carets, text selection, transitions and animations are neutralised so only focus
// styling can differ.
async function check(browser, url) {
  const page = await browser.newPage({ viewport: { width: 1440, height: 900 } });
  const stops = [];
  for (let k = 1; k <= 60; k++) {
    await page.goto(url, { waitUntil: "networkidle" });
    await page.addStyleTag({ content: "*,*::before,*::after{caret-color:transparent!important;transition:none!important;animation:none!important}::selection{background:transparent!important;color:inherit!important}" });
    for (let i = 0; i < k; i++) await page.keyboard.press("Tab");
    const id = await page.evaluate(() => {
      const el = document.activeElement;
      if (!el || el === document.body || el === document.documentElement) return null;
      return `${[...document.querySelectorAll("*")].indexOf(el)}: ${el.outerHTML.slice(0, 100)}`;
    });
    if (id === null || stops.some((s) => s.id === id)) break;
    const focused = await page.screenshot();
    await page.evaluate(() => document.activeElement.blur());
    const blurred = await page.screenshot();
    stops.push({ id, visible: !focused.equals(blurred) });
  }
  const invisible = stops.filter((s) => !s.visible).map((s) => s.id);
  console.log(`${stops.length} tab stops; no visible focus: ${JSON.stringify(invisible, null, 1)}`);
  return stops.length > 0 && invisible.length === 0;
}
