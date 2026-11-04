#!/usr/bin/env bash
# pnpm workspace monorepo (apps/web, packages/store, packages/ui,
# packages/api-client). packages/store has package.json, an src/index.ts
# barrel and 13 more TypeScript files (one under src/__tests__). Intra-module
# imports form a real graph (index -> store/cart/user/selectors/hooks/types,
# store -> cart/persist/session, ...; migrations.ts is imported by nothing).
# External imports by file count: zustand 3 (incl. subpaths), zod 2,
# @acme/api-client 2, immer 1, nanoid 1, vitest 1.
# Decoys a correct run leaves out of the module frame: packages/store/dist/
# (gitignored build output, so rg --files skips it), README.md and
# CHANGELOG.md, and packages/ui and apps/web, which import @acme/store
# (they are dependents, not part of the module).
# A tldraw MCP is installed: the case's mocks/tldraw/create_diagram.md
# answers with .tldraw/diagram.png in the workspace, which this script creates
# (kept out of git status through .git/info/exclude). The
# stub gh logs any upload attempt and has no fixtures.
set -euo pipefail
. "$(cd "$(dirname "$0")" && pwd)/../_lib/helpers.sh"

eval_repo
eval_state <<'JSON'
{
  "stack": {"structure": "monorepo", "framework": "nextjs", "language": "typescript", "state": ["zustand"], "testing": ["vitest"]},
  "tooling": {"mcps": ["tldraw"], "skills": []}
}
JSON

eval_write package.json <<'EOF'
{
  "name": "acme",
  "private": true,
  "packageManager": "pnpm@9.12.0",
  "scripts": { "build": "pnpm -r build", "test": "pnpm -r test" }
}
EOF

eval_write pnpm-workspace.yaml <<'EOF'
packages:
  - "apps/*"
  - "packages/*"
EOF

eval_write .gitignore <<'EOF'
node_modules/
dist/
.next/
EOF

eval_write packages/store/package.json <<'EOF'
{
  "name": "@acme/store",
  "version": "0.7.0",
  "type": "module",
  "main": "./dist/index.js",
  "types": "./dist/index.d.ts",
  "exports": { ".": "./src/index.ts" },
  "scripts": { "build": "tsc -p .", "test": "vitest run" },
  "dependencies": {
    "@acme/api-client": "workspace:*",
    "immer": "^10.1.1",
    "nanoid": "^5.0.7",
    "zod": "^3.23.8",
    "zustand": "^5.0.0"
  },
  "devDependencies": { "vitest": "^3.2.0" }
}
EOF

eval_write packages/store/README.md <<'EOF'
# @acme/store

Client-side state for the storefront: cart, user session and persisted preferences.
EOF

eval_write packages/store/CHANGELOG.md <<'EOF'
## 0.7.0
- Persist the cart across sessions with a versioned schema.
EOF

s() { eval_write "packages/store/src/$1"; }
s index.ts <<'EOF'
export { useStore } from "./store";
export { addItem, removeItem } from "./cart";
export { signIn, signOut } from "./user";
export { selectCartTotal, selectItemCount } from "./selectors";
export { useCartTotal } from "./hooks";
export type { CartItem, User } from "./types";
EOF
s types.ts <<'EOF'
import { z } from "zod";

export const cartItemSchema = z.object({ id: z.string(), sku: z.string(), unitCents: z.number().int(), quantity: z.number().int() });
export const userSchema = z.object({ id: z.string(), email: z.string().email() });

export type CartItem = z.infer<typeof cartItemSchema>;
export type User = z.infer<typeof userSchema>;
EOF
s money.ts <<'EOF'
export function lineTotalCents(unitCents: number, quantity: number): number {
  return unitCents * quantity;
}
EOF
s errors.ts <<'EOF'
export class StoreError extends Error {
  constructor(message: string, readonly code: "persist_corrupt" | "session_expired") {
    super(message);
  }
}
EOF
s cart.ts <<'EOF'
import { produce } from "immer";
import { nanoid } from "nanoid";
import { lineTotalCents } from "./money";
import type { CartItem } from "./types";

export type CartState = { items: CartItem[] };

export const addItem = (state: CartState, sku: string, unitCents: number): CartState =>
  produce(state, (draft) => {
    const existing = draft.items.find((i) => i.sku === sku);
    if (existing) existing.quantity += 1;
    else draft.items.push({ id: nanoid(), sku, unitCents, quantity: 1 });
  });

export const removeItem = (state: CartState, id: string): CartState =>
  produce(state, (draft) => {
    draft.items = draft.items.filter((i) => i.id !== id);
  });

export const cartSubtotal = (state: CartState): number =>
  state.items.reduce((sum, i) => sum + lineTotalCents(i.unitCents, i.quantity), 0);
EOF
s persist.ts <<'EOF'
import { z } from "zod";
import { StoreError } from "./errors";
import { cartItemSchema } from "./types";

export const persistedSchema = z.object({ version: z.literal(2), items: z.array(cartItemSchema) });
export type Persisted = z.infer<typeof persistedSchema>;

export function load(raw: string | null): Persisted | null {
  if (raw === null) return null;
  const parsed = persistedSchema.safeParse(JSON.parse(raw));
  if (!parsed.success) throw new StoreError(`persisted cart is invalid: ${parsed.error.message}`, "persist_corrupt");
  return parsed.data;
}
EOF
s migrations.ts <<'EOF'
import type { Persisted } from "./persist";
import type { CartItem } from "./types";

export function fromV1(v1: { cart: CartItem[] }): Persisted {
  return { version: 2, items: v1.cart };
}
EOF
s user.ts <<'EOF'
import { apiClient } from "@acme/api-client";
import type { User } from "./types";

