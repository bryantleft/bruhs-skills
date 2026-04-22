---
description: Create a new project or add an app/package to a monorepo — select stack, scaffold via official CLIs, create Linear project, wire up GitHub Actions, write .claude/bruhs.json. Use when starting a greenfield project or adding to a pnpm/turbo monorepo.
---

# spawn - Project Scaffolding

Create a new project from scratch or add an app/package to an existing monorepo.

## Contents

- [Invocation](#invocation)
- [Workflow](#workflow)
- [Example: New Project](#example-new-project)
- [Example: Add to Monorepo](#example-add-to-monorepo)
- [Stack Reference](#stack-reference)

---

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

If monorepo detected, use `AskUserQuestion`:

```javascript
AskUserQuestion({
  questions: [{
    question: "What would you like to add to this monorepo?",
    header: "Add to repo",
    multiSelect: false,
    options: [
      { label: "New app", description: "Add a new application to apps/" },
      { label: "New package", description: "Add a shared package to packages/" },
      { label: "New project (outside)", description: "Create entirely new project outside this monorepo" },
    ]
  }]
})

### Step 2: Selection Flow

Guide user through selections top-down. Each choice filters subsequent options.

```
Structure → Project Type → Language → Framework → Stack Additions
```

#### 2a: Structure (if new project)

Use `AskUserQuestion`:

```javascript
AskUserQuestion({
  questions: [{
    question: "What project structure do you want?",
    header: "Structure",
    multiSelect: false,
    options: [
      { label: "Monorepo (Turborepo)", description: "Multiple apps/packages in one repository" },
      { label: "Single package", description: "Standalone project with one package" },
    ]
  }]
})

#### 2b: Project Type

Use `AskUserQuestion` (split into two questions due to 4-option limit):

```javascript
AskUserQuestion({
  questions: [
    {
      question: "What are you building?",
      header: "Type",
      multiSelect: false,
      options: [
        { label: "Web", description: "Website or web application" },
        { label: "API", description: "Backend service" },
        { label: "Mobile", description: "Mobile application" },
        { label: "Desktop", description: "Desktop application" },
      ]
    }
  ]
})

// If user selects "Other", show secondary options:
AskUserQuestion({
  questions: [{
    question: "What type of project?",
    header: "Type",
    multiSelect: false,
    options: [
      { label: "Extension", description: "Browser or VS Code extension" },
      { label: "CLI", description: "Command-line tool" },
      { label: "Library", description: "Reusable package" },
      { label: "Roblox", description: "Roblox game" },
    ]
  }]
})

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

Use `AskUserQuestion` with `multiSelect: true` for each category. Present only relevant categories based on project type.

**For Web/Desktop/Mobile - Styling & State:**

```javascript
AskUserQuestion({
  questions: [
    {
      question: "Which styling options do you want?",
      header: "Styling",
      multiSelect: true,
      options: [
        { label: "Tailwind CSS", description: "Utility-first CSS framework" },
        { label: "shadcn/ui", description: "Re-usable components (base-mira style by default)" },
      ]
    },
    {
      question: "Which state management do you want?",
      header: "State",
      multiSelect: false,
      options: [
        { label: "Zustand", description: "Simple, fast state management" },
        { label: "Jotai", description: "Primitive and flexible atomic state" },
      ]
    }
  ]
})
```

**For Web/API/Desktop - Database & Auth:**

```javascript
AskUserQuestion({
  questions: [
    {
      question: "Which database do you want?",
      header: "Database",
      multiSelect: false,
      options: [
        { label: "Drizzle + Postgres", description: "TypeScript ORM with PostgreSQL" },
        { label: "Convex", description: "Real-time backend with built-in DB" },
        { label: "Upstash Redis", description: "Serverless Redis for caching/queues" },
        { label: "SQLite", description: "Embedded file-based database" },
      ]
    },
    {
      question: "Which auth provider do you want?",
      header: "Auth",
      multiSelect: false,
      options: [
        { label: "Better Auth", description: "TypeScript-first auth framework" },
        { label: "WorkOS", description: "Enterprise SSO and directory sync" },
      ]
    }
  ]
})
```

**For TypeScript projects - Libraries & Testing:**

```javascript
AskUserQuestion({
  questions: [
    {
      question: "Which libraries do you want?",
      header: "Libraries",
      multiSelect: true,
      options: [
        { label: "Zod", description: "TypeScript-first schema validation" },
        { label: "TanStack Query", description: "Async state management" },
        { label: "Effect", description: "Structured concurrency and typed errors" },
      ]
    },
    {
      question: "Which testing tools do you want?",
      header: "Testing",
      multiSelect: true,
      options: [
        { label: "Vitest", description: "Fast unit testing" },
        { label: "Playwright", description: "End-to-end browser testing" },
      ]
    }
  ]
})
```

**For TypeScript projects - Tooling:**

```javascript
AskUserQuestion({
  questions: [{
    question: "Which tooling do you want?",
    header: "Tooling",
    multiSelect: true,
    options: [
      { label: "Biome", description: "Fast linter and formatter" },
      { label: "Husky", description: "Git hooks for pre-commit checks" },
    ]
  }]
})
```

**For Python projects:**

```javascript
AskUserQuestion({
  questions: [{
    question: "Which Python tooling do you want?",
    header: "Tooling",
    multiSelect: true,
    options: [
      { label: "pytest", description: "Python testing framework" },
      { label: "Ruff", description: "Fast Python linter" },
      { label: "uv", description: "Fast Python package manager" },
      { label: "pre-commit", description: "Git hooks for Python" },
    ]
  }]
})
```

**For Rust projects:**

```javascript
AskUserQuestion({
  questions: [{
    question: "Which Rust tooling do you want?",
    header: "Tooling",
    multiSelect: true,
    options: [
      { label: "Clippy", description: "Rust linter" },
      { label: "rustfmt", description: "Rust formatter" },
      { label: "cargo-watch", description: "Auto-rebuild on changes" },
    ]
  }]
})
```

**For Luau (Roblox):**

```javascript
AskUserQuestion({
  questions: [{
    question: "Which Roblox tooling do you want?",
    header: "Tooling",
    multiSelect: true,
    options: [
      { label: "Selene", description: "Luau linter" },
      { label: "StyLua", description: "Luau formatter" },
      { label: "Rojo", description: "Sync to Roblox Studio" },
    ]
  }]
})
```

**For AI/ML projects:**

```javascript
AskUserQuestion({
  questions: [
    {
      question: "Which AI framework do you want?",
      header: "AI",
      multiSelect: false,
      options: [
        { label: "Vercel AI SDK", description: "Streaming AI responses (TypeScript)" },
        { label: "LangChain", description: "LLM application framework" },
      ]
    },
    {
      question: "Which LLM observability do you want?",
      header: "Observability",
      multiSelect: false,
      options: [
        { label: "Langfuse", description: "Open-source LLM tracing" },
        { label: "Braintrust", description: "LLM evaluation platform" },
      ]
    }
  ]
})
```

**For AI/ML projects - GPU Providers:**

```javascript
AskUserQuestion({
  questions: [{
    question: "Which GPU providers do you want?",
    header: "GPU",
    multiSelect: true,
    options: [
      { label: "Modal", description: "Serverless GPU inference" },
      { label: "RunPod", description: "Training and fine-tuning custom models" },
      { label: "Lambda", description: "Training at scale" },
    ]
  }]
})
```

**For Web/API - Infrastructure:**

```javascript
AskUserQuestion({
  questions: [
    {
      question: "Which infrastructure do you want?",
      header: "Infra",
      multiSelect: true,
      options: [
        { label: "Vercel", description: "Frontend and serverless hosting" },
        { label: "Railway", description: "Full-stack app platform" },
        { label: "Docker", description: "Container-based deployment" },
      ]
    },
    {
      question: "Which additional services do you want?",
      header: "Services",
      multiSelect: true,
      options: [
        { label: "Inngest", description: "Background jobs and workflows" },
        { label: "Stripe", description: "Payment processing" },
        { label: "Resend", description: "Transactional email" },
      ]
    }
  ]
})
```

**For All projects - Observability & CI:**

```javascript
AskUserQuestion({
  questions: [{
    question: "Which observability/CI do you want?",
    header: "DevOps",
    multiSelect: true,
    options: [
      { label: "Axiom", description: "Log aggregation and monitoring" },
      { label: "GitHub Actions + Blacksmith", description: "CI/CD with fast runners" },
    ]
  }]
})

### Step 3: Detect Linear MCP Servers

Detect all available Linear MCP servers (supports multiple workspaces via `mcp-server-linear`):

```javascript
// Read MCP server config to find all Linear instances
// Servers are named like: linear-perdix, linear-bnle, linear-sonner
// Tool names are: mcp__<server-name>__linear_<method>
const mcpConfig = JSON.parse(Bash("cat ~/.claude.json")).mcpServers
const linearServers = Object.keys(mcpConfig).filter(name => name.startsWith('linear'))

if (linearServers.length === 0) {
  console.log("No Linear MCP configured.")
  console.log("Add a workspace: edit ~/.claude.json mcpServers and add:")
  console.log(`
    "linear-myworkspace": {
      "type": "stdio",
      "command": "npx",
      "args": ["-y", "mcp-server-linear"],
      "env": {
        "LINEAR_ACCESS_TOKEN": "lin_api_xxx"
      }
    }
  `)
  // Offer to continue without Linear
  AskUserQuestion({
    questions: [{
      question: "Continue without Linear integration?",
      header: "Linear",
      multiSelect: false,
      options: [
        { label: "Yes, skip Linear", description: "Set up Linear later" },
        { label: "No, I'll configure it", description: "Exit and set up Linear first" }
      ]
    }]
  })
}
```

### Step 4: Select Linear Workspace, Team, and Project

**If multiple Linear workspaces exist, ask which one to use:**

```javascript
let selectedServer = linearServers[0]  // default to first

if (linearServers.length > 1) {
  // Multiple Linear workspaces available - ask user which one
  const workspaceOptions = linearServers.slice(0, 4).map(server => ({
    label: server.prefix,
    description: `Use ${server.name} MCP server`
  }))

  AskUserQuestion({
    questions: [{
      question: "Which Linear workspace?",
      header: "Workspace",
      multiSelect: false,
      options: workspaceOptions
    }]
  })

  selectedServer = linearServers.find(s => s.prefix === userSelection)
}

// Tool names are: mcp__<server-name>__linear_<method>
// e.g., mcp__linear-sonner__linear_get_teams
const mcpName = selectedServer  // e.g., "linear-sonner"

// Load the tools for the selected workspace
ToolSearch(`select:mcp__${mcpName}__linear_get_teams`)
ToolSearch(`select:mcp__${mcpName}__linear_list_projects`)
ToolSearch(`select:mcp__${mcpName}__linear_create_project`)

// Fetch available teams from selected workspace
teams = call(`mcp__${mcpName}__linear_get_teams`)

// Build team options dynamically
const teamOptions = teams.slice(0, 4).map(t => ({
  label: t.name,
  description: t.key || "Linear team"
}))

// ALWAYS ask user to select team - don't default to previous
AskUserQuestion({
  questions: [{
    question: "Which Linear team for this project?",
    header: "Team",
    multiSelect: false,
    options: teamOptions
  }]
})

// After team selected, ask if they want to create a new project or use existing
existingProjects = call(`mcp__${mcpName}__linear_list_projects`, { teamId: selectedTeam.id })

if (existingProjects.length > 0) {
  const projectOptions = [
    { label: "Create new project", description: `Create "${projectName}" project` },
    ...existingProjects.slice(0, 3).map(p => ({
      label: p.name,
      description: "Use existing project"
    }))
  ]

  AskUserQuestion({
    questions: [{
      question: "Which Linear project?",
      header: "Project",
      multiSelect: false,
      options: projectOptions
    }])
} else {
  // No existing projects, create new one automatically
  console.log(`Creating new Linear project: ${projectName}`)
}

// Create project if "Create new project" selected
if (createNewProject) {
  call(`mcp__${mcpName}__linear_create_project`, {
    name: projectName,
    teamIds: [selectedTeam.id]
  })
}
```

**Store selected workspace in bruhs.json:**
- `integrations.linear.mcpServer`: Which MCP server to use (e.g., `"linear-sonner"`)
- Project name: `<project-name>`
- Team: **From user selection (always ask)**

**Setting up multiple Linear workspaces:**

Uses `mcp-server-linear` npm package. Each workspace gets its own MCP server entry.
Edit `~/.claude.json` (the MCP config file):

```json
{
  "mcpServers": {
    "linear-perdix": {
      "type": "stdio",
      "command": "npx",
      "args": ["-y", "mcp-server-linear"],
      "env": {
        "LINEAR_ACCESS_TOKEN": "lin_api_xxx"
      }
    },
    "linear-sonner": {
      "type": "stdio",
      "command": "npx",
      "args": ["-y", "mcp-server-linear"],
      "env": {
        "LINEAR_ACCESS_TOKEN": "lin_api_yyy"
      }
    }
  }
}

**Tool naming:** Tools are always `mcp__<server-name>__linear_<method>`, e.g.:
- `mcp__linear-sonner__linear_get_teams`
- `mcp__linear-perdix__linear_create_issue`
```

**Get your Linear API key:**
1. Go to Linear → Settings → API → Personal API Keys
2. Click "Create key", give it a label (e.g., "Claude MCP")
3. Copy the generated key (starts with `lin_api_`)

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

**If shadcn/ui was selected, initialize with base-mira style:**

```bash
# Initialize shadcn with base-mira style (default)
pnpm dlx shadcn@latest init --style base-mira --base-color neutral --css-variables

# Or for monorepo, run from the app directory
cd apps/web && pnpm dlx shadcn@latest init --style base-mira --base-color neutral --css-variables
```

The `base-mira` style provides a clean, modern aesthetic. If user wants a different style, they can specify via "Other" in the styling selection.

### Step 7: Reconcile Tooling Conflicts

Framework scaffolders install their own default tooling. Reconcile conflicts by removing tools that were superseded by user selections.

**Tool Categories & Mutual Exclusivity:**

| Category | Tools | Notes |
|----------|-------|-------|
| **Linting (JS/TS)** | ESLint, Biome | Only one linter |
| **Formatting (JS/TS)** | Prettier, Biome, dprint | Only one formatter |
| **Linting (Python)** | Ruff, Flake8, Pylint | Only one linter |
| **Formatting (Python)** | Ruff, Black, autopep8 | Only one formatter |
| **Linting (Rust)** | Clippy | Standard, no conflicts |
| **Package Manager (JS)** | npm, yarn, pnpm, bun | Only one |
| **Testing (JS/TS)** | Vitest, Jest | Only one unit test runner |
| **Testing (E2E)** | Playwright, Cypress | Can coexist, but usually pick one |
| **Type Checking (Python)** | ty, mypy, pyright, pytype | Can coexist, but usually pick one |

**Reconciliation Logic:**

```javascript
// Define what each tool replaces
const TOOL_SUPERSEDES = {
  // JS/TS
  'biome': ['eslint', 'prettier', 'eslint-config-*', '@eslint/*', 'prettier-*'],
  'dprint': ['prettier', 'prettier-*'],
  'vitest': ['jest', '@jest/*', 'ts-jest', 'babel-jest'],
  'pnpm': ['package-lock.json', 'yarn.lock'],  // Lock files to remove
  'yarn': ['package-lock.json', 'pnpm-lock.yaml'],
  'bun': ['package-lock.json', 'pnpm-lock.yaml', 'yarn.lock'],

  // Python
  'ruff': ['flake8', 'pylint', 'black', 'autopep8', 'isort', 'pyflakes', 'pycodestyle'],
  'ty': ['mypy', 'pyright', 'pytype'],
  'uv': ['pip', 'pipenv', 'poetry'],  // uv replaces these as package manager
}

// Files to remove when tool is superseded
const TOOL_FILES = {
  'eslint': ['.eslintrc', '.eslintrc.js', '.eslintrc.cjs', '.eslintrc.json', '.eslintrc.yml', 'eslint.config.js', 'eslint.config.mjs'],
  'prettier': ['.prettierrc', '.prettierrc.js', '.prettierrc.json', '.prettierrc.yml', 'prettier.config.js', 'prettier.config.mjs'],
  'jest': ['jest.config.js', 'jest.config.ts', 'jest.config.mjs', 'jest.setup.js', 'jest.setup.ts'],
  'flake8': ['.flake8', 'setup.cfg'],  // setup.cfg may have flake8 config
  'black': ['pyproject.toml'],  // Check for [tool.black] section
  'mypy': ['mypy.ini', '.mypy.ini'],  // pyproject.toml may have [tool.mypy]
  'pylint': ['.pylintrc', 'pylintrc'],
}
```

**Execution:**

```bash
# 1. Identify what user selected
selectedTools = userSelections.tooling  # e.g., ['biome', 'vitest']

# 2. For each selected tool, find what it supersedes
for tool in selectedTools:
  superseded = TOOL_SUPERSEDES[tool] || []

  for oldTool in superseded:
    # Remove from package.json dependencies
    # Handles glob patterns like 'eslint-config-*'
    pnpm remove $(pnpm list --json | jq -r '.dependencies | keys[] | select(test("^eslint"))')

    # Remove config files
    for file in TOOL_FILES[oldTool]:
      rm -f $file

# 3. Remove superseded lock files
if selectedPackageManager == 'pnpm':
  rm -f package-lock.json yarn.lock bun.lockb

# 4. Update package.json scripts to use selected tools
# e.g., replace "lint": "eslint ." with "lint": "biome check ."
```

**Script Updates:**

| If Selected | Replace Script | With |
|-------------|---------------|------|
| Biome | `"lint": "eslint ."` | `"lint": "biome check ."` |
| Biome | `"format": "prettier --write ."` | `"format": "biome format --write ."` |
| Biome | `"lint": "next lint"` | `"lint": "biome check ."` |
| Vitest | `"test": "jest"` | `"test": "vitest"` |
| Ruff | `"lint": "flake8"` | `"lint": "ruff check ."` |
| Ruff | `"format": "black ."` | `"format": "ruff format ."` |

**Framework-Specific Handling:**

| Framework | Default Tooling | If Biome Selected |
|-----------|-----------------|-------------------|
| Next.js | eslint, eslint-config-next | Remove both, add `biome.json` with Next.js rules |
| Create React App | eslint (built-in) | Eject or use CRACO to disable |
| Vite | None by default | No conflict |
| Astro | None by default | No conflict |
| TanStack Start | None by default | No conflict |

**Biome Config for Next.js:**

When Biome replaces ESLint in a Next.js project, create `biome.json`:

```json
{
  "$schema": "https://biomejs.dev/schemas/1.9.4/schema.json",
  "organizeImports": { "enabled": true },
  "linter": {
    "enabled": true,
    "rules": {
      "recommended": true,
      "correctness": {
        "useExhaustiveDependencies": "warn",
        "useHookAtTopLevel": "error"
      },
      "a11y": {
        "recommended": true
      }
    }
  },
  "formatter": {
    "enabled": true,
    "indentStyle": "space",
    "indentWidth": 2
  },
  "javascript": {
    "formatter": {
      "quoteStyle": "single",
      "semicolons": "asNeeded"
    }
  }
}
```

This mirrors the key rules from `eslint-config-next` (React hooks, a11y).

### Step 8: Create/Update bruhs.json

**If adding to an existing monorepo:**

When a `.claude/bruhs.json` already exists (monorepo-addition case), merge the new package's config into the existing one instead of overwriting:

```javascript
const existing = JSON.parse(Bash("cat .claude/bruhs.json"));
const detected = /* config assembled from user selections for the new package */;

const merged = {
  ...existing,
  stack: {
    ...existing.stack,
    // Union arrays — don't replace
    frameworks:  [...new Set([...(existing.stack.frameworks  || []), ...(detected.stack.frameworks  || [])])],
    libraries:   [...new Set([...(existing.stack.libraries   || []), ...(detected.stack.libraries   || [])])],
    styling:     [...new Set([...(existing.stack.styling     || []), ...(detected.stack.styling     || [])])],
    testing:     [...new Set([...(existing.stack.testing     || []), ...(detected.stack.testing     || [])])],
  },
  integrations: {
    ...existing.integrations,
    // Linear workspace is already configured for the monorepo — leave untouched
    linear: existing.integrations?.linear,
  },
  tooling: {
    ...existing.tooling,
    // Union with any new skills detected for the added package
    skills: [...new Set([...(existing.tooling?.skills || []), ...(detected.tooling?.skills || [])])],
  },
};

// Write atomically through the canonical writer
Bash(`echo '${JSON.stringify(merged)}' | python3 scripts/write_bruhs_config.py`);
```

Otherwise (fresh project), create `.claude/bruhs.json` with selected configuration:

```json
{
  "integrations": {
    "linear": {
      "mcpServer": "<selected-mcp-server>", // e.g., "linear-sonner"
      "team": "<selected-team-id>",
      "teamName": "<selected-team-name>",
      "project": "<selected-project-id>",
      "projectName": "<selected-project-name>",
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
    "infra": ["<selected-infra>"],
    "gpu": ["<selected-gpu>"]
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

### Step 9: Recommend Skills (using find-skills)

Use `find-skills` to recommend relevant skills based on selected stack:

```javascript
// Search for skills matching the selected framework/stack
Skill("find-skills", `${framework} best practices`)  // e.g., "nextjs best practices"

// Also search for specific stack items
for (item of selectedStack) {
  Skill("find-skills", item)  // e.g., "drizzle", "tailwind", "zustand"
}
```

Present skill recommendations using `AskUserQuestion` with `multiSelect: true`:

```javascript
// Build options dynamically from find-skills results
const skillOptions = foundSkills.map(skill => ({
  label: skill.name,
  description: `${skill.description} (${skill.installs} installs)`
}));

// Present in batches of 4 (AskUserQuestion limit)
AskUserQuestion({
  questions: [{
    question: "Which skills do you want to install?",
    header: "Skills",
    multiSelect: true,
    options: skillOptions.slice(0, 4)  // First 4 skills
  }]
})

// If more than 4 skills, ask again for the rest
if (skillOptions.length > 4) {
  AskUserQuestion({
    questions: [{
      question: "Any additional skills?",
      header: "More skills",
      multiSelect: true,
      options: skillOptions.slice(4, 8)
    }]
  })
}
```

Install selected skills:
```bash
npx skills add <owner/repo> --skill <skill-name>
```

### Step 10: Setup GitHub Actions

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
- Luau: Use `selene` and `stylua` — see the Luau / Rojo template below

**Luau / Rojo projects:**

For Roblox projects scaffolded with Rojo, use this workflow template instead of the TypeScript one above. It uses Aftman (the Luau toolchain manager) to install `selene`, `stylua`, and `rojo` from `aftman.toml`, then runs lint + format-check + build.

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

      - uses: ok-nick/setup-aftman@v0.4.2

      - run: aftman install
      - run: selene src
      - run: stylua --check src
      - run: rojo build default.project.json -o <name>.rbxlx
```

Replace `<name>` with the project name. If the TypeScript template above uses `ubuntu-latest` instead of the Blacksmith runner, use `ubuntu-latest` here too for consistency.

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

Done! Ready to commit when you are.
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
| **GPU** | Modal (inference), RunPod (training/fine-tuning), Lambda (training at scale) | Python, API |
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
