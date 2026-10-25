export interface Config {
  port: number;
  dbPath: string;
  adminKey: string;
  paymentsUrl: string;
  webhookUrl?: string;
  sessionTtlHours: number;
}

export function loadConfig(env: NodeJS.ProcessEnv = process.env): Config {
  const adminKey = env.ADMIN_KEY;
  if (!adminKey) {
    throw new Error("ADMIN_KEY must be set");
  }
  const port = Number(env.PORT ?? 3000);
  if (!Number.isInteger(port) || port <= 0 || port > 65535) {
    throw new Error(`invalid PORT: ${env.PORT}`);
  }
  const sessionTtlHours = Number(env.SESSION_TTL_HOURS ?? 72);
  if (!(sessionTtlHours > 0)) {
    throw new Error(`invalid SESSION_TTL_HOURS: ${env.SESSION_TTL_HOURS}`);
  }
  return {
    port,
    dbPath: env.DB_PATH ?? "orderdesk.db",
    adminKey,
    paymentsUrl: env.PAYMENTS_URL ?? "http://localhost:4010",
    webhookUrl: env.WEBHOOK_URL || undefined,
    sessionTtlHours,
  };
}
