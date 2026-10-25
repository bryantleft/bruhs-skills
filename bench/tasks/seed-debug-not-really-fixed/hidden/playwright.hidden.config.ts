import { defineConfig, devices } from "@playwright/test";

// The port comes from the check command (HIDDEN_PORT), so the main process and every
// worker agree on it.
const port = Number(process.env.HIDDEN_PORT ?? 4319);

export default defineConfig({
  testDir: "tests/hidden",
  testMatch: "**/*.spec.ts",
  fullyParallel: true,
  retries: 0,
  use: {
    ...devices["Desktop Chrome"],
    baseURL: `http://127.0.0.1:${port}`,
  },
  webServer: {
    command: `./node_modules/.bin/vite preview --host 127.0.0.1 --port ${port} --strictPort`,
    url: `http://127.0.0.1:${port}`,
    reuseExistingServer: false,
    timeout: 60_000,
  },
});
