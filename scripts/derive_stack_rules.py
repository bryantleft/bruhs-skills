#!/usr/bin/env python3
"""derive_stack_rules.py — Emit stack-specific behavioral rules as markdown.

Reads project state JSON on stdin (the same shape that lives inside the
bruhs:state block) and prints a small, curated set of rules to stdout in
markdown — one bullet group per detected stack signal. Pipe the output
into `sync_bruhs_block.py --kind rules`.

Design intent:
    - Inject ONLY stack-derived rules (deterministic from detection).
    - Do NOT inject universal "behavioral rules" — those should be
      hand-written by the user, per the article's argument that rules
      must map to *that user's* failure modes.
    - Keep each rule short, concrete, and high-signal. Drop the rest.

Output is markdown, not JSON. Empty when nothing matches; the sync
script will render a `_No stack-specific rules detected._` placeholder.

Usage:
    cat state.json | derive_stack_rules.py
    cat state.json | derive_stack_rules.py --json   # emit signals as JSON (debug)

Exit codes:
    0 — success (even when no rules match)
    2 — invalid JSON on stdin
"""

from __future__ import annotations

import argparse
import json
import sys
from typing import Iterable

# Rule library. Keys are normalized signal tokens (lower-case, hyphen-free
# where possible) compared against the detected stack. Values are bullet
# lists rendered as-is. Keep entries small and high-signal — the article
# warns that long auto-injected sections hurt compliance.
RULES: dict[str, tuple[str, list[str]]] = {
    "convex": (
        "Convex",
        [
            "Convex actions that import the `ai` SDK MUST live in a file whose first line is `'use node'`. Split Node.js actions out of files containing queries/mutations.",
            "`convertToModelMessages()` returns a Promise — always `await` it.",
            "Required env vars (`AI_GATEWAY_API_KEY`, etc.) must be set in **both** the Next.js env and the Convex env (`npx convex env set`).",
        ],
    ),
    "better-auth": (
        "Better Auth",
        [
            "Every API route that mutates state MUST check `isAuthenticated()` from `@/lib/auth-server` before doing work.",
            "Wrap `req.json()` in try/catch — malformed bodies must not 500.",
        ],
    ),
    "biome": (
        "Biome",
        [
            "Type-only imports require the `type` keyword: `import { type Foo } from 'x'`.",
            "Biome auto-sorts imports alphabetically within braces — don't fight it.",
            "Single quotes, no semicolons, 2-space indent.",
        ],
    ),
    "shadcn": (
        "shadcn/ui",
        [
            "Check `components/ui/` (or `packages/ui/`) before creating a new primitive — there's probably already one.",
            "Install components via the shadcn MCP / `pnpm dlx shadcn@latest add <name>`, never copy-paste manually.",
        ],
    ),
    "tailwind": (
        "Tailwind",
        [
            "Use tokens from the design system (`design-system.json` if present) before introducing arbitrary values like `text-[#abc]`.",
        ],
    ),
    "drizzle-postgres": (
        "Drizzle",
        [
            "Never edit a committed migration. Schema changes create a new migration file.",
        ],
    ),
    "prisma": (
        "Prisma",
        [
            "Schema changes require `pnpm prisma migrate dev` — never hand-edit the generated SQL.",
        ],
    ),
    "nextjs": (
        "Next.js (App Router)",
        [
            "Server Components by default. Add `'use client'` only when you need state, effects, or browser APIs.",
            "Fetch data inside async Server Components — don't fall back to client `useEffect` for initial loads.",
        ],
    ),
    "tanstack-query": (
        "TanStack Query",
        [
            "`queryKey` must be a stable, serializable array — don't put functions or unsorted objects in it.",
            "After a mutation, `invalidateQueries` the affected keys rather than refetching by hand.",
        ],
    ),
    "vercel-ai-sdk": (
        "Vercel AI SDK",
        [
            "AI SDK v6+: `convertToModelMessages()` is async — `await` it.",
            "Use the AI Gateway (`gateway('provider/model')`) over per-provider clients when possible.",
        ],
    ),
    "zustand": (
        "Zustand",
        [
            "Subscribe with a selector + `shallow` for object/array slices to avoid extra re-renders.",
            "Don't put non-serializable values (functions, DOM refs) in persisted slices.",
        ],
    ),
    "effect": (
        "Effect",
        [
            "Errors belong in the Effect's error channel, not thrown. Use `Effect.fail` / typed error classes.",
            "Reach for `Layer` for dependency injection — don't construct services per request.",
        ],
    ),
    "vitest": (
        "Vitest",
        [
            "Run `pnpm vitest run <file>` for single-file runs; reserve watch mode for local dev.",
        ],
    ),
    "modal": (
        "Modal (GPU)",
        [
            "Cold starts are expensive — batch invocations and cache model weights in the container, don't re-load per request.",
        ],
    ),
    "tailscale": (
        "Tailscale",
        [
            "Scope ACL tags narrowly (`tag:crawler`, `tag:admin`) — avoid blanket `tag:server` grants.",
            "Prefer embedding via `tsnet` over running a sidecar daemon when the service is yours to modify.",
            "Don't hardcode MagicDNS hostnames — read them from env vars so non-tailnet devs and CI can override.",
        ],
    ),
}

