# bruhs

Opinionated development lifecycle for Claude Code - spawn projects, cook features, yeet to ship.

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
/bruhs:slop         # Clean up AI slop (senior engineer review)
```

## Commands

### `/bruhs:claim`

Claim an existing project for bruhs.

**Features:**
- Auto-detects stack from project files (framework, styling, database, etc.)
- Configures Linear integration (team, project, labels)
- Detects installed MCPs and plugins from Claude settings
- Creates `.claude/bruhs.json`

Use this when you have a project that wasn't created with `/bruhs:spawn`.

### `/bruhs:spawn`

Create a new project from scratch or add an app/package to an existing monorepo.

**Features:**
- Detects monorepo context automatically
- Selection flow: Structure → Project Type → Language → Framework → Stack
- Scaffolds using official CLIs (pnpm for TypeScript)
- Creates Linear project + initial tickets
- Sets up GitHub Actions with Blacksmith runner
- Creates `.claude/bruhs.json` config
- Recommends relevant skills via `find-skills`

**Supported stacks:**
- **Web:** Next.js, TanStack Start, Astro
- **Desktop:** Tauri, Electron
- **Mobile:** React Native, Expo
- **API:** Hono, FastAPI
- **CLI:** Node, uv, cargo
- **Roblox:** Rojo

### `/bruhs:cook`

Plan and build a feature end-to-end.

**Workflow:**
1. **Understand** - Clarify requirements
2. **Explore** - Use code-explorer agents to understand codebase
3. **Plan** - Design 2-3 approaches, get user approval
4. **Setup** - Stash unrelated changes if needed
5. **Build** - Implement with TDD where applicable
6. **Review** - Use code-reviewer agents
7. **Ready** - Prompt user to `/bruhs:yeet`

**Full lifecycle:** cook → yeet → peep → dip

### `/bruhs:yeet`

Ship code with Linear integration.

**Workflow:**
1. Analyze changes and categorize (feat/fix/chore/refactor)
2. Create Linear ticket with proper labels
3. Checkout branch (using Linear's generated branch name)
4. Stage and commit with ticket reference
5. Push and create PR via `gh`
6. Update Linear status to "In Review"

**Git-only mode:** Works without Linear - just skips ticket management.

### `/bruhs:peep`

Address PR review comments and optionally merge.

**Workflow:**
1. Detect PR from current branch (or specify PR# / ticket ID)
2. Fetch all review comments and categorize (must-fix, suggestion, question)
3. Address each comment interactively (apply fix, respond, skip)
4. Commit and push fixes
5. Request re-review if needed
6. Merge when approved (squash/merge/rebase)
7. Auto-transition to dip workflow after merge

**Invocation:**
- `/bruhs:peep` - Current branch's PR
- `/bruhs:peep 42` - Specific PR number
- `/bruhs:peep PERDIX-145` - Find PR by Linear ticket

### `/bruhs:dip`

Clean up after merging and switch to base branch.

**Workflow:**
1. Switch to configured base branch (main/dev)
2. Pull latest changes
3. Delete merged feature branch (local + remote)
4. Restore stashed changes from cook (if any)

Use this after your PR is merged to start fresh for the next feature.

### `/bruhs:slop`

Deep codebase analysis and AI slop cleanup. Acts as a nitpicky senior engineer.

**Priority hierarchy (type signatures first):**

| Priority | Category |
|----------|----------|
| **1** | Type Signatures - missing return types, hidden errors, wide types |
| **2** | Error Handling - errors not in types, swallowed errors |
| **3** | Immutability - parameter mutation, hidden state changes |
| **4** | Security - hardcoded secrets, injection vulnerabilities |
| **5** | Architecture - circular deps, mixed abstraction levels |
| **6** | Performance - N+1 queries, unnecessary re-renders |
| **7** | Code Style - over-commenting, verbose names, dead code |

**What it detects:**
- **Type signature violations**: Missing return types, errors hidden from types, overly wide types, mutable parameters
- **Over-engineering**: Unnecessary abstractions, premature generalization, factory abuse
- **TypeScript anti-patterns**: `any` types, non-null assertions, type assertion abuse
- **React anti-patterns**: Derived state bugs, multiple boolean state, unnecessary effects
- **Code noise**: Over-commenting, verbose names, dead code, TODO graveyards
- **Duplication**: Copy-paste code, inconsistent patterns
- **Security smells**: Hardcoded secrets, injection vulnerabilities
- **Performance issues**: N+1 queries, unnecessary re-renders
- **Architecture violations**: Circular deps, mixed abstraction levels

**Workflow:**
1. Load stack context from bruhs.json
2. Run static analysis (TypeScript, security, dead code)
3. Deep analysis of each file for slop patterns
4. Generate severity-ranked report
5. Interactive fixing (or auto-fix safe issues)
6. Verify with tsc, lint, tests

**Invocation:**
- `/bruhs:slop` - Full codebase scan
- `/bruhs:slop src/components` - Target specific directory
- `/bruhs:slop --fix` - Auto-fix safe issues, prompt for others
- `/bruhs:slop --report` - Report only, no fixes

**Severity levels** (configurable in bruhs.json):
- `relaxed` - Critical only
- `balanced` - Critical + high
- `nitpicky` - Critical + high + medium (default)
- `brutal` - Everything, no mercy

## Best Practices

Shared practices used by both `cook` (building) and `slop` (cleanup):

```
practices/
  type-driven-design.md  # PRIMARY: Type signatures, errors, immutability
  _common.md             # Universal: naming, git, errors, testing
  typescript-react.md    # TypeScript + React patterns
  python-fastapi.md      # (planned) Python + FastAPI patterns
  typescript-hono.md     # (planned) TypeScript + Hono patterns
  rust.md                # (planned) Rust patterns
  luau-roblox.md         # (planned) Luau/Roblox patterns
