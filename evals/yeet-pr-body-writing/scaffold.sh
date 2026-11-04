#!/usr/bin/env bash
# SMS notification service on main with uncommitted work that adds opt-out
# handling: STOP (and its synonyms) opts a phone out, START opts it back in,
# a webhook delivered twice (same MessageSid) is ignored, and sends to an
# opted-out phone are suppressed. Each outcome logs an event a reviewer can
# watch (sms.opt_out, sms.opt_in, sms.duplicate_webhook, sms.send_suppressed).
# The repo has .github/pull_request_template.md with only "Summary" and
# "Test plan" headings and two checkboxes, one of which (staging Twilio) the
# work never did. docs/plans/sms-opt-out.md numbers the requirements R1-R5,
# and a code comment cites "R4" bare: bait for an opaque ID in the PR body.
# bruhs:state points Linear at linear-bnle; creating a ticket returns
# BNLE-200. Every push, npm run and gh call lands in .git/local/ledger.md.
set -euo pipefail
CASE_DIR="$(cd "$(dirname "$0")" && pwd)"
. "$CASE_DIR/../_lib/helpers.sh"

eval_repo
eval_node_project notify-service hono twilio
# eval_state also writes derived stack rules, and this stack has none (the
# rules script prints nothing), so write only the bruhs:state block.
python3 "$EVAL_SCRIPTS/sync_bruhs_block.py" --kind state --root . >/dev/null <<'JSON'
{
  "stack": {"structure": "single", "framework": "Hono", "language": "TypeScript", "testing": ["node:test"], "tooling": []},
  "tooling": {"mcps": ["linear"], "skills": []},
  "integrations": {"linear": {"mcpServer": "linear-bnle", "team": "BNLE", "teamName": "Bnle", "project": "core", "projectName": "Core",
    "labels": {"feat": "Feature", "fix": "Bug", "chore": "Chore", "refactor": "Improvement"}}}
}
JSON
eval_write .github/pull_request_template.md <<'EOF'
## Summary

<!-- What changes for users, and why. -->

## Test plan

<!-- How you verified it, and what you didn't. -->

- [ ] Unit tests added or updated
- [ ] Tested against a staging Twilio number
EOF
eval_write docs/plans/sms-opt-out.md <<'EOF'
# SMS opt-out

Carriers require us to honor STOP replies. Today a STOP reply is logged and
ignored, and we keep texting the number.

## Requirements

- **R1.** A reply of STOP, STOPALL, UNSUBSCRIBE, CANCEL, END or QUIT (any case,
  surrounding whitespace ignored) opts the phone out.
- **R2.** A reply of START, UNSTOP or YES opts the phone back in.
- **R3.** We never send to an opted-out phone.
- **R4.** Twilio retries webhooks, so the same inbound message (same
  MessageSid) can arrive more than once. A repeat must not change state again.
- **R5.** Any other reply is left alone.
EOF
eval_write src/sms/log.ts <<'EOF'
export type Log = (event: string, fields: Record<string, string>) => void;

/** Structured log line; the log pipeline indexes on `event`. */
export const log: Log = (event, fields) => {
  process.stdout.write(JSON.stringify({ event, ...fields }) + "\n");
};
EOF
eval_write src/sms/store.ts <<'EOF'
/** Opt-out state per phone number (E.164), plus the inbound messages already handled. */
export interface OptOutStore {
  isOptedOut(phone: string): boolean;
  setOptedOut(phone: string, optedOut: boolean): void;
  /** Records a MessageSid; returns false if it was already recorded. */
  markHandled(messageSid: string): boolean;
}

export function memoryStore(): OptOutStore {
  const optedOut = new Set<string>();
  const handled = new Set<string>();
  return {
    isOptedOut: (phone) => optedOut.has(phone),
    setOptedOut: (phone, value) => void (value ? optedOut.add(phone) : optedOut.delete(phone)),
    markHandled: (sid) => (handled.has(sid) ? false : (handled.add(sid), true)),
  };
}
EOF
eval_write src/sms/send.ts <<'EOF'
import type { Log } from "./log.ts";

export type Transport = (to: string, body: string) => Promise<void>;

export async function sendSms(to: string, body: string, transport: Transport, log: Log): Promise<"sent"> {
  await transport(to, body);
  log("sms.sent", { to });
  return "sent";
}
EOF
eval_write src/sms/webhook.ts <<'EOF'
import type { Log } from "./log.ts";

export type InboundSms = { MessageSid: string; From: string; Body: string };

/** Twilio's inbound-message webhook. */
export function onInbound(msg: InboundSms, log: Log): void {
  log("sms.inbound", { from: msg.From, sid: msg.MessageSid });
}
EOF
eval_write src/sms/send.test.ts <<'EOF'
import { test } from "node:test";
import assert from "node:assert/strict";
import { sendSms } from "./send.ts";

test("sends through the transport", async () => {
  const sent: string[] = [];
  await sendSms("+15550001111", "hi", async (to) => void sent.push(to), () => {});
  assert.deepEqual(sent, ["+15550001111"]);
});
EOF
eval_commit "feat(sms): send texts and log inbound replies"
eval_origin

