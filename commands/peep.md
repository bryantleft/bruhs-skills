---
description: Address PR review comments and optionally merge
---

# peep - Address PR Review Comments

Review and address PR feedback, push fixes, and optionally merge when ready.

## Invocation

- `/bruhs peep` - Address comments on current branch's PR
- `/bruhs peep 42` - Address comments on PR #42 (switches branch if needed)
- `/bruhs peep PERDIX-145` - Find PR by Linear ticket ID

## Prerequisites

- GitHub CLI (`gh`) authenticated
- Open PR with review comments
- Linear MCP configured (optional, for ticket ID lookup)

## Workflow

### Step 1: Detect PR

**If no argument provided:**

```bash
# Get PR for current branch
pr=$(gh pr view --json number,headRefName,url,state,reviewDecision,title 2>/dev/null)
```

If no PR found:
```
No PR found for current branch.

Would you like to:
○ Specify a PR number
○ Abort
```

**If PR number provided:**

```bash
pr=$(gh pr view <number> --json number,headRefName,url,state,reviewDecision,title)
currentBranch=$(git branch --show-current)

# Switch to PR branch if needed
if [ "$currentBranch" != "$headRefName" ]; then
  git fetch origin $headRefName
  git switch $headRefName
  git pull origin $headRefName
fi
```

**If Linear ticket ID provided:**

```javascript
ToolSearch("select:mcp__linear__get_issue")

// Get issue details
issue = mcp__linear__get_issue({ identifier: "PERDIX-145" })

// Search for PR with ticket reference in title or body
pr=$(gh pr list --search "PERDIX-145" --json number,headRefName --jq '.[0]')

// Then proceed as with PR number
```

### Step 2: Fetch Review Comments

```bash
# Get all review comments
gh api repos/{owner}/{repo}/pulls/{number}/comments --jq '.[] | {
  id: .id,
  path: .path,
  line: .line,
  body: .body,
  user: .user.login,
  created_at: .created_at,
  in_reply_to_id: .in_reply_to_id
}'

# Get review threads with resolution status
gh api graphql -f query='
  query($owner: String!, $repo: String!, $number: Int!) {
    repository(owner: $owner, name: $repo) {
      pullRequest(number: $number) {
        reviewThreads(first: 100) {
          nodes {
            id
            isResolved
            path
            line
            comments(first: 10) {
              nodes {
                body
                author { login }
              }
            }
          }
        }
      }
    }
  }
'

# Get PR reviews (approved, changes requested, etc.)
gh pr view <number> --json reviews --jq '.reviews[] | {user: .author.login, state: .state, body: .body}'
```

### Step 3: Categorize Comments

Parse and categorize each unresolved comment thread:

| Category | Indicators | Action |
|----------|------------|--------|
| **must-fix** | "please fix", "this will break", "bug", "security", blocking review | Address immediately |
| **suggestion** | "consider", "might be better", "nit:", "optional" | Evaluate and decide |
| **question** | "why", "what does", "can you explain", "?" | Respond with explanation |
| **approval** | "lgtm", "looks good", "nice", ":+1:" | No action needed |

Display summary:
```
PR #42: Add leaderboard to game page
Branch: perdix-140-add-leaderboard

Review Status:
- @reviewer1: Changes Requested
- @reviewer2: Approved

Comments (4 unresolved):
┌─────────────┬──────┬─────────────────────────────────────┐
│ Category    │ Count│ Files                               │
├─────────────┼──────┼─────────────────────────────────────┤
│ must-fix    │ 1    │ lib/db/queries.ts                   │
│ suggestion  │ 2    │ components/game/leaderboard-card.tsx│
│ question    │ 1    │ lib/hooks/use-leaderboard.ts        │
└─────────────┴──────┴─────────────────────────────────────┘

Ready to address comments?
○ Yes - Go through each comment
○ View all comments first
○ Abort
```

### Step 4: Address Each Comment

For each unresolved comment thread, in order of priority (must-fix first):

```
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
[1/4] must-fix | lib/db/queries.ts:45
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

@reviewer1:
> This query isn't using an index. Add .orderBy(desc(agentStats.winRate))
> before the limit to use the existing index.

Current code:
```typescript
export async function getTopAgents(limit = 10) {
  return db.select().from(agentStats).limit(limit);
}
```

How would you like to proceed?
○ Apply fix - Add orderBy clause
○ Skip - Address later
○ Discuss - Need clarification
```

**If "Apply fix":**

