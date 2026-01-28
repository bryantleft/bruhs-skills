# bruhs

Opinionated development lifecycle plugin for Claude Code - spawn projects, cook features, yeet to ship.

## Installation

```bash
claude plugin install bruhs
```

## Commands

| Command | Purpose |
|---------|---------|
| `/bruhs:spawn` | Create new project or add to monorepo |
| `/bruhs:cook` | Plan + Build a feature end-to-end |
| `/bruhs:yeet` | Ship: Linear ticket → Branch → Commit → PR |

## Workflow

```
/bruhs:spawn → Create project/app with full stack setup
    ↓
/bruhs:cook → Plan and build features with TDD
    ↓
/bruhs:yeet → Ship to Linear + GitHub
```

## `/bruhs:spawn`

Create a new project from scratch or add an app/package to an existing monorepo.

**Features:**
- Detects monorepo context automatically
- Selection flow: Structure → Project Type → Language → Framework → Stack
- Scaffolds using official CLIs (pnpm for TypeScript)
- Creates Linear project + initial tickets
- Sets up GitHub Actions with Blacksmith runner
- Creates `.claude/bruhs.json` config

**Supported stacks:**
- **Web:** Next.js, TanStack Start, Astro
- **Desktop:** Tauri, Electron
- **Mobile:** React Native, Expo
- **API:** Hono, FastAPI
- **CLI:** Node, uv, cargo
- **Roblox:** Rojo

## `/bruhs:cook`

Plan and build a feature end-to-end.

**Workflow:**
1. **Understand** - Clarify requirements
2. **Explore** - Use code-explorer agents to understand codebase
3. **Plan** - Design 2-3 approaches, get user approval
4. **Setup** - Stash unrelated changes if needed
5. **Build** - Implement with TDD where applicable
6. **Review** - Use code-reviewer agents
7. **Ready** - Prompt user to `/bruhs:yeet`

## `/bruhs:yeet`

Ship code with Linear integration.

**Workflow:**
1. Analyze changes and categorize (feat/fix/chore/refactor)
2. Create Linear ticket with proper labels
3. Checkout branch (using Linear's generated branch name)
4. Stage and commit with ticket reference
5. Push and create PR via `gh`
6. Update Linear status to "In Review"

**Git-only mode:** Works without Linear - just skips ticket management.

## Configuration

Create `.claude/bruhs.json` in your project:

```json
{
  "integrations": {
    "linear": {
      "team": "Your Team",
      "project": "Your Project",
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
    "structure": "turborepo",
    "framework": "nextjs",
    "styling": ["tailwind", "shadcn"],
    "database": ["drizzle-postgres"],
    "auth": "better-auth"
  }
}
```

- **integrations** - Config for external services (Linear, GitHub, etc.)
- **tooling** - Recommended MCPs and plugins (auto-detected at setup)
- **stack** - Tech stack choices

## Dependencies

- **Linear MCP** (optional) - For ticket management. Run `claude mcp add linear` to enable.
- **GitHub CLI** - For PR creation. Authenticate with `gh auth login`.

## License

MIT
