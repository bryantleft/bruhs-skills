---
description: Summarize your authored commits over a time window into a short status update — bugfix / tech-debt / net-new classification, 2-5 bullets max. Use for standups, weekly retros, sprint reviews, "what did I get done" check-ins.
---

# recap - Status Update From Git Log

Generate a concise, executive-readable recap of work shipped by the current git user over a time window. Source: `git log --author`. Output: a short summary suitable for standup, plus an optional classification paragraph.

## Contents

- [Invocation](#invocation)
- [Workflow](#workflow)
- [Time Window Resolution](#time-window-resolution)
- [Classification Rules](#classification-rules)
- [Output Templates](#output-templates)
- [Examples](#examples)
- [Tips](#tips)

---

## Invocation

- `/bruhs:recap` — Default: last 7 days, current branch's repo, current git user
- `/bruhs:recap yesterday`
- `/bruhs:recap "last 3 days"`
- `/bruhs:recap "last week"` — Adds the bugfix/tech-debt/net-new classification paragraph
- `/bruhs:recap "2026-05-14..2026-05-21"` — Explicit date range
- `/bruhs:recap --all-authors` — Recap for the whole team, not just you
- `/bruhs:recap --branch main` — Restrict to a specific branch's history
- `/bruhs:recap --linear` — Cross-reference Linear ticket IDs in commit messages and pull ticket titles

## Workflow

### Step 1: Resolve User and Window

```bash
# Current git user
EMAIL=$(git config user.email)

if [ -z "$EMAIL" ]; then
  # Bail — never guess
  echo "git user.email not set. Run: git config user.email <your-email>"
  exit 1
fi
```

Resolve the time window — see [Time Window Resolution](#time-window-resolution). Always echo the **resolved absolute date range** back to the user (e.g. `2026-05-14 → 2026-05-21`) so they can sanity-check what was actually scanned.

### Step 2: Collect Commits

```bash
git log \
  --author="$EMAIL" \
  --since="<from>" --until="<to>" \
  --no-merges \
  --pretty=format:'%h%x09%ai%x09%s%x09%b%x1e' \
  --shortstat
```

Excludes:
- merge commits (`--no-merges`)
- uncommitted / staged changes (we summarize shipped work only)
- commits authored by others (unless `--all-authors`)

Capture for each commit:
- short SHA
- subject line
- body (often contains the Linear ticket ID)
- shortstat (files / lines)

### Step 3: Group Into Meaningful Changes

Don't list every commit. Collapse into 2-5 bullets, each representing a **shipped unit of work**:

- Multiple commits with the same Linear ticket → one bullet
- "fix: typo / nit / lint" across many files → roll up into one bullet or drop entirely
- Refactors that span 5 commits over 2 days but achieve one outcome → one bullet
- Cosmetic-only commits (formatting, imports, minor renames) → drop unless they're the whole window

Each bullet should be:
- **one short clause** (under ~15 words)
- **describes what changed in the system**, not what files moved
- **functional, not motivational** — "Added LeaderboardCard", not "Improved game page UX"

### Step 4: Classify (Optional)

When the user invoked `recap` over a longer window (≥ 5 days) or explicitly asked for a weekly recap, add a one-paragraph classification using [Classification Rules](#classification-rules):

> This week was mostly bugfix-heavy (3 fixes across the search pipeline), with one net-new addition (the LeaderboardCard surface) and a small Convex schema cleanup as tech debt.

### Step 5: Output

Use one of the [Output Templates](#output-templates). Always include the resolved date range.

## Time Window Resolution

| User input | Resolution |
|---|---|
| (empty) | `7 days ago` → `now` |
| `yesterday` | `2 days ago 00:00` → `1 day ago 23:59` |
| `today` | `today 00:00` → `now` |
| `last N days` | `N+1 days ago` → `now` |
| `last week` | `8 days ago` → `1 day ago` (excludes today) |
| `this week` | most recent Monday → `now` |
| `<YYYY-MM-DD>..<YYYY-MM-DD>` | Use literally |

Always convert relative inputs to absolute dates **before** running `git log`, and surface those absolute dates in the output. Future-you (or the user) reading the recap a month later needs to know what "last week" meant.

## Classification Rules

Map each grouped bullet to one of three buckets, based on commit subject prefix, ticket label (if Linear), or — fallback — diff inspection:

| Bucket | Signals |
|---|---|
| **Bugfix** | `fix:` prefix, `bug` / `Bug` Linear label, reverts, tests added without behavior change, hotfix branches |
| **Tech debt** | `refactor:`, `chore:`, `docs:`, dependency bumps, type-only changes, test infra changes, deletions outnumbering additions by > 2× |
| **Net-new** | `feat:` prefix, `Feature` Linear label, new files in `src/` (not `__tests__`), new exported APIs |

Edge cases:
- A commit that fixes a regression in a feature shipped this same window → **Bugfix** (regression dominates).
- A refactor that enables a new feature still pending → **Tech debt** (capability isn't shipped yet).
- A test file added for a behavior that already existed → **Tech debt**, not Net-new.

## Output Templates

### Short (default, < 5-day window)

```
Recap — <from> → <to>  (<N> commits, <files> files, +<add>/-<del> LOC)

- <bullet 1>
- <bullet 2>
- <bullet 3>
```

### Long (≥ 5-day window or `--linear`)

```
Recap — <from> → <to>  (<N> commits, <files> files, +<add>/-<del> LOC)

- <bullet 1>          [PROJ-123]
- <bullet 2>          [PROJ-145, PROJ-149]
- <bullet 3>          (no ticket)

Classification:
  <one sentence on bugfix mix, tech-debt mix, and net-new>
```

## Examples

### Default — yesterday

```
> /bruhs:recap yesterday

Recap — 2026-05-20 → 2026-05-20  (4 commits, 9 files, +312/-87 LOC)

- Added LeaderboardCard to game sidebar with `getTopAgents` query
- Fixed empty-deck draw crash in engine (PERDIX-142)
- Tightened drawCard return type to remove silent undefined
```

### Last week, with classification

```
> /bruhs:recap "last week"

Recap — 2026-05-14 → 2026-05-20  (11 commits, 28 files, +1402/-934 LOC)

- Added LeaderboardCard surface with pagination          [PERDIX-140]
- Reworked Convex `engine.ts` to remove orchestration sprawl  [PERDIX-138]
- Fixed empty-deck crash + 2 related game-state edge cases    [PERDIX-142, PERDIX-144]
- Deleted unused `legacy/` directory after migration verified

Classification:
  Bugfix-leaning week (3 fixes, all in engine), one net-new surface (LeaderboardCard),
  and one structural tech-debt cleanup (Convex engine refactor + legacy deletion).
```

### Linear-aware

```
> /bruhs:recap "last week" --linear

Recap — 2026-05-14 → 2026-05-20  (11 commits, 28 files, +1402/-934 LOC)

- LeaderboardCard surface with pagination
  ↳ PERDIX-140 "Add leaderboard to game page" (Feature)
- Convex engine.ts orchestration refactor
  ↳ PERDIX-138 "Reduce engine.ts complexity" (Improvement)
- Engine edge-case fixes
  ↳ PERDIX-142 "Empty-deck crash" (Bug)
  ↳ PERDIX-144 "Discard pile reshuffle off-by-one" (Bug)

Classification:
  3 Bug, 1 Feature, 1 Improvement.
```

### Whole team

```
> /bruhs:recap "last 7 days" --all-authors

Recap — 2026-05-14 → 2026-05-21  (34 commits across 4 authors)

By author:
  Bryant Le (11)        — LeaderboardCard, engine cleanup, 2 fixes
  Alice Chen (9)        — Search pipeline rework, GitHub source adapter
  Bob Tran (8)          — Auth refresh, invite-token flow
  Carlos Mendez (6)     — CI infra, Vercel deploy fixes

Classification:
  Mostly net-new (search + leaderboard) with a steady bugfix stream.
```

## Tips

- **Run before standup.** Faster than skimming Linear, more accurate than memory.
- **`--all-authors` for retros**, default for personal updates.
- **Pair with `/bruhs:doodle pr`** when the recap calls out a structural change — a diagram lands better than a sentence.
- **Pair with `/bruhs:slop`** if recap shows a lot of `fix:` commits in the same module — that's a signal the module wants a deeper look.
- **Don't editorialize.** `recap` describes what shipped, functionally. Motivation belongs in retros, not recaps.
