# bruhs

End-to-end development lifecycle for AI coding agents — scaffold projects, plan and build features, open and review PRs, clean up after merge, audit codebases, surface architectural deepenings, drill the test safety net, and improve UI polish/motion quality. Works with any agent that reads `CLAUDE.md` or `AGENTS.md`.

## Installation

```bash
npx skills add bryantleft/bruhs-skills
```

## Usage

```bash
/bruhs              # Interactive selection
/bruhs:spawn        # Create new project or add to monorepo
/bruhs:claim        # Initialize config for existing project
/bruhs:cook         # Plan + Build a feature end-to-end
/bruhs:yeet         # Ship: Linear ticket → Branch → Commit → PR
/bruhs:peep         # Address PR review comments and merge
/bruhs:dip          # Clean up after merge and switch to base branch
/bruhs:doodle       # Render architecture diagrams (PR, module, deps, compare, map)
/bruhs:slop         # Clean up AI slop (senior engineer audit)
/bruhs:deepen       # Find shallow modules, propose architectural deepenings
/bruhs:drill        # Find missing/weak test-infra layers, propose adoptions
```

## Commands

### `/bruhs:claim`

Initialize bruhs for an existing project by writing `bruhs:state` and `bruhs:rules` marker blocks into `CLAUDE.md` and `AGENTS.md` — auto-detect stack, wire up Linear, detect installed MCPs. Use when adopting bruhs on a repo that wasn't created via `/bruhs:spawn`. Migrates legacy `.claude/bruhs.json` and prompts before deleting the old file.

### `/bruhs:spawn`

Create a new project from scratch or add an app/package to an existing monorepo.

**Workflow:** detect monorepo context → Structure → Project Type → Language → Framework → Stack. Scaffolds via official CLIs (pnpm for TS, cargo for Rust, uv for Python), creates Linear project + initial tickets, wires up GitHub Actions, writes `bruhs:state` and `bruhs:rules` blocks into `CLAUDE.md` + `AGENTS.md`.

**Supported stacks:** Next.js, TanStack Start, Astro, Tauri, Electron, React Native, Expo, Hono, FastAPI, Axum, Leptos, GPUI, Rojo, Node/uv/cargo CLIs.

### `/bruhs:cook`

Plan and build a feature end-to-end.

**Workflow:** understand → explore codebase → plan (2–3 approaches, user picks) → setup → **RED-GREEN-REFACTOR** build cycle → self-review → run `scripts/validate_pr_ready.sh` → ready to ship.

For UI-only changes where TDD isn't feasible, the Build step offers an explicit opt-in to manual verification.

**Full lifecycle:** cook → yeet → peep → dip.

### `/bruhs:yeet`

Ship staged work. Runs the project's full verification suite before committing — failures surface an `AskUserQuestion` with Show / Fix / Ship-anyway / Abort; "Ship anyway" injects a warning into the PR body's Test plan.

