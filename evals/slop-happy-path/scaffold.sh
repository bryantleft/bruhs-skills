#!/usr/bin/env bash
# Next.js app (bruhs:state framework=nextjs) with a small src/components/.
# Planted: UserCard.tsx mirrors props into state with a useEffect (derived
# state), Form.tsx reads the API response as `any` and aborts after an
# unexplained 10000 ms, HeroImage.tsx passes a fresh inline style object to a
# memo()'d child on every render. Decoys that are fine: ThemeWatcher.tsx's
# useEffect syncs with an external system (matchMedia, with cleanup) and
# Badge.tsx's `as const` is on a literal, not on external data.
set -euo pipefail
. "$(cd "$(dirname "$0")" && pwd)/../_lib/helpers.sh"

eval_repo
eval_node_project team-directory next react react-dom tailwindcss
eval_state <<'JSON'
{
  "stack": {"structure": "single", "framework": "nextjs", "language": "typescript", "styling": ["tailwind"], "testing": ["node:test"]},
  "tooling": {"mcps": [], "skills": []}
}
JSON

eval_write src/lib/types.ts <<'EOF'
export type User = {
  id: string;
  firstName: string;
  lastName: string;
  email: string;
  avatarUrl: string | null;
  role: "member" | "admin";
};
EOF

eval_write src/lib/format.ts <<'EOF'
export function formatRole(role: "member" | "admin"): string {
  return role === "admin" ? "Admin" : "Member";
}
EOF

eval_write src/lib/format.test.ts <<'EOF'
import { test } from "node:test";
import assert from "node:assert/strict";
import { formatRole } from "./format.ts";

test("admins are labelled Admin", () => {
  assert.equal(formatRole("admin"), "Admin");
});
EOF

eval_write src/components/Avatar.tsx <<'EOF'
type AvatarProps = { url: string | null; initials: string };

export function Avatar({ url, initials }: AvatarProps) {
  if (url) {
    return <img src={url} alt="" className="size-10 rounded-full" />;
  }
  return (
    <span className="grid size-10 place-items-center rounded-full bg-neutral-200 text-sm font-medium">
      {initials}
    </span>
  );
}
EOF

eval_write src/components/Badge.tsx <<'EOF'
const VARIANTS = {
  member: "bg-neutral-100 text-neutral-700",
  admin: "bg-amber-100 text-amber-800",
} as const;

type BadgeProps = { variant: keyof typeof VARIANTS; children: React.ReactNode };

export function Badge({ variant, children }: BadgeProps) {
  return <span className={`rounded px-2 py-0.5 text-xs ${VARIANTS[variant]}`}>{children}</span>;
}
EOF

eval_write src/components/UserCard.tsx <<'EOF'
"use client";

import { useEffect, useState } from "react";
import type { User } from "../lib/types";
import { formatRole } from "../lib/format";
import { Avatar } from "./Avatar";
import { Badge } from "./Badge";

export function UserCard({ user }: { user: User }) {
  const [displayName, setDisplayName] = useState("");
  const [initials, setInitials] = useState("");

  useEffect(() => {
    setDisplayName(`${user.firstName} ${user.lastName}`);
    setInitials(`${user.firstName[0]}${user.lastName[0]}`.toUpperCase());
  }, [user.firstName, user.lastName]);

  return (
    <article className="flex items-center gap-3 rounded-lg border p-4">
      <Avatar url={user.avatarUrl} initials={initials} />
      <div>
        <h3 className="font-medium">{displayName}</h3>
        <p className="text-sm text-neutral-500">{user.email}</p>
      </div>
      <Badge variant={user.role}>{formatRole(user.role)}</Badge>
    </article>
  );
}
EOF

eval_write src/components/Form.tsx <<'EOF'
"use client";

import { useState } from "react";
import type { User } from "../lib/types";

type FormProps = { userId: string; onSaved: (user: User) => void };

export function Form({ userId, onSaved }: FormProps) {
  const [name, setName] = useState("");
  const [error, setError] = useState<string | null>(null);

  async function handleSubmit(event: React.FormEvent<HTMLFormElement>) {
    event.preventDefault();
    const res = await fetch(`/api/users/${userId}`, {
      method: "PATCH",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ firstName: name }),
      signal: AbortSignal.timeout(10000),
    });
    const data: any = await res.json();
    if (!res.ok) {
      setError(data.message);
      return;
    }
    onSaved(data.user);
  }

  return (
    <form onSubmit={handleSubmit} className="space-y-2">
      <label className="block text-sm font-medium" htmlFor="first-name">
        First name
      </label>
      <input
        id="first-name"
        value={name}
        onChange={(event) => setName(event.target.value)}
        className="w-full rounded border px-3 py-2"
      />
      {error && <p className="text-sm text-red-600">{error}</p>}
      <button type="submit" className="rounded bg-black px-3 py-2 text-white">
        Save
      </button>
    </form>
  );
}
EOF

eval_write src/components/HeroImage.tsx <<'EOF'
import { memo } from "react";

type FadeImageProps = { src: string; alt: string; style: React.CSSProperties };

const FadeImage = memo(function FadeImage({ src, alt, style }: FadeImageProps) {
  return <img src={src} alt={alt} style={style} className="transition-opacity duration-200" />;
});

type HeroImageProps = { src: string; alt: string; caption: string };

export function HeroImage({ src, alt, caption }: HeroImageProps) {
  return (
    <figure className="relative">
      <FadeImage src={src} alt={alt} style={{ objectFit: "cover", width: "100%", aspectRatio: "16 / 9" }} />
      <figcaption className="absolute bottom-2 left-2 text-sm text-white">{caption}</figcaption>
    </figure>
  );
}
EOF

eval_write src/components/ThemeWatcher.tsx <<'EOF'
"use client";

import { useEffect } from "react";

export function ThemeWatcher() {
  useEffect(() => {
    const query = window.matchMedia("(prefers-color-scheme: dark)");
    const apply = () => document.documentElement.classList.toggle("dark", query.matches);
    apply();
    query.addEventListener("change", apply);
    return () => query.removeEventListener("change", apply);
  }, []);

  return null;
}
EOF

eval_write src/components/index.ts <<'EOF'
export { Avatar } from "./Avatar";
export { Badge } from "./Badge";
export { Form } from "./Form";
export { HeroImage } from "./HeroImage";
export { ThemeWatcher } from "./ThemeWatcher";
export { UserCard } from "./UserCard";
EOF

eval_write src/app/page.tsx <<'EOF'
import { HeroImage, ThemeWatcher, UserCard } from "../components";
import type { User } from "../lib/types";

const team: User[] = [
  { id: "u1", firstName: "Ada", lastName: "Lovelace", email: "ada@example.com", avatarUrl: null, role: "admin" },
  { id: "u2", firstName: "Alan", lastName: "Turing", email: "alan@example.com", avatarUrl: null, role: "member" },
];

export default function Page() {
  return (
    <main className="mx-auto max-w-2xl space-y-6 p-6">
      <ThemeWatcher />
      <HeroImage src="/team.jpg" alt="The team at the offsite" caption="Offsite 2026" />
      {team.map((user) => (
        <UserCard key={user.id} user={user} />
      ))}
    </main>
  );
}
EOF

eval_commit "feat: team directory with profile form"
eval_origin
eval_gh
