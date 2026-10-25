import type { DB } from "../db.js";

export interface DeliveryOptions {
  attempts: number;
  baseDelayMs: number;
}

const DEFAULTS: DeliveryOptions = { attempts: 4, baseDelayMs: 250 };

const sleep = (ms: number) => new Promise((resolve) => setTimeout(resolve, ms));

export function backoffMs(attempt: number, baseDelayMs: number): number {
  const exponential = baseDelayMs * 2 ** (attempt - 1);
  return exponential + Math.floor(Math.random() * baseDelayMs);
}

export async function deliverWebhook(
  db: DB,
  url: string,
  event: string,
  payload: unknown,
  options: Partial<DeliveryOptions> = {},
): Promise<boolean> {
  const { attempts, baseDelayMs } = { ...DEFAULTS, ...options };
  const body = JSON.stringify({ event, payload, sentAt: new Date().toISOString() });
  const { lastInsertRowid: id } = db
    .prepare("INSERT INTO webhook_deliveries (event, body) VALUES (?, ?)")
    .run(event, body);
  const record = db.prepare(
    "UPDATE webhook_deliveries SET status = ?, attempts = ? WHERE id = ?",
  );

  for (let attempt = 1; attempt <= attempts; attempt++) {
    try {
      const res = await fetch(url, {
        method: "POST",
        headers: { "content-type": "application/json" },
        body,
        signal: AbortSignal.timeout(5_000),
      });
      if (res.ok) {
        record.run("delivered", attempt, id);
        return true;
      }
    } catch (err) {
      console.warn(`webhook ${event} attempt ${attempt} failed:`, (err as Error).message);
    }
    if (attempt < attempts) {
      await sleep(backoffMs(attempt, baseDelayMs));
    }
  }
  record.run("failed", attempts, id);
  return false;
}
