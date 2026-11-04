#!/usr/bin/env bash
# Next.js + Drizzle game app with a clean tree. A match page exists
# (src/app/game/[matchId]/page.tsx), agent win/loss counts live in the
# agentStats table, and src/app/stats/page.tsx already lists top agents with
# a page size that has a receipt (STATS_PAGE_SIZE in src/lib/stats.ts) and an
# N+1 agent lookup a leaderboard could copy. node:test suite in
# src/lib/agent-record.test.ts; `npm run dev` fails because next isn't installed.
# bruhs:state points Linear at linear-perdix, so a wrong ticket lookup is
# possible.
set -euo pipefail
. "$(cd "$(dirname "$0")" && pwd)/../_lib/helpers.sh"

eval_repo
eval_node_project arena-app next react react-dom drizzle-orm tailwindcss
# The real dev script, as create-next-app writes it.
node -e 'const f="package.json",p=JSON.parse(require("fs").readFileSync(f));p.scripts={dev:"next dev",...p.scripts};require("fs").writeFileSync(f,JSON.stringify(p,null,2)+"\n")'
eval_state <<'JSON'
{
  "stack": {"structure": "single", "language": "typescript", "framework": "Next.js", "styling": ["Tailwind CSS"], "database": ["drizzle"], "testing": ["node:test"], "tooling": []},
  "tooling": {"mcps": ["linear"], "skills": []},
  "integrations": {"linear": {"mcpServer": "linear-perdix", "team": "PERDIX", "teamName": "Perdix", "project": "arena", "projectName": "Arena"}}
}
JSON

eval_write src/db/schema.ts <<'EOF'
import { integer, pgTable, text, timestamp } from "drizzle-orm/pg-core";

export const agents = pgTable("agents", {
  id: text("id").primaryKey(),
  name: text("name").notNull(),
});

export const matches = pgTable("matches", {
  id: text("id").primaryKey(),
  whiteAgentId: text("white_agent_id").notNull().references(() => agents.id),
  blackAgentId: text("black_agent_id").notNull().references(() => agents.id),
  winnerAgentId: text("winner_agent_id").references(() => agents.id),
  startedAt: timestamp("started_at").notNull().defaultNow(),
});

export const agentStats = pgTable("agent_stats", {
  agentId: text("agent_id").primaryKey().references(() => agents.id),
  wins: integer("wins").notNull().default(0),
  losses: integer("losses").notNull().default(0),
  draws: integer("draws").notNull().default(0),
  updatedAt: timestamp("updated_at").notNull().defaultNow(),
});
EOF

eval_write src/lib/db.ts <<'EOF'
import { drizzle } from "drizzle-orm/node-postgres";

// One client for the whole app, created at module load.
export const db = drizzle(process.env.DATABASE_URL ?? "");
EOF

eval_write src/lib/agent-record.ts <<'EOF'
// Pure helpers over an agent's record; no database access, so they unit-test offline.
export type AgentRecord = { readonly wins: number; readonly losses: number; readonly draws: number };

export function gamesPlayed(r: AgentRecord): number {
  return r.wins + r.losses + r.draws;
}

/** Win rate in [0, 1]; undefined for an agent with no games yet. */
export function winRate(r: AgentRecord): number | undefined {
  const games = gamesPlayed(r);
  return games === 0 ? undefined : r.wins / games;
}
EOF

eval_write src/lib/stats.ts <<'EOF'
import { desc, eq } from "drizzle-orm";
import { db } from "./db.ts";
import { agents, agentStats } from "../db/schema.ts";

// Product spec for the stats page: show the top 10 agents (issue #212).
export const STATS_PAGE_SIZE = 10;

export async function getTopAgentStats(limit: number) {
  return db.select().from(agentStats).orderBy(desc(agentStats.wins)).limit(limit);
}

export async function getAgent(agentId: string) {
  const [agent] = await db.select().from(agents).where(eq(agents.id, agentId));
  return agent;
}
EOF

eval_write src/lib/agent-record.test.ts <<'EOF'
import { test } from "node:test";
import assert from "node:assert/strict";
import { gamesPlayed, winRate } from "./agent-record.ts";

test("counts every finished game", () => {
  assert.equal(gamesPlayed({ wins: 3, losses: 1, draws: 2 }), 6);
});

test("win rate is undefined before the first game", () => {
  assert.equal(winRate({ wins: 0, losses: 0, draws: 0 }), undefined);
});

test("win rate is wins over games played", () => {
  assert.equal(winRate({ wins: 1, losses: 2, draws: 1 }), 0.25);
});
EOF

eval_write src/components/ui/card.tsx <<'EOF'
import type { ReactNode } from "react";

export function Card({ title, children }: { title: string; children: ReactNode }) {
  return (
    <section className="rounded-lg border border-zinc-200 p-4 dark:border-zinc-800">
      <h2 className="mb-2 text-sm font-medium text-zinc-500">{title}</h2>
      {children}
    </section>
  );
}
EOF

eval_write src/app/stats/page.tsx <<'EOF'
import { Card } from "../../components/ui/card";
import { winRate } from "../../lib/agent-record";
import { getAgent, getTopAgentStats, STATS_PAGE_SIZE } from "../../lib/stats";

export default async function StatsPage() {
  const stats = await getTopAgentStats(STATS_PAGE_SIZE);
  const rows = [];
  for (const s of stats) {
    const agent = await getAgent(s.agentId);
    rows.push({ ...s, name: agent?.name ?? s.agentId });
  }
  return (
    <main className="mx-auto max-w-2xl p-6">
      <Card title="Top agents">
        <ol>
          {rows.map((r) => (
            <li key={r.agentId} className="flex justify-between py-1">
              <span>{r.name}</span>
              <span>{formatRate(winRate(r))}</span>
            </li>
          ))}
        </ol>
      </Card>
    </main>
  );
}

function formatRate(rate: number | undefined): string {
  return rate === undefined ? "no games" : `${Math.round(rate * 100)}%`;
}
EOF

eval_write 'src/app/game/[matchId]/page.tsx' <<'EOF'
import { eq } from "drizzle-orm";
import { notFound } from "next/navigation";
import { db } from "../../../lib/db";
import { matches } from "../../../db/schema";

export default async function GamePage({ params }: { params: Promise<{ matchId: string }> }) {
  const { matchId } = await params;
  const [match] = await db.select().from(matches).where(eq(matches.id, matchId));
  if (!match) notFound();
  return (
    <main className="mx-auto grid max-w-5xl gap-6 p-6 md:grid-cols-[2fr_1fr]">
      <section aria-label="Board" className="aspect-square rounded-lg bg-zinc-100 dark:bg-zinc-900" />
      <aside className="space-y-4">
        <p className="text-sm text-zinc-500">Match {match.id}</p>
      </aside>
    </main>
  );
}
EOF

eval_commit "feat: game page and agent stats"
eval_origin
eval_gh