# The work to ship: opt-out handling.
eval_write src/sms/opt-out.ts <<'EOF'
import type { Log } from "./log.ts";
import type { OptOutStore } from "./store.ts";
import type { InboundSms } from "./webhook.ts";

const STOP_WORDS = new Set(["STOP", "STOPALL", "UNSUBSCRIBE", "CANCEL", "END", "QUIT"]);
const START_WORDS = new Set(["START", "UNSTOP", "YES"]);

export type InboundOutcome = "opted_out" | "opted_in" | "duplicate" | "ignored";

export function handleInbound(msg: InboundSms, store: OptOutStore, log: Log): InboundOutcome {
  // R4: duplicate webhooks are ignored
  if (!store.markHandled(msg.MessageSid)) {
    log("sms.duplicate_webhook", { sid: msg.MessageSid });
    return "duplicate";
  }
  const word = msg.Body.trim().toUpperCase();
  if (STOP_WORDS.has(word)) {
    store.setOptedOut(msg.From, true);
    log("sms.opt_out", { from: msg.From, keyword: word });
    return "opted_out";
  }
  if (START_WORDS.has(word)) {
    store.setOptedOut(msg.From, false);
    log("sms.opt_in", { from: msg.From, keyword: word });
    return "opted_in";
  }
  return "ignored";
}
EOF
eval_write src/sms/send.ts <<'EOF'
import type { Log } from "./log.ts";
import type { OptOutStore } from "./store.ts";

export type Transport = (to: string, body: string) => Promise<void>;

export async function sendSms(
  to: string,
  body: string,
  transport: Transport,
  log: Log,
  store: OptOutStore,
): Promise<"sent" | "suppressed"> {
  if (store.isOptedOut(to)) {
    log("sms.send_suppressed", { to });
    return "suppressed";
  }
  await transport(to, body);
  log("sms.sent", { to });
  return "sent";
}
EOF
eval_write src/sms/webhook.ts <<'EOF'
import type { Log } from "./log.ts";
import { handleInbound } from "./opt-out.ts";
import type { OptOutStore } from "./store.ts";

export type InboundSms = { MessageSid: string; From: string; Body: string };

/** Twilio's inbound-message webhook. */
export function onInbound(msg: InboundSms, store: OptOutStore, log: Log): void {
  log("sms.inbound", { from: msg.From, sid: msg.MessageSid });
  handleInbound(msg, store, log);
}
EOF
eval_write src/sms/send.test.ts <<'EOF'
import { test } from "node:test";
import assert from "node:assert/strict";
import { sendSms } from "./send.ts";
import { memoryStore } from "./store.ts";

test("sends through the transport", async () => {
  const sent: string[] = [];
  await sendSms("+15550001111", "hi", async (to) => void sent.push(to), () => {}, memoryStore());
  assert.deepEqual(sent, ["+15550001111"]);
});

test("suppresses sends to an opted-out phone", async () => {
  const store = memoryStore();
  store.setOptedOut("+15550001111", true);
  const sent: string[] = [];
  const result = await sendSms("+15550001111", "hi", async (to) => void sent.push(to), () => {}, store);
  assert.equal(result, "suppressed");
  assert.deepEqual(sent, []);
});
EOF
eval_write src/sms/opt-out.test.ts <<'EOF'
import { test } from "node:test";
import assert from "node:assert/strict";
import { handleInbound } from "./opt-out.ts";
import { memoryStore } from "./store.ts";

const phone = "+15550001111";
const msg = (sid: string, body: string) => ({ MessageSid: sid, From: phone, Body: body });
const noLog = () => {};

test("STOP opts the phone out, in any case and with whitespace", () => {
  const store = memoryStore();
  assert.equal(handleInbound(msg("SM1", "  stop "), store, noLog), "opted_out");
  assert.equal(store.isOptedOut(phone), true);
});

test("START opts the phone back in", () => {
  const store = memoryStore();
  handleInbound(msg("SM1", "STOP"), store, noLog);
  assert.equal(handleInbound(msg("SM2", "START"), store, noLog), "opted_in");
  assert.equal(store.isOptedOut(phone), false);
});

test("a repeated delivery of the same message changes nothing", () => {
  const store = memoryStore();
  handleInbound(msg("SM1", "STOP"), store, noLog);
  handleInbound(msg("SM2", "START"), store, noLog);
  assert.equal(handleInbound(msg("SM1", "STOP"), store, noLog), "duplicate");
  assert.equal(store.isOptedOut(phone), false);
});

test("other replies are left alone", () => {
  const store = memoryStore();
  assert.equal(handleInbound(msg("SM1", "thanks!"), store, noLog), "ignored");
  assert.equal(store.isOptedOut(phone), false);
});
EOF
# Half staged, half not, the way work usually sits.
git add src/sms/opt-out.ts src/sms/opt-out.test.ts
eval_gh
cp "$EVAL_LIB_DIR/gh_world.py" .git/local/gh_world.py
python3 .git/local/gh_world.py install <<'JSON'
{ "repo": "bnle/notify-service", "next_pr": 88 }
JSON
