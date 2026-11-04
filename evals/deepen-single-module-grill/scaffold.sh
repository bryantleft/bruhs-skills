#!/usr/bin/env bash
# Restaurant booking app (TypeScript, Drizzle/Postgres, Stripe deposits).
# src/reservations/ReservationManager.ts is the shallow module to grill:
#   createReservation(customerId, restaurantId, partySize, date, time, smoking,
#     vip, depositCents, depositRequired, notes, stripePaymentIntentId)
#   updateReservation(id, partialFields)
# both forward straight to a ReservationRepository interface that has exactly
# one adapter (DrizzleReservationRepository). Three callers duplicate the
# validation and disagree: api/reservations.ts (partySize > 0, date in the
# future, deposit >= 0), admin/reservations.ts (partySize 1..20, date today or
# later, deposit >= 0), jobs/reminders.ts (rebooks no-shows; checks partySize
# > 0 and a future date). Only api/reservations.ts takes deposits; it creates
# the Stripe PaymentIntent itself and passes the id into createReservation.
# Existing tests test past the interface (the manager test asserts arguments
# reach the repository mock; the api/admin tests re-test the copied rules).
# CONTEXT.md is the glossary; docs/adr/ holds one ADR.
set -euo pipefail
. "$(cd "$(dirname "$0")" && pwd)/../_lib/helpers.sh"

# eval_state, but writes the "no rules" placeholder when the stack derives no
# rules (sync_bruhs_block.py rejects the empty stdin eval_state pipes it).
eval_repo
eval_node_project tablebook drizzle-orm stripe hono
eval_state <<'JSON'
{
  "stack": {"structure": "single", "framework": "hono", "language": "typescript", "database": ["drizzle-postgres"], "payments": ["stripe"], "testing": ["node:test"]},
  "tooling": {"mcps": [], "skills": []}
}
JSON

eval_write CONTEXT.md <<'EOF'
# Domain glossary

- **Restaurant**: a venue that takes bookings.
- **Customer**: the person who books.
- **Reservation**: a Customer's booking at a Restaurant for a party size, a date
  and a time. Booked, seated, no-show or canceled.
- **Party size**: number of guests on a Reservation. Restaurants cap it (20 by
  default) unless an admin overrides.
- **Deposit**: money held to secure a Reservation at restaurants that require
  one. Collected through Stripe as a PaymentIntent; released on arrival,
  captured on a no-show.
- **Reminder**: the message a Customer gets the day before.
EOF

eval_write docs/adr/0001-drizzle-for-persistence.md <<'EOF'
# 1. Drizzle for persistence

Status: accepted

We use Drizzle over Postgres for all persistence. Tests run against PGlite, so
repository code is exercised against a real SQL engine in-process.
EOF

eval_write src/reservations/types.ts <<'EOF'
export type ReservationStatus = "booked" | "seated" | "no_show" | "canceled";

export type Reservation = {
  id: string;
  customerId: string;
  restaurantId: string;
  partySize: number;
  date: string; // YYYY-MM-DD, restaurant local time
  time: string; // HH:mm
  smoking: boolean;
  vip: boolean;
  depositCents: number;
  depositRequired: boolean;
  stripePaymentIntentId: string | null;
  notes: string;
  status: ReservationStatus;
  reminderSentAt: Date | null;
};
EOF

eval_write src/reservations/ReservationRepository.ts <<'EOF'
import type { Reservation } from "./types.ts";

export interface ReservationRepository {
  insert(fields: Omit<Reservation, "id">): Promise<Reservation>;
  update(id: string, fields: Partial<Reservation>): Promise<Reservation>;
  findById(id: string): Promise<Reservation | undefined>;
}
EOF

eval_write src/reservations/DrizzleReservationRepository.ts <<'EOF'
import { eq } from "drizzle-orm";
import { db } from "../db/client.ts";
import { reservations } from "../db/schema.ts";
import type { ReservationRepository } from "./ReservationRepository.ts";
import type { Reservation } from "./types.ts";

export class DrizzleReservationRepository implements ReservationRepository {
  async insert(fields: Omit<Reservation, "id">): Promise<Reservation> {
    const [row] = await db.insert(reservations).values(fields).returning();
    return row;
  }

  async update(id: string, fields: Partial<Reservation>): Promise<Reservation> {
    const [row] = await db.update(reservations).set(fields).where(eq(reservations.id, id)).returning();
    if (!row) throw new Error(`reservation ${id} not found`);
    return row;
  }