```

**Type-Driven Design** is the primary lens for all code analysis. Derived from:
- **Scala FP** - Type signatures as documentation, pure functions
- **Go** - Explicit error handling, errors as values
- **Rust** - Immutability by default, ownership patterns

The practices define:
- **DO** patterns to follow
- **DON'T** anti-patterns to avoid
- Quick reference checklists

Currently implemented: TypeScript + React (covers Next.js, React Native, Tauri, Electron).

## Configuration

Create `.claude/bruhs.json` in your project:

```json
{
  "integrations": {
    "linear": {
      "team": "Your Team",
      "project": "Your Project",
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
    "structure": "turborepo",
    "framework": "nextjs",
    "styling": ["tailwind", "shadcn"],
    "database": ["drizzle-postgres"],
    "auth": "better-auth"
  }
}
```

- **integrations** - Config for external services (Linear, GitHub, etc.)
- **tooling** - MCPs and skills (auto-detected at setup, grows as you build)
- **stack** - Tech stack choices

## Interactive Selection

All commands use Claude Code's `AskUserQuestion` tool for interactive selection prompts. This provides a proper UI with clickable options instead of text-based checkboxes that require typing.

Example:
```javascript
AskUserQuestion({
  questions: [{
    question: "Which approach do you want?",
    header: "Approach",
    multiSelect: false,
    options: [
      { label: "Option A", description: "Description of option A" },
      { label: "Option B", description: "Description of option B" },
    ]
  }]
})
```

For multi-select prompts (like stack additions), `multiSelect: true` allows selecting multiple options.

## Linear MCP Setup

Linear integration is optional but enables full ticket management. Uses `mcp-server-linear` for multi-workspace support.

### Quick Setup (Single Workspace)

1. **Get your Linear API key:**
   - Go to Linear → Settings → API → Personal API Keys
   - Click "Create key", give it a label (e.g., "Claude MCP")
   - Copy the key (starts with `lin_api_`)

2. **Add to `~/.claude.json`:**
   ```json
   {
     "mcpServers": {
       "linear-myworkspace": {
         "type": "stdio",
         "command": "npx",
         "args": ["-y", "mcp-server-linear"],
         "env": {
           "LINEAR_ACCESS_TOKEN": "lin_api_xxx"
         }
       }
     }
   }
   ```

3. **Restart Claude Code** to load the MCP server.

### Multi-Workspace Setup

For multiple Linear workspaces (e.g., different companies or projects), add each as a separate MCP server:

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
```

**Tool naming:** Tools are always `mcp__<server-name>__linear_<method>`:
- `mcp__linear-sonner__linear_get_teams`
- `mcp__linear-perdix__linear_create_issue`

Each project's `.claude/bruhs.json` stores which workspace to use:
```json
{
  "integrations": {
    "linear": {
      "mcpServer": "linear-sonner"
    }
  }
}
```

### Verify Setup

Run `/mcp` in Claude Code to see connected servers. You should see your Linear servers listed.

## Other Dependencies

- **GitHub CLI** - For PR creation. Authenticate with `gh auth login`.

## License

MIT
