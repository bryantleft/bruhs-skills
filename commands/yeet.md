---
description: Ship workflow - Linear ticket → Branch → Commit → PR
---

# yeet - Ship Workflow

Ship code that's ready to go. Creates Linear ticket, commits, pushes, and opens PR.

## Invocation

- `/bruhs yeet` - Ship current changes
- `/bruhs yeet` after `/bruhs cook` - Complete the cooking workflow (uses existing ticket if cook started from one)

## Prerequisites

- Changes ready to commit (staged or unstaged)
- GitHub CLI (`gh`) authenticated
- Linear MCP configured (optional, will work without)

## Workflow

### Step 0: Check Config

```bash
ls .claude/bruhs.json 2>/dev/null
```

If config doesn't exist:
```
No bruhs.json found. Would you like to:
○ Run /bruhs claim (recommended) - Full setup with Linear integration
○ Continue in git-only mode - Commit and PR without Linear tickets
```

If user chooses git-only mode:
- Skip all Linear steps (ticket creation, status updates)
- Generate branch names from change type: `<type>/<short-description>`
- Commit without ticket reference
- Remind user at end: "Run /bruhs claim to enable Linear integration"

### Step 1: Check for Changes

```bash
git status
git diff --stat
git diff --cached --stat
```

If no changes:
```
No changes to ship. Make some changes first!
```

### Step 2: Analyze Changes

Understand what changed to generate good descriptions:

```bash
git diff
git diff --cached
```

Categorize the change type:
- `feat` - New feature
- `fix` - Bug fix
- `chore` - Maintenance/config
- `refactor` - Code improvement
- `docs` - Documentation
- `test` - Test additions/changes

Generate:
- **Title**: Short description (under 70 chars)
- **Summary**: What changed and why

### Step 3: Check Linear MCP

```javascript
// Attempt to use Linear MCP
try {
  mcp__linear__list_teams()
  linearAvailable = true
} catch {
  console.log("Linear MCP not configured.")
  // Ask user
  "Continue without Linear (git-only mode)? [Y/n]"
}
```

### Step 4: Get or Create Linear Ticket (if available)

**First, check if ticket context exists from cook:**

The ticket context lives in conversation memory - if cook ran earlier in the same session with a ticket ID, that context is available here.

```javascript
// If cook passed ticket context (started from a ticket ID), use it
if (ticketContext) {
  console.log("Using existing ticket from cook...")
  branchName = ticketContext.branchName   // "perdix-145-add-dark-mode-toggle"
  ticketId = ticketContext.identifier     // "PERDIX-145"
  issueId = ticketContext.id              // UUID for API calls

  // Skip ticket creation
  return
}

// Note: If user started a new conversation after cook, context is lost
// and we'll create a new ticket below (which is fine)
```

**If no existing ticket, create one:**

```javascript
// Load Linear tools
ToolSearch("select:mcp__linear__create_issue")
ToolSearch("select:mcp__linear__list_issue_labels")

// Fetch available labels from Linear (dynamic)
availableLabels = mcp__linear__list_issue_labels({ teamId: config.integrations.linear.team })

// Get the label name from config (e.g., "feat" -> "Feature")
labelName = config.integrations.linear.labels[changeType]

// Find matching label in available labels (case-insensitive)
labelId = availableLabels.find(l => l.name.toLowerCase() === labelName.toLowerCase())?.id

// Create issue (auto-assigns to current user)
issue = mcp__linear__create_issue({
  title: generatedTitle,
  teamId: config.integrations.linear.team,
  projectId: config.integrations.linear.project,
  labelIds: labelId ? [labelId] : [],
  assigneeId: "me"
})

// Capture the branch name Linear generates
branchName = issue.gitBranchName  // e.g., "perdix-140-improve-game-state-validation"
ticketId = issue.identifier  // e.g., "PERDIX-140"
issueId = issue.id
```

### Step 5: Create Branch

Use modern git commands for branch operations:

```bash
git switch -c <branchName>
```

