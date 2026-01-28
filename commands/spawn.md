---
description: Create new project OR add to monorepo
---

# spawn - Project Scaffolding

Create a new project from scratch or add an app/package to an existing monorepo.

## Invocation

- `/bruhs:spawn <name>` - Create new project with given name
- `/bruhs:spawn` - In existing monorepo, add new app or package

## Workflow

### Step 1: Detect Context

Check if we're in a monorepo:

```bash
# Check for turbo.json or pnpm-workspace.yaml
ls turbo.json pnpm-workspace.yaml 2>/dev/null
```

If monorepo detected, ask:
- Add new app to this monorepo?
- Add new package to this monorepo?
- Create entirely new project (outside)?

### Step 2: Selection Flow

Guide user through selections top-down. Each choice filters subsequent options.

```
Structure → Project Type → Language → Framework → Stack Additions
```

#### 2a: Structure (if new project)

Ask user:
```
Project structure:
○ Monorepo (Turborepo) - Multiple apps/packages
○ Single package - Standalone project
```

#### 2b: Project Type

Ask user:
```
What are you building?
○ Web - Website or web application
○ Desktop - Desktop application
○ Mobile - Mobile application
○ Extension - Browser or VS Code extension
○ Roblox - Roblox game
○ CLI - Command-line tool
○ Library - Reusable package
○ API - Backend service
```

#### 2c: Language (filtered by project type)

| Project Type | Available Languages |
|--------------|---------------------|
| Web | TypeScript |
| Desktop | TypeScript, Rust |
| Mobile | TypeScript |
| Extension | TypeScript |
| Roblox | Luau |
| CLI | TypeScript, Python, Rust |
| Library | TypeScript, Python, Rust |
| API | TypeScript, Python |

#### 2d: Framework (filtered by language + type)

| Project Type | Language | Frameworks |
|--------------|----------|------------|
| Web | TypeScript | Next.js, TanStack Start, Astro |
| Desktop | TypeScript | Tauri, Electron |
| Desktop | Rust | Tauri |
| Mobile | TypeScript | React Native, Expo |
| Extension | TypeScript | Chrome Extension, VS Code Extension |
| Roblox | Luau | Rojo |
| CLI | TypeScript | Node (Commander/yargs) |
| CLI | Python | uv (Click/Typer) |
| CLI | Rust | cargo (clap) |
| Library | TypeScript | npm package |
| Library | Python | PyPI package |
| Library | Rust | crates.io |
| API | TypeScript | Hono |
| API | Python | FastAPI |

#### 2e: Stack Additions (filtered by project type)

Present relevant options based on project type:

**For Web/Desktop/Mobile:**
- Styling: Tailwind CSS, shadcn/ui
- State: Zustand, Jotai
- Animation: Framer Motion, GSAP

**For Web/API/Desktop:**
- Database: Drizzle + Postgres, Convex, ClickHouse, Upstash Redis, SQLite
- Auth: Better Auth, WorkOS

**For TypeScript projects:**
- Libraries: Effect, Zod, TanStack Query
- Testing: Vitest, Playwright
- Tooling: Biome, Husky

**For Python projects:**
- Testing: pytest
- Tooling: Ruff, uv, ty, pre-commit

**For Rust projects:**
- Testing: cargo test
- Tooling: Clippy, rustfmt, cargo-watch

**For Luau (Roblox):**
- Tooling: Selene, StyLua, Rojo

**For AI/ML projects:**
- AI: Vercel AI SDK (TS), LangChain (TS/Python)
- LLM Observability: Langfuse, Braintrust
- GPU: Modal (Python)

**For Web/API:**
- Workers: Inngest
- Payments: Stripe, Polar
- Email: Resend
- Infra: Vercel, Railway, Docker

**For All:**
- Observability: Axiom, Vanta
- CI/CD: GitHub Actions + Blacksmith

### Step 3: Check Linear MCP