1. Read the file for full context
2. Apply the fix using Edit tool
3. Show the diff
4. Confirm the change addresses the comment

```
Applying fix...

✓ Updated lib/db/queries.ts:45

Diff:
- return db.select().from(agentStats).limit(limit);
+ return db.select().from(agentStats).orderBy(desc(agentStats.winRate)).limit(limit);

Does this address the comment?
○ Yes - Continue to next
○ No - Revise
```

**If "Skip":**

```
Skipped. Will remain unresolved.
```

**If "Discuss":**

```
What would you like to clarify?
> [user types response]

Posting reply...
✓ Replied to @reviewer1's comment
```

### Step 5: Handle Suggestions

For suggestions, provide more nuanced options:

```
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
[2/4] suggestion | components/game/leaderboard-card.tsx:23
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

@reviewer2:
> nit: Consider using a constant for the max items instead of magic number 10

Current code:
```typescript
const topAgents = agents.slice(0, 10);
```

How would you like to proceed?
○ Apply - Use constant
○ Acknowledge - Good idea, will do
○ Decline - Explain why not
○ Skip - Address later
```

**If "Decline":**

```
Why decline this suggestion?
> [user types or selects reason]

Suggested response:
"Thanks for the suggestion! I'm keeping it as-is because this is only used
in one place and the limit is already parameterized in the query. Adding
a constant here would be over-abstraction."

Post this reply?
○ Yes
○ Edit first
```

### Step 6: Handle Questions

For questions, help formulate a response:

```
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
[4/4] question | lib/hooks/use-leaderboard.ts:12
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

@reviewer1:
> Why refetch every 5 seconds? Seems aggressive for a leaderboard.

Current code:
```typescript
const { data } = useQuery({
  queryKey: ['leaderboard'],
  queryFn: getTopAgents,
  refetchInterval: 5000,
});
```

Suggested response based on context:
"The 5-second interval matches our game state polling. During active games,
the leaderboard can change frequently as matches complete. Happy to make
this configurable if you think it's too aggressive."

How would you like to proceed?
○ Post suggested response
○ Edit and post
○ Skip
```

### Step 7: Commit and Push Fixes

After addressing all comments:

```bash
# Check for changes
git status
git diff
```

If changes were made:

```
Changes made:
- lib/db/queries.ts (1 fix)
- components/game/leaderboard-card.tsx (1 fix)

Commit message:
"fix: address PR review feedback

- Add orderBy to getTopAgents query for index usage
- Extract LEADERBOARD_LIMIT constant"

Commit and push?
○ Yes
○ Edit message first
○ Abort
```

```bash
git add -A
git commit -m "$(cat <<'EOF'
fix: address PR review feedback

- Add orderBy to getTopAgents query for index usage
- Extract LEADERBOARD_LIMIT constant
EOF
)"
git push
```

### Step 8: Resolve Threads (Optional)

```javascript
// For comments that were addressed with code changes
gh api graphql -f query='
  mutation($threadId: ID!) {
    resolveReviewThread(input: {threadId: $threadId}) {
      thread { isResolved }
    }
  }
' -f threadId="$threadId"
```

```
Resolve addressed comment threads?
○ Yes - Mark 2 threads as resolved
○ No - Let reviewer resolve
```

### Step 9: Check Merge Readiness

```bash
# Refresh PR status
gh pr view <number> --json reviewDecision,mergeable,mergeStateStatus,statusCheckRollup
```

Evaluate:
- `reviewDecision`: APPROVED, CHANGES_REQUESTED, or REVIEW_REQUIRED
- `mergeable`: MERGEABLE, CONFLICTING, or UNKNOWN
- `mergeStateStatus`: CLEAN, UNSTABLE, DIRTY
- `statusCheckRollup`: All checks passing?

### Step 10: Offer to Merge

**If ready to merge:**

```
✓ All review comments addressed
✓ PR approved by @reviewer1, @reviewer2
✓ CI passing
✓ No merge conflicts

Ready to merge?
○ Squash and merge (recommended)
○ Merge commit
○ Rebase and merge
○ Not yet - Wait for more reviews
```

**If merge blocked:**

```
⚠ Cannot merge yet:

- ✗ Changes requested by @reviewer1
- ✓ CI passing
- ✓ No merge conflicts

Waiting for @reviewer1 to re-review after your fixes.

Options:
○ Request re-review from @reviewer1
○ Done for now - Exit peep
```

```bash
# Request re-review
gh pr edit <number> --add-reviewer reviewer1
```