**Workflow:** analyze diff → categorize (feat/fix/chore/refactor) → **validate pre-ship** → create Linear ticket (or reuse cook's context) → branch via Linear's `gitBranchName` → commit with `Fixes TICKET-ID` → push → `gh pr create` → update Linear to In Review.

Git-only mode skips Linear if not configured.

### `/bruhs:peep`

Address PR review comments using isolated subagents — one per thread, no context bleed between threads.

**Local validation per fix**: each subagent applies its proposed fix, runs the project's typecheck + lint + affected tests, reverts, and reports `VALIDATION_STATUS` (passed/failed/skipped). Auto-apply gated on validation passing. Full-suite validation runs once before commit to catch cross-file interactions.

**Invocation:**
- `/bruhs:peep` — current branch's PR
- `/bruhs:peep 42` — specific PR number
- `/bruhs:peep PERDIX-145` — find PR by Linear ticket

### `/bruhs:dip`

Post-merge cleanup. Switch to base branch → pull → delete merged feature branch (local + remote) → restore any stashed changes from cook.

### `/bruhs:doodle`

Render architectural diagrams as tldraw images. Requires an MCP server exposing `create_diagram` (see [bryantleft/tldraw-mcp](https://github.com/bryantleft/tldraw-mcp) or `bassimeledath/tldraw-render`).

**Modes:** `pr` (changed files + edges from a PR), `module` (internal structure of a module), `deps` (forward imports), `dependents` (reverse), `compare` (diff between refs), `map` (full tree), `freeform` (natural-language prompt).

**Outputs:** `--out <path>`, `--pr-comment`, `--gist`, `--commit` into `.bruhs/diagrams/`.

### `/bruhs:slop`

Deep codebase audit — acts as a nitpicky senior engineer. Priority hierarchy:

| Priority | Category |
|---|---|
| **1** | Type signatures — missing return types, hidden errors, wide types, mutable parameters |
| **2** | Security — SQL injection, XSS, hardcoded secrets, unbounded input |
| **3** | Performance — N+1, `await`-in-loop, sync-in-async, per-request clients, unbounded concurrency |
| **4** | Error handling — errors not in types, swallowed errors, generic `Error` |
| **5** | Architecture — circular deps, mixed abstraction levels, unnecessary abstractions |
| **6** | Immutability — parameter mutation, hidden state changes |
| **7** | Code style — over-commenting, verbose names, dead code |

**Invocation:** `/bruhs:slop [path] [--fix|--report]`. Severity levels: `relaxed` / `balanced` / `nitpicky` (default) / `brutal`.

### `/bruhs:deepen`

Find **shallow modules** — modules whose interface is nearly as complex as their implementation — and propose **deepening opportunities** that hide more behaviour behind smaller interfaces. Structural audit, distinct from `/bruhs:slop`'s line-level lens. Adapted from Matt Pocock's `improve-codebase-architecture` skill (Ousterhout + Feathers lineage).

**Workflow:** Explore (read the domain glossary, trace 2–3 call paths, note bouncing / pass-through / leaky implementations / scattered invariants) → Present candidates (ranked by leverage × locality, 5–8 max) → Grilling loop (design the deepened module's interface twice — Minimal / Extensible / Caller-optimised / Ports & Adapters — pick one with reasons). Hands off to `/bruhs:cook` for implementation.

**Vocabulary:** module, interface, depth, seam, adapter, leverage, locality. **Use these exactly.**

**Invocation:** `/bruhs:deepen [path | module-name] [--no-explore]`.

### `/bruhs:drill`

Find **missing or weak layers** in the test safety net and propose adoption plans. The companion to `/bruhs:deepen`: deepen modules, drill tests. Same 3-phase workflow on the 8-layer testing-infra axis (acceptance specs, unit tests, coverage gate, mutation runner, complexity composite, architecture checker, test-code linter, CI orchestrator).

**Workflow:** Explore (read CI workflow files, test config, ADRs; map each layer to absent / advisory / gated / rotting; apply the "what would slip through" test) → Present candidates (ranked by bug-class-prevented × cross-layer leverage) → Grilling loop (design the gate twice — Strict day 1 / Ratchet-only / Scoped pilot / Cross-layer fusion). Hands off to `/bruhs:cook` for adoption.

**Key principles:** hard gate / advisory / ratchet — pick one, defend it; the CI orchestrator is load-bearing (layers 1–7 without a real gate are theatre); the "what would slip through" test (no concrete bug class → not a candidate).

**Invocation:** `/bruhs:drill [path | layer-name] [--no-explore]`.

## Best Practices

Stack-agnostic and stack-specific guidance, loaded conditionally by `cook` and `slop` based on the `bruhs:state` block in `CLAUDE.md`:

| File | Scope |
|---|---|
| `practices/type-driven-design.md` | **Primary** — type signatures, explicit errors, immutability |
| `practices/architecture-deepening.md` | Module depth, seams, dependency categories (used by deepen) |
| `practices/testing-infrastructure.md` | The 8 testing layers, gating posture, kill ratio (used by drill) |
| `practices/_common.md` | Universal — naming, git, errors, testing |
| `practices/pr-review.md` | PR authoring + review etiquette (used by peep) |
| `practices/typescript-react.md` | TypeScript + React (Next.js, React Native, Tauri, Electron) |
| `practices/typescript-hono.md` | Hono framework patterns |
| `practices/python.md` | Modern Python 3.12+ with Astral tooling (uv/ruff/ty) |
| `practices/python-fastapi.md` | FastAPI specifics (builds on python.md) |
| `practices/effect-ts.md` + `practices/effect-*.md` | Effect-TS (service, error, schema, layer, RPC, atom, anti-patterns) |
| `practices/rust.md` + `practices/rust-*.md` | Rust (ownership, errors, async, axum, leptos, gpui, type-state) |
| `practices/ui-design.md` | UI quality (integrates `pbakaus/impeccable` skills plus Emil-derived design engineering) |
| `practices/design-engineering.md` | Emil-derived UI polish, motion standards, animation review, gestures, performance, a11y, and animation vocabulary |

## Utility Scripts

`scripts/` contains deterministic helpers that commands shell out to:

- `detect_stack.py` — read `package.json`/`Cargo.toml`/`pyproject.toml`/etc., output JSON with detected languages, frameworks, styling, DB, auth, testing, tooling.
- `detect_mcp_servers.py` — list MCP servers from `~/.claude.json`, grouped by category.
- `sync_bruhs_block.py` — atomic writer for the `bruhs:state` and `bruhs:rules` blocks inside `CLAUDE.md` and `AGENTS.md`, with schema validation for state.
- `read_bruhs_block.py` — read a marker block back to stdout; falls back to legacy `.claude/bruhs.json` for `--kind state` during the transition.
- `derive_stack_rules.py` — emit stack-specific behavioral rules as markdown given state JSON on stdin.
- `write_bruhs_config.py` *(deprecated)* — thin shim that forwards to `sync_bruhs_block.py --kind state` so existing callers don't break.
- `validate_pr_ready.sh` — run typecheck + lint + tests for the detected stack (Node/Rust/Python/Go); used by `yeet`, `peep`, `cook`.

## Evaluations

`evals/` holds 27 JSON scenarios (3 per command) covering happy path, edge case, and adversarial phrasings. See `evals/README.md` for the manual eval workflow.

## Configuration

Project state lives in two marker-bounded blocks inside `CLAUDE.md` **and** `AGENTS.md` (mirrored). The model reads them every session — no separate config file. Hand-written rules outside the blocks are never touched.

````markdown
<!-- bruhs:state:begin v1 -->
<!-- AUTO-MAINTAINED BY /bruhs. Edits inside this block will be overwritten. -->

### Project State (managed by /bruhs)

```json
{
  "integrations": {
    "linear": {
      "mcpServer": "linear-myworkspace",
      "team": "TEAM-UUID",
      "teamName": "Your Team",
      "project": "PROJECT-UUID",
      "projectName": "Your Project",
      "labels": {
        "feat": "Feature",
        "fix": "Bug",
        "chore": "Chore",
        "refactor": "Improvement"
      }
    }
  },
  "tooling": {
    "mcps": ["linear", "notion", "context7"],
    "skills": ["superpowers", "feature-dev", "commit-commands", "shadcn", "vercel-react-best-practices"]
  },
  "stack": {
    "structure": "single",
    "framework": "nextjs",
    "styling": ["tailwind", "shadcn"],
    "database": ["drizzle-postgres"],
    "auth": "better-auth"
  }
}
```
<!-- bruhs:state:end -->

<!-- bruhs:rules:begin v1 -->
<!-- AUTO-MAINTAINED BY /bruhs. Stack-specific rules derived from detected stack. -->

### Stack-Specific Rules (managed by /bruhs)

#### Next.js (App Router)
- Server Components by default. Add `'use client'` only when you need state, effects, or browser APIs.
- ...
<!-- bruhs:rules:end -->
````

`/bruhs:claim` writes both blocks for you by running `scripts/detect_stack.py`, `scripts/detect_mcp_servers.py`, and `scripts/derive_stack_rules.py`. Legacy `.claude/bruhs.json` files are auto-migrated (with a delete prompt).

**Universal behavioral rules** (the kind that map to *your* failure modes) should be hand-written by you, **outside** the bruhs blocks. The plugin only manages stack-derived rules.

## Linear MCP Setup

Linear integration is optional but enables full ticket management. Uses `mcp-server-linear` with multi-workspace support.

### Quick Setup (Single Workspace)

1. **Get your Linear API key:** Linear → Settings → API → Personal API Keys → "Create key".
2. **Add to `~/.claude.json`:**
   ```json
   {
     "mcpServers": {
       "linear-myworkspace": {
         "type": "stdio",
         "command": "npx",
         "args": ["-y", "mcp-server-linear"],
         "env": { "LINEAR_ACCESS_TOKEN": "lin_api_xxx" }
       }
     }
   }
   ```
3. Restart your AI coding agent.

### Multi-Workspace

Add one entry per workspace with a unique name (e.g. `linear-perdix`, `linear-sonner`). Each project's `bruhs:state` block selects which workspace via `integrations.linear.mcpServer`.

**Tool naming convention:** `mcp__<server-name>__linear_<method>` — e.g. `mcp__linear-sonner__linear_create_issue`.

Run `/mcp` (or your agent's equivalent) to verify connected servers.

## Other Dependencies

- **GitHub CLI (`gh`)** — required for PR creation. Authenticate with `gh auth login`.
- **tldraw MCP** (optional) — required for `/bruhs:doodle`. See the command docs for install hints.

## License

MIT