# Synonyms: things that show up in stack detection but should map to a
# canonical rule key.
SYNONYMS: dict[str, str] = {
    "next.js": "nextjs",
    "next": "nextjs",
    "@ai-sdk/react": "vercel-ai-sdk",
    "ai-sdk": "vercel-ai-sdk",
    "tailwind css": "tailwind",
    "shadcn/ui": "shadcn",
    "drizzle": "drizzle-postgres",
    "effect-ts": "effect",
    "@tanstack/react-query": "tanstack-query",
}


def normalize(token: str) -> str:
    t = token.strip().lower()
    return SYNONYMS.get(t, t)


def collect_signals(state: dict) -> list[str]:
    """Flatten the stack/tooling/integrations dicts into a list of signals."""
    signals: list[str] = []

    def push(v):
        if isinstance(v, str):
            signals.append(normalize(v))
        elif isinstance(v, list):
            for x in v:
                if isinstance(x, str):
                    signals.append(normalize(x))

    stack = state.get("stack") or {}
    for key in (
        "framework",
        "frameworks",
        "styling",
        "database",
        "auth",
        "libraries",
        "state",
        "animation",
        "ai",
        "workers",
        "payments",
        "email",
        "testing",
        "tooling",
        "infra",
        "networking",
        "gpu",
        "observability",
        "llmObservability",
    ):
        push(stack.get(key))

    tooling = state.get("tooling") or {}
    push(tooling.get("mcps"))
    push(tooling.get("skills"))

    # Dedupe, preserve order
    seen: set[str] = set()
    out: list[str] = []
    for s in signals:
        if not s or s in seen:
            continue
        seen.add(s)
        out.append(s)
    return out


def render_rules(matched: Iterable[str]) -> str:
    lines: list[str] = []
    rendered: set[str] = set()
    for sig in matched:
        if sig not in RULES or sig in rendered:
            continue
        rendered.add(sig)
        heading, bullets = RULES[sig]
        lines.append(f"#### {heading}")
        for b in bullets:
            lines.append(f"- {b}")
        lines.append("")
    return "\n".join(lines).rstrip()


def main(argv: list[str]) -> int:
    parser = argparse.ArgumentParser(prog="derive_stack_rules.py")
    parser.add_argument(
        "--json",
        action="store_true",
        help="Emit matched signals as JSON (debug).",
    )
    args = parser.parse_args(argv[1:])

    raw = sys.stdin.read()
    if not raw.strip():
        print("error: no JSON received on stdin", file=sys.stderr)
        return 2

    try:
        state = json.loads(raw)
    except json.JSONDecodeError as exc:
        print(f"error: invalid JSON on stdin: {exc}", file=sys.stderr)
        return 2

    if not isinstance(state, dict):
        print("error: state must be a JSON object", file=sys.stderr)
        return 2

    signals = collect_signals(state)
    matched = [s for s in signals if s in RULES]

    if args.json:
        json.dump(
            {"signals": signals, "matched": matched},
            sys.stdout,
            indent=2,
        )
        sys.stdout.write("\n")
        return 0

    sys.stdout.write(render_rules(matched) + "\n")
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv))