### Step 11: Merge and Transition

If user chooses to merge:

```bash
# Squash and merge (default)
gh pr merge <number> --squash --delete-branch

# Or merge commit
gh pr merge <number> --merge --delete-branch

# Or rebase
gh pr merge <number> --rebase --delete-branch
```

After successful merge:

```
✓ PR #42 merged!

Switching to main and cleaning up...
```

Then automatically run the dip workflow:
- Switch to base branch
- Pull latest
- Delete local feature branch (remote already deleted by --delete-branch)
- Check for stashed changes

```
✓ Switched to main
✓ Pulled latest (includes your merged changes)
✓ Deleted local branch: perdix-140-add-leaderboard

Ready for your next feature! Run /bruhs cook to start.
```

### Step 12: Update Linear (if available)

If Linear MCP is configured and PR was merged:

```javascript
ToolSearch("select:mcp__linear__update_issue")

// Find the Done/Completed state
mcp__linear__update_issue({
  issueId: issueId,
  stateId: "done"  // Or find the "Done" state ID
})
```

```
Updating Linear...
✓ PERDIX-140 → Done
```

## Output Summary

**After addressing comments (not merging yet):**

```
PR #42: Add leaderboard to game page

Addressed:
✓ [must-fix] lib/db/queries.ts:45 - Added orderBy clause
✓ [suggestion] components/game/leaderboard-card.tsx:23 - Added constant
✓ [question] lib/hooks/use-leaderboard.ts:12 - Replied

Skipped:
- [suggestion] components/game/leaderboard-card.tsx:45 - Will address later

Committed and pushed:
✓ fix: address PR review feedback (abc1234)

Requested re-review from @reviewer1

Run /bruhs peep again after re-review, or wait for approval to merge.
```

**After addressing and merging:**

```
PR #42: Add leaderboard to game page

Addressed:
✓ [must-fix] lib/db/queries.ts:45 - Added orderBy clause
✓ [suggestion] components/game/leaderboard-card.tsx:23 - Added constant
✓ [question] lib/hooks/use-leaderboard.ts:12 - Replied

Committed and pushed:
✓ fix: address PR review feedback (abc1234)

Merged:
✓ PR #42 squash-merged into main

Cleaned up:
✓ Switched to main
✓ Deleted branch perdix-140-add-leaderboard

Linear:
✓ PERDIX-140 → Done

Ready for your next feature! Run /bruhs cook to start.
```

## Examples

### Simple Review - All Approved

```
> /bruhs peep

PR #42: Add leaderboard to game page
Branch: perdix-140-add-leaderboard

Review Status:
- @reviewer1: Approved
- @reviewer2: Approved ("LGTM!")

Comments (0 unresolved)

✓ All reviews approved
✓ CI passing
✓ No merge conflicts

Ready to merge?
○ Squash and merge ← selected

Merging...
✓ PR #42 merged!

✓ Switched to main
✓ Pulled latest
✓ Deleted branch perdix-140-add-leaderboard
✓ PERDIX-140 → Done

Ready for your next feature! Run /bruhs cook to start.
```

### Multiple Rounds of Review

```
> /bruhs peep

PR #42: Add leaderboard to game page

Comments (3 unresolved):
- 1 must-fix
- 2 suggestions

[... addresses comments ...]

✓ Pushed fixes

⚠ Cannot merge yet - waiting for re-review

Requested re-review from @reviewer1

---

[Later, after re-review]

> /bruhs peep

PR #42: Add leaderboard to game page

Review Status:
- @reviewer1: Approved
- @reviewer2: Approved

Comments (0 unresolved)

Ready to merge?
○ Squash and merge ← selected

✓ PR #42 merged!
✓ Switched to main
✓ PERDIX-140 → Done

Ready for your next feature! Run /bruhs cook to start.
```

### Switching Branches

```
> /bruhs peep 42

Currently on: main
PR #42 is on branch: perdix-140-add-leaderboard

Switching branches...
✓ Fetched origin/perdix-140-add-leaderboard
✓ Switched to perdix-140-add-leaderboard
✓ Pulled latest

[... continues with review ...]
```

## Tips

- **Run early, run often** - Don't wait for all reviews; address feedback as it comes
- **Must-fix first** - Always prioritize blocking feedback
- **Decline gracefully** - It's okay to push back on suggestions with good reasoning
- **Re-request reviews** - After pushing fixes, explicitly request re-review
- **Let reviewers resolve** - Some teams prefer reviewers mark their own threads resolved