Example:
```bash
git switch -c perdix-140-improve-game-state-validation
```

If Linear not available, generate branch name:
```bash
# Format: <type>/<short-description>
git switch -c feat/add-leaderboard
```

### Step 6: Stage and Commit

Stage changes:
```bash
# Stage specific files (preferred)
git add <file1> <file2> ...

# Or stage all if appropriate
git add -A
```

Commit with ticket reference:
```bash
git commit -m "$(cat <<'EOF'
<type>: <description>

Fixes <TICKET-ID>
EOF
)"
```

Example:
```bash
git commit -m "$(cat <<'EOF'
feat: add leaderboard to game page

Fixes PERDIX-140
EOF
)"
```

Without Linear:
```bash
git commit -m "$(cat <<'EOF'
feat: add leaderboard to game page
EOF
)"
```

### Step 7: Push

```bash
git push -u origin <branchName>
```

### Step 8: Create PR

```bash
gh pr create --title "<title>" --body "$(cat <<'EOF'
## Summary
<bullet points of changes>

## Linear
<TICKET-ID>

## Test plan
- [ ] <verification step 1>
- [ ] <verification step 2>
EOF
)"
```

Example:
```bash
gh pr create --title "feat: add leaderboard to game page" --body "$(cat <<'EOF'
## Summary
- Added LeaderboardCard component showing top agents by win rate
- Integrated leaderboard into game page sidebar
- Added getTopAgents query function

## Linear
PERDIX-140

## Test plan
- [ ] Verify leaderboard displays on game page
- [ ] Verify agents are sorted by win rate
- [ ] Verify loading state works correctly
EOF
)"
```

### Step 9: Update Linear Status (if available)

```javascript
ToolSearch("select:mcp__linear__update_issue")

mcp__linear__update_issue({
  issueId: issue.id,
  stateId: "in-review"  // Or find the "In Review" state ID
})
```

### Step 10: Output Summary

**If created new ticket:**
```
Analyzing changes...
- 3 files modified in components/game/

Creating Linear ticket...
✓ PERDIX-140: Add leaderboard to game page

Switching to branch...
✓ perdix-140-add-leaderboard-to-game-page

Committing...
✓ feat: add leaderboard to game page (Fixes PERDIX-140)

Pushing & creating PR...
✓ PR #42: https://github.com/org/repo/pull/42

Updating Linear...
✓ PERDIX-140 → In Review

Done! 🚀

When you get review feedback, run /bruhs peep to address comments.
```

**If using existing ticket (from cook):**
```
Analyzing changes...
- 2 files modified in app/settings/, lib/hooks/

Using existing ticket...
✓ PERDIX-145: Add dark mode toggle to settings page

Switching to branch...
✓ perdix-145-add-dark-mode-toggle-to-settings-page

Committing...
✓ feat: add dark mode toggle to settings page (Fixes PERDIX-145)

Pushing & creating PR...
✓ PR #45: https://github.com/org/repo/pull/45

Updating Linear...
✓ PERDIX-145 → In Review

Done! 🚀

When you get review feedback, run /bruhs peep to address comments.
```

## Configuration

Reads `.claude/bruhs.json`:

```json
{
  "integrations": {
    "linear": {
      "team": "Perdix Labs",
      "project": "Gambit",
      "labels": {
        "feat": "Feature",
        "fix": "Bug",
        "chore": "Chore",
        "refactor": "Improvement"
      }
    }
  }
}
```

The `labels` map commit types to Linear label names. At runtime, yeet fetches available labels from Linear and matches by name.

## Git-Only Mode

If Linear MCP not available, yeet still works:

1. ~~Create Linear ticket~~ (skipped)
2. Generate branch name from change type + description
3. Stage and commit (without ticket reference)
4. Push and create PR
5. ~~Update Linear~~ (skipped)

Output:
```
Analyzing changes...
- 3 files modified in components/game/

⚠ Linear not configured (git-only mode)

Switching to branch...
✓ feat/add-leaderboard

Committing...
✓ feat: add leaderboard to game page

Pushing & creating PR...
✓ PR #42: https://github.com/org/repo/pull/42

Done! 🚀

When you get review feedback, run /bruhs peep to address comments.
```