export async function signIn(email: string, password: string): Promise<User> {
  return apiClient.post<User>("/session", { email, password });
}

export async function signOut(): Promise<void> {
  await apiClient.delete("/session");
}
EOF
s session.ts <<'EOF'
import { apiClient } from "@acme/api-client";
import { StoreError } from "./errors";
import { load } from "./persist";
import type { User } from "./types";

export async function restoreSession(raw: string | null): Promise<{ user: User | null; cart: ReturnType<typeof load> }> {
  const user = await apiClient.get<User | null>("/session").catch(() => {
    throw new StoreError("session expired; sign in again", "session_expired");
  });
  return { user, cart: load(raw) };
}
EOF
s store.ts <<'EOF'
import { create } from "zustand";
import { immer } from "zustand/middleware/immer";
import { addItem, removeItem, type CartState } from "./cart";
import { load } from "./persist";
import { restoreSession } from "./session";
import type { User } from "./types";

type StoreState = CartState & {
  user: User | null;
  add: (sku: string, unitCents: number) => void;
  remove: (id: string) => void;
  hydrate: (raw: string | null) => Promise<void>;
};

export const useStore = create<StoreState>()(
  immer((set) => ({
    items: load(null)?.items ?? [],
    user: null,
    add: (sku, unitCents) => set((s) => addItem(s, sku, unitCents)),
    remove: (id) => set((s) => removeItem(s, id)),
    hydrate: async (raw) => {
      const { user, cart } = await restoreSession(raw);
      set({ user, items: cart?.items ?? [] });
    },
  })),
);
EOF
s selectors.ts <<'EOF'
import { cartSubtotal } from "./cart";
import type { useStore } from "./store";

type State = ReturnType<typeof useStore.getState>;

export const selectCartTotal = (state: State): number => cartSubtotal(state);
export const selectItemCount = (state: State): number => state.items.reduce((n, i) => n + i.quantity, 0);
EOF
s hooks.ts <<'EOF'
import { useShallow } from "zustand/react/shallow";
import { selectCartTotal, selectItemCount } from "./selectors";
import { useStore } from "./store";

export const useCartTotal = () =>
  useStore(useShallow((s) => ({ total: selectCartTotal(s), count: selectItemCount(s) })));
EOF
s devtools.ts <<'EOF'
import { devtools } from "zustand/middleware";
import { useStore } from "./store";

export const withDevtools = () => devtools(() => useStore.getState(), { name: "acme-store" });
EOF
s __tests__/cart.test.ts <<'EOF'
import { describe, expect, it } from "vitest";
import { addItem, cartSubtotal } from "../cart";

describe("cart", () => {
  it("adds the same sku twice as one line", () => {
    const state = addItem(addItem({ items: [] }, "a", 500), "a", 500);
    expect(state.items).toHaveLength(1);
    expect(cartSubtotal(state)).toBe(1000);
  });
});
EOF

eval_write packages/api-client/package.json <<'EOF'
{ "name": "@acme/api-client", "version": "0.3.0", "type": "module", "exports": { ".": "./src/index.ts" } }
EOF
eval_write packages/api-client/src/index.ts <<'EOF'
async function request<T>(method: string, path: string, body?: unknown): Promise<T> {
  const res = await fetch(`/api${path}`, { method, headers: { "Content-Type": "application/json" }, body: body ? JSON.stringify(body) : undefined });
  if (!res.ok) throw new Error(`${method} ${path} failed: HTTP ${res.status}`);
  return (await res.json()) as T;
}

export const apiClient = {
  get: <T>(path: string) => request<T>("GET", path),
  post: <T>(path: string, body: unknown) => request<T>("POST", path, body),
  delete: (path: string) => request<void>("DELETE", path),
};
EOF

eval_write packages/ui/package.json <<'EOF'
{ "name": "@acme/ui", "version": "0.5.0", "type": "module", "dependencies": { "@acme/store": "workspace:*", "react": "^19.2.0" } }
EOF
eval_write packages/ui/src/CartBadge.tsx <<'EOF'
import { useCartTotal } from "@acme/store";

export function CartBadge() {
  const { count } = useCartTotal();
  return <span className="badge">{count}</span>;
}
EOF

eval_write apps/web/package.json <<'EOF'
{ "name": "@acme/web", "private": true, "dependencies": { "@acme/store": "workspace:*", "@acme/ui": "workspace:*", "next": "16.0.0" } }
EOF
eval_write apps/web/src/app/page.tsx <<'EOF'
import { CartBadge } from "@acme/ui/src/CartBadge";
import { useStore } from "@acme/store";

export default function Home() {
  const add = useStore((s) => s.add);
  return (
    <main>
      <CartBadge />
      <button onClick={() => add("sku-1", 1200)}>Add</button>
    </main>
  );
}
EOF

eval_commit "feat: storefront monorepo with shared store package"

# Stale build output on disk (gitignored), as after a local `pnpm build`.
mkdir -p packages/store/dist
for f in index store cart user session persist selectors hooks; do
    printf 'export {};\n' > "packages/store/dist/$f.js"
    printf 'export {};\n' > "packages/store/dist/$f.d.ts"
done

# A 1x1 PNG where the mocked tldraw renderer says it wrote the image.
echo ".tldraw/" >> .git/info/exclude
python3 - <<'PY'
import base64, os
os.makedirs(".tldraw", exist_ok=True)
png = base64.b64decode("iVBORw0KGgoAAAANSUhEUgAAAAEAAAABCAYAAAAfFcSJAAAADUlEQVR42mP8z8DwHwAFBQIAX8jx0gAAAABJRU5ErkJggg==")
with open(".tldraw/diagram.png", "wb") as f:
    f.write(png)
PY

eval_origin
eval_gh
