---
description: Initialize bruhs config for an existing project — auto-detect stack, wire up Linear, detect installed MCPs, write marker-bounded state and rules blocks into CLAUDE.md and AGENTS.md. Use when adopting bruhs on a repo that wasn't created via /bruhs:spawn.
---

# claim - Claim Existing Project

Set up bruhs for an existing project by writing the `bruhs:state` and `bruhs:rules` marker blocks into `CLAUDE.md` and `AGENTS.md` (mirrored). Use this when you have a project that wasn't created with `/bruhs:spawn`.

If a legacy `.claude/bruhs.json` is present, this command migrates it into the marker blocks and prompts before deleting the old file.

## Contents

- [Invocation](#invocation)
- [Prerequisites](#prerequisites)
- [Workflow](#workflow)
- [Stack Detection Reference](#stack-detection-reference)
- [Examples](#examples)

---

## Invocation

- `/bruhs:claim` - Claim current project for bruhs

## Prerequisites

- Existing project with git initialized
- In project root directory

## Workflow

### Step 1: Detect Existing Config

Check for both the new marker-block format and the legacy JSON file:

```bash
# Try the marker block first (new format)
python3 <PLUGIN_DIR>/scripts/read_bruhs_block.py --kind state --root . 2>/dev/null

# Then check for legacy file
ls .claude/bruhs.json 2>/dev/null
```

**Case A — `bruhs:state` block found in CLAUDE.md / AGENTS.md:**

The marker block always wins. If a legacy `.claude/bruhs.json` is *also* present, surface that to the user as a one-line note before the prompt — it's dormant (ignored by `read_bruhs_block.py`) but should be cleaned up at some point.

```javascript
// Optional one-line note when both are present:
// "Note: a legacy .claude/bruhs.json is also on disk. It's dormant — read_bruhs_block.py reads the marker block."

AskUserQuestion({
  questions: [{
    question: "Config already exists in CLAUDE.md (bruhs:state block). Would you like to reconfigure?",
    header: "Reconfigure",
    multiSelect: false,
    options: [
      { label: "Yes", description: "Re-detect and overwrite the block" },
      { label: "No", description: "Keep existing configuration and exit" },
    ]
  }]
})
```
- If **Yes**: proceed into Step 2 and re-run the full detection + prompt flow. If a legacy `.claude/bruhs.json` was also present, fire the delete-prompt AskUserQuestion after Step 7 (same prompt as the Migrate / Re-detect paths).
- If **No**: exit with `Kept existing bruhs:state block.` Any dormant legacy file stays in place.

**Case B — Legacy `.claude/bruhs.json` found, no marker block yet (MIGRATION PATH):**

```javascript
AskUserQuestion({
  questions: [{
    question: "Legacy .claude/bruhs.json found. Migrate it into CLAUDE.md + AGENTS.md marker blocks?",
    header: "Migrate legacy config",
    multiSelect: false,
    options: [
      { label: "Migrate (recommended)", description: "Port .claude/bruhs.json into the new blocks, then ask before deleting" },
      { label: "Re-detect from scratch", description: "Ignore the legacy file and run full detection (Steps 2–7)" },
      { label: "Cancel", description: "Do nothing" },
    ]
  }]
})
```

- If **Migrate**:
  1. Read the legacy JSON: `LEGACY=$(cat .claude/bruhs.json)`.
  2. Write the state block: `echo "$LEGACY" | python3 <PLUGIN_DIR>/scripts/sync_bruhs_block.py --kind state --root .`
  3. Derive and write the rules block: `echo "$LEGACY" | python3 <PLUGIN_DIR>/scripts/derive_stack_rules.py | python3 <PLUGIN_DIR>/scripts/sync_bruhs_block.py --kind rules --root .`
  4. Prompt before deleting:
     ```javascript
     AskUserQuestion({
       questions: [{
         question: "Migration complete. Delete the legacy .claude/bruhs.json?",
         header: "Delete legacy",
         multiSelect: false,
         options: [
           { label: "Yes, delete", description: "Remove .claude/bruhs.json — read_bruhs_block.py reads from CLAUDE.md now" },
           { label: "No, keep both", description: "Leave the legacy file in place (it will be ignored)" },
         ]
       }]
     })
     ```
     If **Yes**: `rm .claude/bruhs.json` (and `rmdir .claude 2>/dev/null` only if empty).
  5. Exit with summary.
- If **Re-detect**: proceed to Step 2 with the legacy file ignored. After Step 7 writes the freshly-detected blocks, fire the same delete prompt as the Migrate path (the legacy file is still on disk but will be ignored by `read_bruhs_block.py` going forward; ask the user before removing it).
- If **Cancel**: exit, no changes (no marker blocks written, legacy file untouched).

**Case C — Neither block nor legacy file present:** proceed to Step 2 (fresh setup).

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
// Config is in ~/.claude.json (the MCP config file)
const mcpConfig = JSON.parse(Bash("cat ~/.claude.json")).mcpServers
const linearServers = Object.keys(mcpConfig).filter(name => name.startsWith('linear'))

if (linearServers.length === 0) {
  console.log("No Linear MCP configured (optional).")
  console.log("To add: edit ~/.claude.json mcpServers with mcp-server-linear")
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
    label: server,
    description: `Use ${server} MCP server`
  }))

  AskUserQuestion({
    questions: [{
      question: "Which Linear workspace?",
      header: "Workspace",
      multiSelect: false,
      options: workspaceOptions
    }]
  })

  selectedServer = userSelection
}

const mcpName = selectedServer    // e.g., "linear-sonner"

// Load tools for selected workspace
// Tool format: mcp__<server-name>__linear_<method>
ToolSearch(`select:mcp__${mcpName}__linear_get_teams`)
ToolSearch(`select:mcp__${mcpName}__linear_list_projects`)

// Fetch teams
teams = call(`mcp__${mcpName}__linear_get_teams`)

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
projects = call(`mcp__${mcpName}__linear_list_projects`, { teamId: selectedTeam.id })

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
# Check the agent's MCP config for installed MCPs (Claude Code: ~/.claude.json)
cat ~/.claude.json 2>/dev/null
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

### Step 7: Write State + Rules Blocks

Build the state JSON in memory, then pipe it through the two helper scripts to write **both** the `bruhs:state` and `bruhs:rules` blocks into `CLAUDE.md` **and** `AGENTS.md` (mirrored, atomic).

**State shape — single project:**
```json
{
  "integrations": {
    "linear": {
      "mcpServer": "<selected-mcp-server>",
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
    "networking": [],
    "agentAccess": [],
    "sandboxing": [],
    "gpu": ["<detected>"],
    "observability": [],
    "llmObservability": null
  }
}
```

**Monorepos:** Use `frameworks` (array) instead of `framework` (string), set `structure: "monorepo"`, and include `"Turborepo"` or `"Nx"` in `tooling` if detected.

**If Linear not configured:** omit the `linear` section from `integrations`.

**Write to disk:**

```bash
STATE_JSON='<the JSON object above>'

# 1. State block (validated, atomic, mirrored to CLAUDE.md + AGENTS.md)
echo "$STATE_JSON" | python3 <PLUGIN_DIR>/scripts/sync_bruhs_block.py --kind state --root .

# 2. Rules block (derived from state, mirrored to both files)
echo "$STATE_JSON" \
  | python3 <PLUGIN_DIR>/scripts/derive_stack_rules.py \
  | python3 <PLUGIN_DIR>/scripts/sync_bruhs_block.py --kind rules --root .
```

If `CLAUDE.md` or `AGENTS.md` does not exist, the sync script creates it with a minimal header. Hand-written content outside the markers is **never** touched.

### Step 8: Output Summary

```
Initialized bruhs in CLAUDE.md + AGENTS.md

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

Ready! You can now use /bruhs:cook and /bruhs:yeet.
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
| `modal` in deps / `modal.toml` | gpu: modal |
| `runpod` in deps / `runpod.toml` | gpu: runpod |
| `lambdalabs` in deps | gpu: lambda |
| `framer-motion`, `motion`, `@motionone/react`, `@react-spring/web` in deps | animation: framer-motion / motion / motion-one / react-spring |
| `zod` in deps | libraries: zod |
| `@tanstack/react-query` in deps | libraries: tanstack-query |
| `effect` in deps | libraries: effect |
| `better-auth` in deps | auth: better-auth |
| `auth.md` / `.well-known/auth.md` / `public/auth.md` | agentAccess: auth.md |
| `vercel.json` | infra: vercel |
| `Dockerfile` | infra: docker |
| `railway.json` | infra: railway |

## Examples

### Single Project

```
> /bruhs:claim

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

Writing state + rules blocks...
✓ Wrote bruhs:state to CLAUDE.md + AGENTS.md
✓ Wrote bruhs:rules to CLAUDE.md + AGENTS.md

Ready! You can now use /bruhs:cook and /bruhs:yeet.
```

### Monorepo

```
> /bruhs:claim

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

Writing state + rules blocks...
✓ Wrote bruhs:state to CLAUDE.md + AGENTS.md
✓ Wrote bruhs:rules to CLAUDE.md + AGENTS.md

Ready! You can now use /bruhs:cook and /bruhs:yeet.
```