## Examples

### After /bruhs cook (from feature description)

```
> /bruhs yeet

Analyzing changes...
- 2 files created
- 1 file modified
- Type: feat (new feature)

Creating Linear ticket...
✓ PERDIX-141: Add dark mode toggle

Switching to branch...
✓ perdix-141-add-dark-mode-toggle

Committing...
✓ feat: add dark mode toggle (Fixes PERDIX-141)

Pushing & creating PR...
✓ PR #43: https://github.com/perdixlabs/gambit/pull/43

Updating Linear...
✓ PERDIX-141 → In Review

Done! 🚀

When you get review feedback, run /bruhs peep to address comments.
```

### After /bruhs cook PERDIX-145 (from ticket)

```
> /bruhs yeet

Analyzing changes...
- 2 files modified
- Type: feat (new feature)

Using existing ticket...
✓ PERDIX-145: Add dark mode toggle to settings page

Switching to branch...
✓ perdix-145-add-dark-mode-toggle-to-settings-page

Committing...
✓ feat: add dark mode toggle to settings page (Fixes PERDIX-145)

Pushing & creating PR...
✓ PR #46: https://github.com/perdixlabs/gambit/pull/46

Updating Linear...
✓ PERDIX-145 → In Review

Done! 🚀

When you get review feedback, run /bruhs peep to address comments.
```

### Bug Fix

```
> /bruhs:yeet

Analyzing changes...
- 1 file modified in lib/engine/
- Type: fix (bug fix)

Creating Linear ticket...
✓ PERDIX-142: Fix card draw validation

Switching to branch...
✓ perdix-142-fix-card-draw-validation

Committing...
✓ fix: validate card draw against deck state (Fixes PERDIX-142)

Pushing & creating PR...
✓ PR #44: https://github.com/perdixlabs/gambit/pull/44

Updating Linear...
✓ PERDIX-142 → In Review

Done! 🚀

When you get review feedback, run /bruhs peep to address comments.
```

### Multiple Changes (Interactive)

If changes span multiple logical units:

```
> /bruhs:yeet

Analyzing changes...
- 5 files modified
- Changes appear to span multiple features

How would you like to ship?
○ Single commit (all changes together)
○ Interactive (choose files per commit)

> Interactive

Select files for first commit:
☑ components/game/leaderboard-card.tsx
☑ lib/db/queries.ts
☐ components/ui/button.tsx
☐ lib/utils.ts

Description: Add leaderboard component

[Creates ticket, branch, commit, PR for selection]

Remaining changes:
☑ components/ui/button.tsx
☑ lib/utils.ts

Ship these too? [Y/n]
```

## Git Best Practices

yeet follows modern git conventions:

| Old Command | Modern Command | Purpose |
|-------------|----------------|---------|
| `git checkout -b <branch>` | `git switch -c <branch>` | Create and switch to new branch |
| `git checkout <branch>` | `git switch <branch>` | Switch to existing branch |
| `git checkout -- <file>` | `git restore <file>` | Discard changes to file |
| `git reset HEAD <file>` | `git restore --staged <file>` | Unstage file |

**Why modern commands?**
- `git switch` and `git restore` were introduced in Git 2.23 (2019)
- Clearer intent: `switch` for branches, `restore` for files
- Less ambiguous than overloaded `checkout` command
- Better error messages and safer defaults

**Other conventions:**
- Stage specific files over `git add -A` when possible
- Use HEREDOC for multi-line commit messages
- Include ticket references in commit body, not title
- Push with `-u` to set upstream tracking

## Tips

- **Run after /bruhs:cook** - yeet is designed to follow cook for a complete workflow
- **Review before yeet** - Make sure you're happy with changes before shipping
- **One feature per yeet** - Keep commits focused; use interactive mode if needed
- **Check PR** - Always review the PR link to verify everything looks right
