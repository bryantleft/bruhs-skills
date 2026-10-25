import { createApp } from "./app.js";
import { loadConfig } from "./config.js";
import { openDb } from "./db.js";

const config = loadConfig();
const db = openDb(config.dbPath);
const app = createApp(db, config);

const server = app.listen(config.port, () => {
  console.log(`orderdesk-api listening on :${config.port}`);
});

function shutdown(signal: string) {
  console.log(`${signal} received, shutting down`);
  server.close(() => {
    db.close();
    process.exit(0);
  });
}

process.on("SIGTERM", () => shutdown("SIGTERM"));
process.on("SIGINT", () => shutdown("SIGINT"));