  async findById(id: string): Promise<Reservation | undefined> {
    const [row] = await db.select().from(reservations).where(eq(reservations.id, id));
    return row;
  }
}
EOF

eval_write src/reservations/ReservationManager.ts <<'EOF'
import type { ReservationRepository } from "./ReservationRepository.ts";
import type { Reservation } from "./types.ts";

export class ReservationManager {
  private readonly repo: ReservationRepository;

  constructor(repo: ReservationRepository) {
    this.repo = repo;
  }

  async createReservation(
    customerId: string,
    restaurantId: string,
    partySize: number,
    date: string,
    time: string,
    smoking: boolean,
    vip: boolean,
    depositCents: number,
    depositRequired: boolean,
    notes: string,
    stripePaymentIntentId: string | null = null,
  ): Promise<Reservation> {
    return this.repo.insert({
      customerId,
      restaurantId,
      partySize,
      date,
      time,
      smoking,
      vip,
      depositCents,
      depositRequired,
      stripePaymentIntentId,
      notes,
      status: "booked",
      reminderSentAt: null,
    });
  }

  async updateReservation(id: string, fields: Partial<Reservation>): Promise<Reservation> {
    return this.repo.update(id, fields);
  }
}
EOF

eval_write src/db/client.ts <<'EOF'
import { drizzle } from "drizzle-orm/node-postgres";

export const db = drizzle(process.env.DATABASE_URL ?? "");
EOF

eval_write src/db/schema.ts <<'EOF'
import { boolean, integer, pgTable, text, timestamp } from "drizzle-orm/pg-core";

export const reservations = pgTable("reservations", {
  id: text("id").primaryKey().$defaultFn(() => crypto.randomUUID()),
  customerId: text("customer_id").notNull(),
  restaurantId: text("restaurant_id").notNull(),
  partySize: integer("party_size").notNull(),
  date: text("date").notNull(),
  time: text("time").notNull(),
  smoking: boolean("smoking").notNull(),
  vip: boolean("vip").notNull(),
  depositCents: integer("deposit_cents").notNull(),
  depositRequired: boolean("deposit_required").notNull(),
  stripePaymentIntentId: text("stripe_payment_intent_id"),
  notes: text("notes").notNull(),
  status: text("status").$type<"booked" | "seated" | "no_show" | "canceled">().notNull(),
  reminderSentAt: timestamp("reminder_sent_at"),
});
EOF

eval_write src/payments/stripe.ts <<'EOF'
import Stripe from "stripe";

const stripe = new Stripe(process.env.STRIPE_SECRET_KEY ?? "");

export async function createDepositIntent(stripeCustomerId: string, cents: number): Promise<string> {
  const intent = await stripe.paymentIntents.create({
    amount: cents,
    currency: "usd",
    customer: stripeCustomerId,
    capture_method: "manual",
  });
  return intent.id;
}
EOF

eval_write src/api/reservations.ts <<'EOF'
import type { ReservationManager } from "../reservations/ReservationManager.ts";
import type { Reservation } from "../reservations/types.ts";

export type BookingRequest = {
  customerId: string;
  stripeCustomerId: string;
  restaurantId: string;
  partySize: number;
  date: string;
  time: string;
  smoking?: boolean;
  notes?: string;
};

type Deps = {
  manager: ReservationManager;
  depositFor: (restaurantId: string) => Promise<number>;
  createDepositIntent: (stripeCustomerId: string, cents: number) => Promise<string>;
  today: () => string;
};

export function createBookingHandler(deps: Deps) {
  return async (req: BookingRequest): Promise<Reservation> => {
    if (req.partySize <= 0) throw new Error("party size must be at least 1");
    if (req.date <= deps.today()) throw new Error("reservation date must be in the future");
    const depositCents = await deps.depositFor(req.restaurantId);
    if (depositCents < 0) throw new Error("deposit cannot be negative");
    const intentId = depositCents > 0 ? await deps.createDepositIntent(req.stripeCustomerId, depositCents) : null;
    return deps.manager.createReservation(
      req.customerId,
      req.restaurantId,
      req.partySize,
      req.date,
      req.time,
      req.smoking ?? false,
      false,
      depositCents,
      depositCents > 0,
      req.notes ?? "",
      intentId,
    );
  };
}
EOF