```javascript
// Attempt to use Linear MCP
try {
  mcp__linear__list_teams()
} catch {
  console.log("Linear MCP not configured. Run `claude mcp add linear` to enable ticket management.")
  // Offer to continue without Linear
}
```

### Step 4: Create Linear Project (if new repo and Linear available)

Use Linear MCP to create project:
- Project name: `<project-name>`
- Team: From user selection or config

### Step 5: Create Initial Linear Tickets

Create foundational tickets:
1. "Initial project setup" - Already done by spawn
2. "Configure CI/CD" - GitHub Actions setup
3. "Add core dependencies" - Based on stack selections

### Step 6: Scaffold Using CLIs

**IMPORTANT: Always use pnpm for TypeScript projects.**

| Framework | CLI Command |
|-----------|-------------|
| Turborepo | `pnpm create turbo@latest <name>` |
| Next.js | `pnpm create next-app@latest <name>` |
| TanStack Start | `pnpm create @tanstack/router@latest <name>` |
| Astro | `pnpm create astro@latest <name>` |
| Tauri | `pnpm create tauri-app@latest <name>` |
| Electron | `pnpm create electron-app@latest <name>` |
| Expo | `pnpm create expo-app@latest <name>` |
| Hono | `pnpm create hono@latest <name>` |
| FastAPI | `uv init <name> && cd <name> && uv add fastapi` |
| Rojo | `rojo init <name>` |
| cargo | `cargo new <name>` |
| uv | `uv init <name>` |

For monorepo additions:
- Apps go in `apps/<name>`
- Packages go in `packages/<name>`
- Update `turbo.json` pipeline if needed

### Step 7: Create/Update bruhs.json

Create `.claude/bruhs.json` with selected configuration:

```json
{
  "project": {
    "name": "<project-name>",
    "team": "<team-name>"
  },
  "integrations": {
    "linear": {
      "project": "<project-name>",
      "labelMapping": {
        "feat": "Feature",
        "fix": "Bug",
        "chore": "Chore",
        "refactor": "Improvement"
      }
    }
  },
  "tooling": {
    "mcps": ["linear", "notion", "context7"],
    "plugins": ["superpowers", "commit-commands", "feature-dev"]
  },
  "stack": {
    "structure": "<monorepo|single>",
    "framework": "<framework>",
    "styling": ["<selected-styling>"],
    "database": ["<selected-db>"],
    "auth": "<selected-auth>",
    "libraries": ["<selected-libs>"],
    "state": "<selected-state>",
    "testing": ["<selected-testing>"],
    "tooling": ["<selected-tooling>"],
    "infra": ["<selected-infra>"]
  }
}
```

**Tooling is auto-detected at generation time:**

```bash
# Read user's current setup
cat ~/.claude/settings.json | jq '.mcpServers | keys'      # Installed MCPs
cat ~/.claude/settings.json | jq '.enabledPlugins | keys'  # Enabled plugins
```

The `tooling` section stores what's recommended for this project. New devs can compare against their setup and install missing ones.

### Step 8: Setup GitHub Actions

Create `.github/workflows/ci.yml` with Blacksmith runner:

```yaml
name: CI

on:
  push:
    branches: [main]
  pull_request:
    branches: [main]

jobs:
  ci:
    runs-on: blacksmith-2vcpu-ubuntu-2204

    steps:
      - uses: actions/checkout@v4

      # For TypeScript/pnpm
      - uses: pnpm/action-setup@v4
      - uses: actions/setup-node@v4
        with:
          node-version: 22
          cache: 'pnpm'

      - run: pnpm install
      - run: pnpm lint
      - run: pnpm typecheck
      - run: pnpm test
      - run: pnpm build
```

Adjust based on language:
- Python: Use `uv` and `pytest`
- Rust: Use `cargo` commands
- Luau: Use `selene` and `stylua`

### Step 9: Initial Commit

