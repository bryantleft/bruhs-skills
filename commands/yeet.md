---
description: Ship workflow - Linear ticket → Branch → Commit → PR
---

# yeet - Ship Workflow

Ship code that's ready to go. Creates Linear ticket, commits, pushes, and opens PR.

## Invocation

- `/bruhs:yeet` - Ship current changes
- `/bruhs:yeet` after `/bruhs:cook` - Complete the cooking workflow

## Prerequisites

- Changes ready to commit (staged or unstaged)
- GitHub CLI (`gh`) authenticated
- Linear MCP configured (optional, will work without)

## Workflow

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

### Step 4: Create Linear Ticket (if available)

Load Linear MCP tools and create issue:

```javascript
// Load Linear tools
ToolSearch("select:mcp__linear__create_issue")
ToolSearch("select:mcp__linear__list_issue_labels")

// Get labels for the team
labels = mcp__linear__list_issue_labels({ teamId: config.linear.team })

// Map change type to label
labelId = findLabel(labels, config.linear.labelMapping[changeType])

// Create issue
issue = mcp__linear__create_issue({
  title: generatedTitle,
  teamId: config.linear.team,
  projectId: config.linear.project,
  labelIds: [labelId],
  assigneeId: "me"  // Auto-assign to current user
})

// Capture the branch name Linear generates
branchName = issue.gitBranchName  // e.g., "perdix-140-improve-game-state-validation"
ticketId = issue.identifier  // e.g., "PERDIX-140"
```

### Step 5: Checkout Branch

```bash
git checkout -b <branchName>
```

Example:
```bash
git checkout -b perdix-140-improve-game-state-validation
```

If Linear not available, generate branch name:
```bash
# Format: <type>/<short-description>
git checkout -b feat/add-leaderboard
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

```
Analyzing changes...
- 3 files modified in components/game/

Creating Linear ticket...
✓ PERDIX-140: Add leaderboard to game page

Checking out branch...
✓ perdix-140-add-leaderboard-to-game-page

Committing...
✓ feat: add leaderboard to game page (Fixes PERDIX-140)

Pushing & creating PR...
✓ PR #42: https://github.com/org/repo/pull/42

Updating Linear...
✓ PERDIX-140 → In Review

Done! 🚀
```

## Configuration

Reads `.claude/bruhs.json`:

```json
{
  "integrations": {
    "linear": {
      "team": "Perdix Labs",
      "project": "Gambit",
      "labelMapping": {
        "feat": "Feature",
        "fix": "Bug",
        "chore": "Chore",
        "refactor": "Improvement"
      }
    }
  }
}
```

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

Checking out branch...
✓ feat/add-leaderboard

Committing...
✓ feat: add leaderboard to game page

Pushing & creating PR...
✓ PR #42: https://github.com/org/repo/pull/42

Done! 🚀
```

## Examples

### After /bruhs:cook

```
> /bruhs:yeet

Analyzing changes...
- 2 files created
- 1 file modified
- Type: feat (new feature)

Creating Linear ticket...
✓ PERDIX-141: Add dark mode toggle

Checking out branch...
✓ perdix-141-add-dark-mode-toggle

Committing...
✓ feat: add dark mode toggle (Fixes PERDIX-141)

Pushing & creating PR...
✓ PR #43: https://github.com/perdixlabs/gambit/pull/43

Updating Linear...
✓ PERDIX-141 → In Review

Done! 🚀
```

### Bug Fix

```
> /bruhs:yeet

Analyzing changes...
- 1 file modified in lib/engine/
- Type: fix (bug fix)

Creating Linear ticket...
✓ PERDIX-142: Fix card draw validation

Checking out branch...
✓ perdix-142-fix-card-draw-validation

Committing...
✓ fix: validate card draw against deck state (Fixes PERDIX-142)

Pushing & creating PR...
✓ PR #44: https://github.com/perdixlabs/gambit/pull/44

Updating Linear...
✓ PERDIX-142 → In Review

Done! 🚀
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

## Tips

- **Run after /bruhs:cook** - yeet is designed to follow cook for a complete workflow
- **Review before yeet** - Make sure you're happy with changes before shipping
- **One feature per yeet** - Keep commits focused; use interactive mode if needed
- **Check PR** - Always review the PR link to verify everything looks right
