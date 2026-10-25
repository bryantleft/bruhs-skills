import { defineConfig } from "vitest/config";

export default defineConfig({
  test: {
    include: ["tests/hidden/**/*.test.ts"],
    environment: "node",
    globalSetup: ["tests/hidden/server.ts"],
    testTimeout: 30_000,
    hookTimeout: 90_000,
  },
});