```bash
git init  # if new project
git add -A
git commit -m "chore: initial project setup with <framework>"
```

## Example: New Project

```
> /bruhs:spawn gambit-v2

Project structure:
○ Monorepo (Turborepo) ← selected

What are you building?
○ Web ← selected

Language: TypeScript (default for Web)

Framework:
○ Next.js ← selected

Stack additions:
☑ Tailwind CSS
☑ shadcn/ui
☑ Drizzle + Postgres
☑ Better Auth
☑ Zustand
☑ Vitest + Playwright
☑ Biome + Husky

Creating Linear project...
✓ Created project: gambit-v2

Creating tickets...
✓ TEAM-100: Initial project setup
✓ TEAM-101: Configure CI/CD
✓ TEAM-102: Add core dependencies

Scaffolding...
$ pnpm create turbo@latest gambit-v2
$ cd gambit-v2 && pnpm create next-app@latest apps/web

Setting up GitHub Actions...
✓ Created .github/workflows/ci.yml

Creating config...
✓ Created .claude/bruhs.json

Initial commit...
✓ chore: initial project setup with Next.js

Done! 🚀
```

## Example: Add to Monorepo

```
> /bruhs:spawn

Detected: Turborepo monorepo (gambit)

What do you want to add?
○ New app ← selected

What are you building?
○ API ← selected

Language: TypeScript (default)

Framework:
○ Hono ← selected

Name: api

Creating Linear ticket...
✓ PERDIX-160: Set up api app (Hono)

Scaffolding...
$ pnpm create hono@latest apps/api

Updating turbo.json...
✓ Added api to pipeline

Done! 🚀
```

## Stack Reference

### Project Type → Language → Framework Matrix

| Project Type | Languages | Frameworks |
|--------------|-----------|------------|
| **Web** | TypeScript | Next.js, TanStack Start, Astro |
| **Desktop** | TypeScript, Rust | Tauri (Rust+TS), Electron (TS) |
| **Mobile** | TypeScript | React Native, Expo |
| **Extension** | TypeScript | Chrome, VS Code |
| **Roblox** | Luau | Rojo |
| **CLI** | TypeScript, Python, Rust | Node, uv, cargo |
| **Library** | TypeScript, Python, Rust | npm, PyPI, crates |
| **API** | TypeScript, Python | Hono, FastAPI |

### Full Stack Options

| Category | Options | Shows For |
|----------|---------|-----------|
| **Styling** | Tailwind CSS, shadcn/ui | Web, Desktop, Mobile |
| **Database** | Drizzle + Postgres, Convex, ClickHouse, Upstash Redis, SQLite, PlanetScale | Web, API, Desktop |
| **Auth** | Better Auth, WorkOS | Web, API, Mobile |
| **Libraries** | Effect, Zod, TanStack Query | TypeScript projects |
| **State** | Zustand, Jotai | Web, Desktop, Mobile |
| **Animation** | Framer Motion, GSAP | Web, Desktop, Mobile |
| **AI/ML** | Vercel AI SDK, LangChain | TypeScript, Python |
| **GPU** | Modal | Python, API |
| **Workers** | Inngest | Web, API |
| **Payments** | Stripe, Polar | Web, API |
| **Email** | Resend | Web, API |
| **Infra** | Vercel, Railway, Docker | Web, API |
| **Observability** | Axiom, Vanta | All |
| **LLM Observability** | Langfuse, Braintrust | AI/ML projects |
| **Testing** | Vitest, Playwright | TypeScript |
| **Testing** | pytest | Python |
| **Testing** | cargo test | Rust |
| **Tooling** | Biome, Husky | TypeScript |
| **Tooling** | Ruff, uv, ty, pre-commit | Python |
| **Tooling** | Clippy, rustfmt, cargo-watch | Rust |
| **Tooling** | Selene, StyLua, Rojo | Luau (Roblox) |
| **CI/CD** | GitHub Actions + Blacksmith | All |
