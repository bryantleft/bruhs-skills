import { HttpError } from "../errors.js";
import type { OrderInput } from "../types.js";

const EMAIL_RE = /^[^\s@]+@[^\s@]+\.[^\s@]+$/;

export interface SignupInput {
  email: string;
  name: string;
  password: string;
}

export function parseSignup(body: unknown): SignupInput {
  const { email, name, password } = (body ?? {}) as Record<string, unknown>;
  if (typeof email !== "string" || !EMAIL_RE.test(email)) {
    throw new HttpError(400, "valid email required");
  }
  if (typeof name !== "string" || name.trim().length === 0 || name.length > 100) {
    throw new HttpError(400, "name required (max 100 chars)");
  }
  if (typeof password !== "string" || password.length < 10) {
    throw new HttpError(400, "password must be at least 10 characters");
  }
  return { email: email.toLowerCase(), name: name.trim(), password };
}

export function parseOrderInput(body: unknown): OrderInput {
  const input = body as OrderInput;
  if (!input || !Array.isArray(input.items) || input.items.length === 0) {
    throw new HttpError(400, "items required");
  }
  if (input.items.length > 50) {
    throw new HttpError(400, "too many items");
  }
  if (input.note !== undefined && (typeof input.note !== "string" || input.note.length > 500)) {
    throw new HttpError(400, "note must be a string of at most 500 chars");
  }
  return input;
}
