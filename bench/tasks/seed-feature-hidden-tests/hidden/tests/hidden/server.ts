// globalSetup for the settle-up suite: serve the built app (next start) against
// tests/hidden/groups.json on a free local port.
import { spawn, type ChildProcess } from "node:child_process";
import { createServer } from "node:net";
import path from "node:path";
import type { TestProject } from "vitest/node";

declare module "vitest" {
  export interface ProvidedContext {
    baseUrl: string;
  }
}

const root = path.resolve(__dirname, "../..");
let server: ChildProcess | undefined;

function freePort(): Promise<number> {
  return new Promise((resolve, reject) => {
    const s = createServer();
    s.once("error", reject);
    s.listen(0, "127.0.0.1", () => {
      const address = s.address();
      s.close(() => (typeof address === "object" && address ? resolve(address.port) : reject(new Error("no port"))));
    });
  });
}

export async function setup(project: TestProject) {
  const port = await freePort();
  const baseUrl = `http://127.0.0.1:${port}`;
  let output = "";
  server = spawn(path.join(root, "node_modules/.bin/next"), ["start", "-p", String(port), "-H", "127.0.0.1"], {
    cwd: root,
    env: { ...process.env, NEXT_TELEMETRY_DISABLED: "1", TABBY_DATA: path.join(__dirname, "groups.json") },
    stdio: ["ignore", "pipe", "pipe"],
    detached: true,
  });
  server.stdout?.on("data", (d) => (output += d));
  server.stderr?.on("data", (d) => (output += d));
  const deadline = Date.now() + 60_000;
  for (;;) {
    if (server.exitCode !== null) throw new Error(`next start exited:\n${output}`);
    try {
      const res = await fetch(`${baseUrl}/api/groups`);
      if (res.ok) break;
    } catch {
      // not listening yet
    }
    if (Date.now() > deadline) throw new Error(`next start not ready after 60s:\n${output}`);
    await new Promise((r) => setTimeout(r, 250));
  }
  project.provide("baseUrl", baseUrl);
}

export async function teardown() {
  if (server?.pid) {
    try {
      process.kill(-server.pid, "SIGKILL");
    } catch {
      // already gone
    }
  }
}
