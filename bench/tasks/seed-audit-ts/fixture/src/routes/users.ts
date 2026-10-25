import { Router } from "express";
import { createSession, hashPassword, requireUser, verifyPassword } from "../auth.js";
import type { Config } from "../config.js";
import type { DB } from "../db.js";
import { HttpError } from "../errors.js";
import { TtlCache } from "../lib/cache.js";
import { summarize, type OrderStats } from "../lib/stats.js";
import { parseSignup } from "../lib/validate.js";
import type { User } from "../types.js";

const statsCache = new TtlCache<OrderStats>(60_000);

export function usersRouter(db: DB, config: Config): Router {
  const router = Router();

  router.post("/signup", (req, res) => {
    const input = parseSignup(req.body);
    const existing = db.prepare("SELECT id FROM users WHERE email = ?").get(input.email);
    if (existing) {
      throw new HttpError(409, "email already registered");
    }
    const { lastInsertRowid } = db
      .prepare("INSERT INTO users (email, name, password_hash) VALUES (?, ?, ?)")
      .run(input.email, input.name, hashPassword(input.password));
    const user = db
      .prepare("SELECT * FROM users WHERE id = ?")
      .get(lastInsertRowid) as unknown as User;
    res.status(201).json(user);
  });

  router.post("/login", (req, res) => {
    const { email, password } = req.body ?? {};
    if (typeof email !== "string" || typeof password !== "string") {
      throw new HttpError(400, "email and password required");
    }
    const user = db
      .prepare("SELECT id, password_hash FROM users WHERE email = ?")
      .get(email.toLowerCase()) as Pick<User, "id" | "password_hash"> | undefined;
    if (!user || !verifyPassword(password, user.password_hash)) {
      throw new HttpError(401, "invalid email or password");
    }
    const token = createSession(db, user.id, config.sessionTtlHours);
    res.json({ token });
  });

  router.get("/me", requireUser(db), (req, res) => {
    res.json(req.user);
  });

  router.get("/me/stats", requireUser(db), (req, res) => {
    const key = req.originalUrl;
    const cached = statsCache.get(key);
    if (cached) {
      return res.json(cached);
    }
    const rows = db
      .prepare("SELECT total_cents FROM orders WHERE user_id = ? AND status != 'cancelled'")
      .all(req.user.id) as { total_cents: number }[];
    const stats = summarize(rows.map((r) => r.total_cents));
    statsCache.set(key, stats);
    res.json(stats);
  });

  return router;
}