eval_write src/admin/reservations.ts <<'EOF'
import type { ReservationManager } from "../reservations/ReservationManager.ts";
import type { Reservation } from "../reservations/types.ts";

export type PhoneBooking = {
  customerId: string;
  restaurantId: string;
  partySize: number;
  date: string;
  time: string;
  vip: boolean;
  notes: string;
};

export async function bookByPhone(manager: ReservationManager, booking: PhoneBooking, today: string): Promise<Reservation> {
  if (booking.partySize < 1 || booking.partySize > 20) throw new Error(`party size ${booking.partySize} is out of range`);
  if (booking.date < today) throw new Error("cannot book in the past");
  const depositCents = 0;
  if (depositCents < 0) throw new Error("deposit cannot be negative");
  return manager.createReservation(
    booking.customerId,
    booking.restaurantId,
    booking.partySize,
    booking.date,
    booking.time,
    false,
    booking.vip,
    depositCents,
    false,
    booking.notes,
  );
}
EOF

eval_write src/jobs/reminders.ts <<'EOF'
import type { ReservationManager } from "../reservations/ReservationManager.ts";
import type { Reservation } from "../reservations/types.ts";

export async function markReminderSent(manager: ReservationManager, reservation: Reservation, now: Date): Promise<void> {
  await manager.updateReservation(reservation.id, { reminderSentAt: now });
}

// No-shows can be moved to a later slot by the customer from the reminder link.
export async function rebookNoShow(
  manager: ReservationManager,
  reservation: Reservation,
  slot: { date: string; time: string },
  today: string,
): Promise<Reservation> {
  if (reservation.partySize <= 0) throw new Error("party size must be at least 1");
  if (slot.date <= today) throw new Error("new date must be in the future");
  return manager.updateReservation(reservation.id, { date: slot.date, time: slot.time, status: "booked" });
}
EOF

eval_write src/reservations/ReservationManager.test.ts <<'EOF'
import { test } from "node:test";
import assert from "node:assert/strict";
import { ReservationManager } from "./ReservationManager.ts";
import type { ReservationRepository } from "./ReservationRepository.ts";

test("createReservation passes every field to the repository", async () => {
  const inserted: unknown[] = [];
  const repo: ReservationRepository = {
    insert: async (fields) => {
      inserted.push(fields);
      return { id: "r1", ...fields };
    },
    update: async () => { throw new Error("unused"); },
    findById: async () => undefined,
  };
  await new ReservationManager(repo).createReservation("c1", "rest1", 4, "2030-01-01", "19:00", false, true, 0, false, "");
  assert.equal(inserted.length, 1);
  assert.equal((inserted[0] as { vip: boolean }).vip, true);
});
EOF

eval_write src/api/reservations.test.ts <<'EOF'
import { test } from "node:test";
import assert from "node:assert/strict";
import { createBookingHandler } from "./reservations.ts";
import type { ReservationManager } from "../reservations/ReservationManager.ts";

const manager = { createReservation: async () => { throw new Error("should not be called"); } } as unknown as ReservationManager;
const handler = createBookingHandler({ manager, depositFor: async () => 0, createDepositIntent: async () => "pi_1", today: () => "2030-01-01" });

test("rejects a party of zero", async () => {
  await assert.rejects(handler({ customerId: "c", stripeCustomerId: "cus", restaurantId: "r", partySize: 0, date: "2030-02-01", time: "19:00" }));
});

test("rejects a date in the past", async () => {
  await assert.rejects(handler({ customerId: "c", stripeCustomerId: "cus", restaurantId: "r", partySize: 2, date: "2029-12-31", time: "19:00" }));
});
EOF

eval_write src/admin/reservations.test.ts <<'EOF'
import { test } from "node:test";
import assert from "node:assert/strict";
import { bookByPhone } from "./reservations.ts";
import type { ReservationManager } from "../reservations/ReservationManager.ts";

const manager = { createReservation: async () => { throw new Error("should not be called"); } } as unknown as ReservationManager;

test("rejects a party of 21", async () => {
  await assert.rejects(
    bookByPhone(manager, { customerId: "c", restaurantId: "r", partySize: 21, date: "2030-02-01", time: "19:00", vip: false, notes: "" }, "2030-01-01"),
  );
});
EOF

eval_commit "feat: reservations with deposits, phone bookings and reminders"
eval_origin
eval_gh
