---
description: Claim an existing project for bruhs
---

# claim - Claim Existing Project

Set up `.claude/bruhs.json` for an existing project. Use this when you have a project that wasn't created with `/bruhs spawn`.

## Invocation

- `/bruhs claim` - Claim current project for bruhs

## Prerequisites

- Existing project with git initialized
- In project root directory

## Workflow

### Step 1: Detect Existing Config

```bash
ls .claude/bruhs.json 2>/dev/null
```

If config exists, use `AskUserQuestion`:

```javascript
AskUserQuestion({
  questions: [{
    question: "Config already exists at .claude/bruhs.json. Would you like to reconfigure?",
    header: "Reconfigure",
    multiSelect: false,
    options: [
      { label: "Yes", description: "Overwrite existing configuration" },
      { label: "No", description: "Keep existing configuration and exit" },
    ]
  }]
})

### Step 2: Detect Project Structure

```bash
# Check for monorepo indicators
ls turbo.json pnpm-workspace.yaml nx.json lerna.json 2>/dev/null

# Check for framework indicators at root
ls next.config.* nuxt.config.* astro.config.* 2>/dev/null

# For monorepos, check all apps/* directories
ls apps/*/next.config.* apps/*/astro.config.* apps/*/nuxt.config.* 2>/dev/null

# Check package.json for clues
cat package.json | jq '.dependencies, .devDependencies'
```

Auto-detect what's possible:

**For single projects:**
- **structure**: "single"
- **framework**: next.config.* → "Next.js", astro.config.* → "Astro", etc.

**For monorepos:**
- **structure**: "monorepo" if turbo.json/pnpm-workspace.yaml/nx.json exists
- **frameworks**: Array of all frameworks found in apps/* directories
  - e.g., `["Next.js", "Astro"]` if apps/web has astro.config.* and apps/agents has next.config.*
- **tooling**: Include "Turborepo" or "Nx" based on config file

**Common detection:**
- **styling**: tailwind.config.* → Tailwind CSS, components/ui or packages/ui → shadcn/ui
- **database**: drizzle.config.* → drizzle, prisma/ → prisma
- **testing**: vitest.config.* → vitest, jest.config.* → jest
- **tooling**: biome.json → biome, .eslintrc → eslint

### Step 3: Detect Linear MCP Servers

```javascript
// Read MCP server config to find all Linear instances
// Uses mcp-server-linear with TOOL_PREFIX for multi-workspace support
const mcpConfig = JSON.parse(Bash("cat ~/.claude/settings.json")).mcpServers
const linearServers = Object.entries(mcpConfig)
  .filter(([name, config]) => name.startsWith('linear'))
  .map(([name, config]) => ({
    name,
    prefix: config.env?.TOOL_PREFIX || name.replace('linear-', '')
  }))

if (linearServers.length === 0) {
  console.log("No Linear MCP configured (optional).")
  console.log("To add: edit ~/.claude/settings.json with mcp-server-linear")
  linearAvailable = false
} else {
  linearAvailable = true
}
```

### Step 4: Gather Linear Config (if available)

If Linear is available, first select workspace (if multiple), then team and project:

```javascript
let selectedServer = linearServers[0]  // default to first

// If multiple workspaces, ask which one
if (linearServers.length > 1) {
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

const mcpName = selectedServer.name    // e.g., "linear-sonner"
const prefix = selectedServer.prefix   // e.g., "sonner"

// Load tools for selected workspace
ToolSearch(`select:mcp__${mcpName}__${prefix}_list_teams`)
ToolSearch(`select:mcp__${mcpName}__${prefix}_list_projects`)

// Fetch teams
teams = call(`mcp__${mcpName}__${prefix}_list_teams`)

// Build team options dynamically
const teamOptions = teams.slice(0, 4).map(t => ({
  label: t.name,
  description: t.key || "Linear team"
}));

AskUserQuestion({
  questions: [{
    question: "Which Linear team?",
    header: "Team",
    multiSelect: false,
    options: teamOptions
  }]
})

// After team selected, get projects and ask
projects = call(`mcp__${mcpName}__${prefix}_list_projects`, { teamId: selectedTeam.id })

const projectOptions = projects.slice(0, 4).map(p => ({
  label: p.name,
  description: p.description || "Linear project"
}));

AskUserQuestion({
  questions: [{
    question: "Which Linear project?",
    header: "Project",
    multiSelect: false,
    options: projectOptions
  }]
})

### Step 5: Confirm Stack Detection

Present detected stack and use `AskUserQuestion` for confirmation:

First, output the detected stack:
```
Detected stack:
  ✓ Framework: Next.js
  ✓ Styling: Tailwind, shadcn
  ✓ Database: Drizzle + Postgres
  ✓ Testing: Vitest
  ✓ Tooling: Biome
```

Then ask for confirmation:

```javascript
AskUserQuestion({
  questions: [{
    question: "Is the detected stack correct?",
    header: "Confirm",
    multiSelect: false,
    options: [
      { label: "Yes, looks good", description: "Confirm and continue" },
      { label: "Add missing items", description: "I need to add something not detected" },
      { label: "Correct detection", description: "Something was detected incorrectly" },
    ]
  }]
})

### Step 6: Detect Installed Tooling

```bash
# Check user's Claude settings for installed MCPs
cat ~/.claude/settings.json 2>/dev/null
```

Extract:
- Installed MCP servers

### Step 6b: Detect Relevant Skills

Based on the detected stack, find skills that should be loaded for this project:

```javascript
// Always include workflow skills
detectedSkills = [
  "superpowers",       // brainstorming, debugging, verification, etc.
  "feature-dev",       // code-explorer, code-reviewer, code-architect
  "commit-commands",   // commit, commit-push-pr
]

// Add library/tech skills based on detected stack
skillsMap = {
  "shadcn": ["shadcn"],                          // styling includes shadcn
  "vercel-ai-sdk": ["vercel-ai-sdk"],            // ai: vercel-ai-sdk
  "better-auth": ["better-auth-best-practices"], // auth: better-auth
  "nextjs": ["vercel-react-best-practices"],     // framework/frameworks includes Next.js
}

if (stack.styling?.includes("shadcn")) detectedSkills.push("shadcn")
if (stack.ai === "vercel-ai-sdk") detectedSkills.push("vercel-ai-sdk")
if (stack.auth === "better-auth") detectedSkills.push("better-auth-best-practices")

// Handle both single (framework) and monorepo (frameworks) structures
const frameworks = stack.frameworks || (stack.framework ? [stack.framework] : [])
if (frameworks.some(f => f.toLowerCase().includes("next"))) {
  detectedSkills.push("vercel-react-best-practices")
}

// Verify skills actually exist
Skill("find-skills")  // Use to validate detected skills
```

Output:
```
Detecting relevant skills...
✓ Found: shadcn (component library)
✓ Found: vercel-react-best-practices (React/Next.js patterns)
```

### Step 7: Create Config

Create `.claude/bruhs.json`:

**For single projects:**
```json
{
  "integrations": {
    "linear": {
      "mcpServer": "<selected-mcp-server>",  // e.g., "linear-sonner"
      "toolPrefix": "<tool-prefix>",          // e.g., "sonner"
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
    "mcps": ["<detected-mcps>"],
    "skills": ["<detected-skills>"]
  },
  "stack": {
    "structure": "single",
    "framework": "<detected>",
    "styling": ["<detected>"],
    "database": ["<detected>"],
    "auth": null,
    "libraries": ["<detected>"],
    "state": "<detected>",
    "animation": null,
    "ai": "<detected>",
    "workers": null,
    "payments": null,
    "email": null,
    "testing": ["<detected>"],
    "tooling": ["<detected>"],
    "infra": ["<detected>"],
    "observability": [],
    "llmObservability": null
  }
}
```

**For monorepos:** Use `frameworks` (array) instead of `framework` (string):
```json
{
  "integrations": { ... },
  "tooling": { ... },
  "stack": {
    "structure": "monorepo",
    "frameworks": ["Next.js", "Astro"],
    "styling": ["Tailwind CSS", "shadcn/ui"],
    "database": ["<detected>"],
    "auth": null,
    "libraries": ["<detected>"],
    "state": "<detected>",
    "animation": null,
    "ai": "<detected>",
    "workers": null,
    "payments": null,
    "email": null,
    "testing": ["<detected>"],
    "tooling": ["Turborepo"],
    "infra": ["<detected>"],
    "observability": [],
    "llmObservability": null
  }
}
```

**Key differences for monorepos:**
- `structure`: "monorepo" instead of "single"
- `frameworks`: Array of all frameworks used across apps (not `framework`)
- `tooling`: Include "Turborepo" or "Nx" if detected

If Linear not configured, omit the `linear` section from integrations.

### Step 8: Output Summary

```
Initialized .claude/bruhs.json

Integrations:
  ✓ Linear: Perdix Labs / Gambit

Stack detected:
  ✓ Framework: nextjs
  ✓ Styling: tailwind, shadcn
  ✓ Database: drizzle-postgres
  ✓ Testing: vitest
  ✓ Tooling: biome

Tooling:
  ✓ MCPs: linear, notion, context7
  ✓ Skills: superpowers, feature-dev, commit-commands, shadcn, vercel-react-best-practices

Ready! You can now use /bruhs cook and /bruhs yeet.
```

## Stack Detection Reference

### Structure Detection

| File/Pattern | Detected As |
|--------------|-------------|
| `turbo.json` | structure: monorepo, tooling: Turborepo |
| `pnpm-workspace.yaml` | structure: monorepo |
| `nx.json` | structure: monorepo, tooling: Nx |
| `lerna.json` | structure: monorepo |

### Framework Detection

For **single projects**, detect one framework → `framework: "nextjs"`
For **monorepos**, scan all `apps/*/` directories → `frameworks: ["Next.js", "Astro"]`

| File/Pattern | Detected As |
|--------------|-------------|
| `next.config.*` | Next.js |
| `nuxt.config.*` | Nuxt |
| `astro.config.*` | Astro |
| `remix.config.*` | Remix |
| `vite.config.*` (no framework) | Vite |

### Other Detection

| File/Pattern | Detected As |
|--------------|-------------|
| `tailwind.config.*` | styling: Tailwind CSS |
| `components/ui/` or `packages/ui/` | styling: shadcn/ui |
| `drizzle.config.*` | database: drizzle-postgres |
| `prisma/schema.prisma` | database: prisma |
| `convex/` | database: convex |
| `vitest.config.*` | testing: vitest |
| `jest.config.*` | testing: jest |
| `playwright.config.*` | testing: playwright |
| `biome.json` | tooling: biome |
| `.eslintrc*` | tooling: eslint |
| `.husky/` | tooling: husky |
| `zustand` in deps | state: zustand |
| `jotai` in deps | state: jotai |
| `@ai-sdk/*` in deps | ai: vercel-ai-sdk |
| `framer-motion` in deps | animation: framer-motion |
| `zod` in deps | libraries: zod |
| `@tanstack/react-query` in deps | libraries: tanstack-query |
| `effect` in deps | libraries: effect |
| `better-auth` in deps | auth: better-auth |
| `vercel.json` | infra: vercel |
| `Dockerfile` | infra: docker |
| `railway.json` | infra: railway |

## Examples

### Single Project

```
> /bruhs claim

Checking for existing config...
✓ No existing config found

Detecting project structure...
✓ Structure: single
✓ Framework: Next.js (next.config.ts found)
✓ Styling: Tailwind CSS, shadcn/ui
✓ Database: Drizzle + Postgres
✓ Testing: Vitest
✓ Tooling: Biome, Husky

Checking Linear MCP...
✓ Linear available

Which Linear team? [Perdix Labs]
Which Linear project? [Gambit]

Detecting relevant skills...
✓ Found: superpowers, feature-dev, commit-commands
✓ Found: shadcn, vercel-react-best-practices

Confirm detected stack? [Y/n] Y

Creating config...
✓ Created .claude/bruhs.json

Ready! You can now use /bruhs cook and /bruhs yeet.
```

### Monorepo

```
> /bruhs claim

Checking for existing config...
✓ No existing config found

Detecting project structure...
✓ Structure: monorepo (turbo.json, pnpm-workspace.yaml)
✓ Frameworks: Next.js (apps/agents), Astro (apps/web)
✓ Styling: Tailwind CSS, shadcn/ui (packages/ui)
✓ Database: none detected
✓ Testing: none detected
✓ Tooling: Turborepo

Checking Linear MCP...
✓ Linear available

Which Linear team? [leftautomated]
Which Linear project? [leftautomated]

Detecting relevant skills...
✓ Found: superpowers, feature-dev, commit-commands
✓ Found: shadcn, vercel-react-best-practices

Confirm detected stack? [Y/n] Y

Creating config...
✓ Created .claude/bruhs.json

Ready! You can now use /bruhs cook and /bruhs yeet.
```
