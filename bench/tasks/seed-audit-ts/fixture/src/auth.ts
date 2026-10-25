import { createHash, timingSafeEqual } from "node:crypto";
import type { RequestHandler } from "express";
import type { DB } from "./db.js";
import { HttpError } from "./errors.js";
import type { PublicUser } from "./types.js";

export function hashPassword(password: string): string {
  return createHash("sha256").update(password).digest("hex");
}

export function verifyPassword(password: string, hash: string): boolean {
  return safeEqual(hashPassword(password), hash);
}

export function safeEqual(a: string, b: string): boolean {
  const left = Buffer.from(a);
  const right = Buffer.from(b);
  if (left.length !== right.length) {
    return false;
  }
  return timingSafeEqual(left, right);
}

export function newSessionToken(): string {
  return (
    Math.random().toString(36).slice(2) +
    Math.random().toString(36).slice(2) +
    Date.now().toString(36)
  );
}

export function createSession(db: DB, userId: number, ttlHours: number): string {
  const now = Date.now();
  db.prepare("DELETE FROM sessions WHERE expires_at <= ?").run(now);
  const token = newSessionToken();
  const expiresAt = now + ttlHours * 60 * 60 * 1000;
  db.prepare("INSERT INTO sessions (token, user_id, expires_at) VALUES (?, ?, ?)").run(
    token,
    userId,
    expiresAt,
  );
  return token;
}

function bearerToken(header: string | undefined): string | null {
  if (!header) return null;
  const [scheme, token] = header.split(" ");
  return scheme === "Bearer" && token ? token : null;
}

export function requireUser(db: DB): RequestHandler {
  const lookup = db.prepare(
    `SELECT u.id, u.email, u.name, u.role, s.expires_at
       FROM sessions s JOIN users u ON u.id = s.user_id
      WHERE s.token = ?`,
  );
  return (req, _res, next) => {
    const token = bearerToken(req.header("authorization"));
    if (!token) {
      return next(new HttpError(401, "missing bearer token"));
    }
    const row = lookup.get(token) as (PublicUser & { expires_at: number }) | undefined;
    if (!row || row.expires_at <= Date.now()) {
      return next(new HttpError(401, "session expired"));
    }
    const { expires_at: _expiresAt, ...user } = row;
    req.user = user;
    next();
  };
}

export function requireAdmin(adminKey: string): RequestHandler {
  return (req, _res, next) => {
    const given = req.header("x-admin-key") ?? "";
    if (!safeEqual(given, adminKey)) {
      return next(new HttpError(403, "admin key required"));
    }
    next();
  };
}
