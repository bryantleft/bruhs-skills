---
description: Clean up after merge and switch to base branch
---

# dip - Clean Up After Merge

Clean up your feature branch after merging and switch back to the base branch to start fresh.

## Invocation

- `/bruhs dip` - Clean up current branch and switch to base

## Prerequisites

- Feature branch merged (or ready to be deleted)
- On a feature branch (not main/dev)

## Workflow

### Step 1: Check Current State

```bash
git branch --show-current
git status
```

If on base branch already:
```
Already on main. Nothing to clean up!
```

If uncommitted changes exist:
```
⚠ You have uncommitted changes:
  - components/foo.tsx (modified)

How would you like to proceed?
○ Stash changes - Save for later
○ Discard changes - Lose all changes
○ Abort - Stay on current branch
```

### Step 2: Detect Base Branch

Auto-detect the default branch from the remote:

```bash
# Detect from GitHub CLI (preferred)
baseBranch = $(gh repo view --json defaultBranchRef -q '.defaultBranchRef.name')

# Fallback to git remote
if (!baseBranch) {
  baseBranch = $(git remote show origin | grep "HEAD branch" | cut -d: -f2 | xargs)
}
```

This automatically detects `main`, `master`, `dev`, or whatever the repo's default branch is.

### Step 3: Switch to Base Branch

```bash
git switch <baseBranch>
```

Example:
```bash
git switch main
```

### Step 4: Pull Latest

```bash
git pull origin <baseBranch>
```

### Step 5: Delete Feature Branch

Get the branch we were on:

```bash
# Delete local branch
git branch -d <featureBranch>

# Delete remote branch (if exists)
git push origin --delete <featureBranch>
```

If branch wasn't merged:
```
⚠ Branch 'feat/unmerged-feature' is not fully merged.

Delete anyway?
○ Yes - Force delete (git branch -D)
○ No - Keep branch
```

### Step 6: Check for Stashed Changes

```bash
git stash list | grep "bruhs:"
```

If stash exists from cook:
```
💡 You have stashed changes from before your last feature:
   stash@{0}: On main: bruhs: stashed before add-leaderboard

Would you like to restore them?
○ Yes - Run git stash pop
○ No - Keep stashed for later
○ Drop - Delete the stash
```

### Step 7: Output Summary

```
Switching to main...
✓ Switched to main

Pulling latest...
✓ Up to date with origin/main

Cleaning up...
✓ Deleted local branch: perdix-139-make-model-form-image-upload-fully-rounded
✓ Deleted remote branch: origin/perdix-139-make-model-form-image-upload-fully-rounded

Ready for your next feature! Run /bruhs cook to start.
```

## Examples

### After Merging PR

```
> /bruhs dip

Switching to main...
✓ Switched to main

Pulling latest...
✓ Pulled 3 new commits

Cleaning up...
✓ Deleted local branch: perdix-139-make-model-form-image-upload-fully-rounded
✓ Deleted remote branch: origin/perdix-139-make-model-form-image-upload-fully-rounded

Ready for your next feature! Run /bruhs cook to start.
```

### With Stashed Changes

```
> /bruhs dip

Switching to main...
✓ Switched to main

Pulling latest...
✓ Up to date

Cleaning up...
✓ Deleted local branch: perdix-140-add-dark-mode

💡 You have stashed changes from before your last feature:
   stash@{0}: On main: bruhs: stashed before add-dark-mode

Would you like to restore them?
○ Yes ← selected

Restoring stash...
✓ Applied stash@{0}

Ready for your next feature! Run /bruhs cook to start.
```

### With Uncommitted Changes

```
> /bruhs dip

⚠ You have uncommitted changes:
  - components/ui/button.tsx (modified)

How would you like to proceed?
○ Stash changes ← selected

Stashing...
✓ Stashed as "bruhs: stashed before dip"

Switching to main...
✓ Switched to main

Pulling latest...
✓ Up to date

Cleaning up...
✓ Deleted local branch: feat/button-update

💡 You have stashed changes. Run `git stash pop` when ready.

Ready for your next feature! Run /bruhs cook to start.
```

### Unmerged Branch

```
> /bruhs dip

Switching to main...
✓ Switched to main

Pulling latest...
✓ Up to date

Cleaning up...
⚠ Branch 'feat/experimental' is not fully merged.

Delete anyway?
○ No ← selected

Keeping branch 'feat/experimental'.

Ready for your next feature! Run /bruhs cook to start.
```

## Git Best Practices

| Old Command | Modern Command | Purpose |
|-------------|----------------|---------|
| `git checkout main` | `git switch main` | Switch to base branch |
| `git branch -d` | `git branch -d` | Delete merged branch (safe) |
| `git branch -D` | `git branch -D` | Force delete unmerged branch |

## Tips

- **Run after merge** - Wait until your PR is merged before running dip
- **Check Linear** - Dip doesn't update Linear status; your PR merge should auto-close the ticket
- **Stash recovery** - If you accidentally dropped a stash, check `git fsck --unreachable | grep commit` within a few days
