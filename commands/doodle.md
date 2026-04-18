---
description: Visualize code architecture as tldraw diagrams (PRs, modules, deps, comparisons, freeform)
---

# doodle - Architecture Visualization

Render architectural diagrams from your codebase: PR changes, module dependency graphs, file dependents/dependencies, branch comparisons, codebase maps, or freeform descriptions. Outputs tldraw diagrams as PNG/SVG. Optionally posts to PR comments, saves to disk, or commits to the repo.

## Invocation

| Form | Mode | Behavior |
|------|------|----------|
| `/bruhs:doodle` | interactive | AskUserQuestion → pick mode |
| `/bruhs:doodle pr [PR# \| TICKET-ID \| URL]` | **pr** | Diagram a PR's changed files + dependency edges |
| `/bruhs:doodle module <path>` | **module** | Internal structure of a module/package |
| `/bruhs:doodle deps <file>` | **deps** | What this file imports (transitive depth N) |
| `/bruhs:doodle dependents <file>` | **dependents** | What imports this file (reverse) |
| `/bruhs:doodle compare <ref1> <ref2>` | **compare** | Architecture delta between two refs |
| `/bruhs:doodle map [path]` | **map** | Full codebase or subtree architecture map |
| `/bruhs:doodle "<freeform>"` | **freeform** | NL prompt → diagram (e.g. "auth flow") |

### Output flags (all modes)

| Flag | Effect |
|------|--------|
| `--out <path>` | Write image to a specific path |
| `--format png\|svg` | Image format (default `png`) |
| `--open` | Open the image after render |
| `--commit` | Commit image into `.bruhs/diagrams/` on current branch |
| `--gist` | Upload to a gist, print URL |
| `--pr-comment [PR#]` | Post into a PR comment (default: current branch's PR) |
| `--no-render` | Stop after generating shape JSON (`/tmp/bruhs-doodle-shapes.json`) |
| `--depth N` | For `deps`/`dependents`: max edge depth (default 2) |

## Prerequisites

- **Always:** an MCP server providing `create_diagram` (or equivalent). Recommended:
  - `bryantleft/tldraw-mcp` (recommended) — `claude mcp add --scope user --transport stdio tldraw -- npx -y tldraw-mcp`
  - `bassimeledath/tldraw-render` — `claude mcp add --scope user --transport stdio tldraw -- npx -y tldraw-render` (drop-in alternative)
- **For `pr` / `--pr-comment`:** GitHub CLI (`gh`) authenticated
- **For `--gist`:** `gh` with default scopes
- **For `freeform` mode:** no extra deps — uses Claude to author shapes directly

## MCP Contract

The single tool `doodle` depends on:

```typescript
{
  name: "create_diagram",
  input: {
    shapes: ShapeJson[],   // tldraw shape array
    format: "png" | "svg", // default "png"
    width?: number,        // canvas width, default 1920
    height?: number,       // canvas height, default 1080
  },
  output: {
    path: string,          // local file path of rendered image
    format: "png" | "svg",
  }
}
```

Some MCPs also expose `tldraw_read_me` (or similar) returning the exact shape spec — call it first if available so the shapes match the renderer's schema.

## Visual Vocabulary (shared across modes)

| Element | Visual |
|---------|--------|
| File / module | Geo box (rectangle), labeled |
| Module group | Frame containing files |
| Layer (e.g., `api`, `db`, `ui`) | tldraw page or labeled frame band |
| Import edge | Solid arrow |
| Re-export edge | Solid arrow, lighter color |
| Cross-module call | Bound arrow with label |
| Added (in diff modes) | Green fill |
| Modified (in diff modes) | Yellow fill |
| Deleted (in diff modes) | Red fill, dashed border |
| Removed edge (in diff modes) | Dashed red arrow |
| Added edge (in diff modes) | Solid green arrow |
| Highlighted focus (`deps`/`dependents`) | Heavier outline, bold label |

Keep it under ~30 nodes by default; collapse beyond that ("see full diagram with `--depth` higher").

---

## Mode: `pr`

PR-aware diagram. Shows changed files, their modules, edges that were added/removed/preserved.

### Pipeline

```
1. PR detect: arg | current branch | TICKET-ID | URL
2. gh api .../pulls/{n}/files (paginate) → file list with status
3. gh pr diff {n} → patch text for content-aware analysis
4. Group files into modules:
   - Workspace member > layer dir > top-level src/ > extension fallback
5. Parse imports old vs new (rg over use|import|from)
   - "old" via git show <base>:<path>
   - Diff edge sets → added / removed / preserved
6. Build shapes (frames=modules, geo=files, arrows=edges)
   - Colors by file status; arrow style by edge change
7. Call MCP create_diagram → PNG
8. Default upload: --pr-comment if PR detected, else --gist, else local
```

### Defaults
- Output: post as PR comment if a PR is detected, otherwise print path
- Comment format includes legend (added/modified/deleted) in `<details>`

---

## Mode: `module`

Show the internal structure of one module/package and its 1-hop external boundary.

### Pipeline

```
1. Resolve <path> to a module root:
   - workspace member with package.json | Cargo.toml
   - directory containing index.ts | mod.rs | lib.rs
2. List files (rg --files <path> | filter by source extension)
3. Parse intra-module imports (file → file within <path>)
4. Parse extra-module imports (file → external module name) — keep top 10 by count
5. Shapes:
   - Outer frame: <path>
   - Inner geo per file
   - Bound arrows for internal imports
   - "External" frame to the right with the top external dependencies
6. Render
```

### Use cases
- "What's actually inside `packages/store`?"
- "How do files in `bruhs-core/src/models` reference each other?"

---

## Mode: `deps`

Forward dependency graph: starting at `<file>`, walk outgoing imports up to `--depth` (default 2).

### Pipeline

```
1. Resolve <file> to absolute path
2. Walk imports BFS to depth N
3. Annotate each node with module it belongs to
4. Shapes:
   - Highlight starting file (heavier outline)
   - Color nodes by depth (saturation decreases with distance)
   - Solid arrows for direct imports
5. Render
```

---

## Mode: `dependents`

Reverse: who imports `<file>`?

### Pipeline

```
1. Build a reverse import index over the repo:
   - For TS/JS: rg "from ['\"]<resolved-path-or-alias>" --type ts,tsx,js,jsx
   - For Rust: rg "use\s+<crate-or-path>"
   - For Python: rg "from\s+<module>" or "import\s+<module>"
2. Walk back to depth N
3. Same shape construction as deps mode, arrows reversed
```

### Use cases
- "If I change `auth.rs`, what breaks?"
- "Find every consumer of `useAuth`"

---

## Mode: `compare`

Architecture delta between two arbitrary refs (branches, tags, commits). Like `pr` mode but freed from the PR concept.

### Pipeline

```
1. git diff --name-status <ref1>..<ref2> → file list with status
2. Otherwise identical to pr mode (group, parse old/new imports, render)
```

### Use cases
- `compare main release/v0.5` — what's heading to the next release
- `compare HEAD~10 HEAD` — last 10 commits' architectural impact
- `compare main feat/refactor-auth` — preview of a feature branch

---

## Mode: `map`

Full codebase or subtree map. Coarsest view: every module as a box, edges = aggregated cross-module imports (thicker = more imports).

### Pipeline

```
1. Discover modules:
   - Workspace members from pnpm-workspace.yaml | Cargo.toml [workspace]
   - Else: top-level src/ subdirs as modules
   - If <path> given: use that as the root, modules = its subdirs
2. For each pair (mod_a, mod_b): count imports a→b
3. Shapes:
   - One geo per module, sized by file count
   - Arrows weighted by import count (stroke width)
   - Optional: layer-band coloring if conventional layers detected
4. Render
```

### Use cases
- New collaborator onboarding
- Pre-refactor "what are we working with"

---

## Mode: `freeform`

Natural language → diagram. No source-code introspection. Useful for ad-hoc sketching.

### Pipeline

```
1. Parse the freeform description ("auth flow with refresh tokens", "data flow from upload to S3")
2. Author shape JSON directly (Claude does this — no rg/gh involvement)
3. Render
```

### Use cases
- Sketches for design docs
- Whiteboard alternative when you're already in the terminal
- Cooking up explanations for a teammate

---

## Workflow (shared across modes)

### Step 0: Resolve mode

If no mode arg, dispatch via `AskUserQuestion`:

```javascript
AskUserQuestion({
  questions: [{
    question: "What do you want to doodle?",
    header: "Mode",
    multiSelect: false,
    options: [
      { label: "pr",         description: "PR architecture — changed files + edges" },
      { label: "module",     description: "One module's internal structure" },
      { label: "deps",       description: "What a file depends on (forward)" },
      { label: "dependents", description: "What depends on a file (reverse)" },
      { label: "compare",    description: "Architecture delta between two refs" },
      { label: "map",        description: "Codebase or subtree overview" },
      { label: "freeform",   description: "Sketch from a natural-language description" },
    ]
  }]
})
```

### Step 1: Verify MCP

```javascript
const renderTool = ToolSearch("select:mcp__tldraw__create_diagram")
              || ToolSearch("select:mcp__tldraw-render__create_diagram");
if (!renderTool) {
  abort("No tldraw render MCP found. Install: claude mcp add --scope user --transport stdio tldraw -- npx -y tldraw-render");
}
```

### Step 2: Mode-specific data gathering

(See per-mode sections above.)

### Step 3: Build tldraw shapes

If the MCP exposes a shape-format reference tool, call it first and follow that schema. Otherwise, default schema:

```javascript
const shapes = [];

for (const [moduleId, module] of modules) {
  shapes.push({
    type: "frame",
    id: `frame:${moduleId}`,
    x: module.x, y: module.y, w: module.w, h: module.h,
    props: { name: module.name },
  });

  for (const file of module.files) {
    shapes.push({
      type: "geo",
      id: `geo:${file.path}`,
      parentId: `frame:${moduleId}`,
      x: file.x, y: file.y, w: 180, h: 60,
      props: {
        geo: "rectangle",
        text: file.basename,
        color: nodeColor(file),  // green/yellow/red/grey/blue
        fill: file.changed || file.focus ? "solid" : "none",
        size: file.focus ? "l" : "m",
      },
    });
  }
}

for (const edge of edges) {
  shapes.push({
    type: "arrow",
    id: `arrow:${edge.from}->${edge.to}`,
    props: {
      color: edgeColor(edge),
      dash:  edge.kind === "removed" ? "dashed" : "solid",
      size:  edge.weight > 5 ? "l" : "m",
      start: { type: "binding", boundShapeId: `geo:${edge.from}` },
      end:   { type: "binding", boundShapeId: `geo:${edge.to}` },
    },
  });
}
```

Layout strategy:
- **`pr`/`compare`/`map`:** layered top-to-bottom by inferred layer; force-directed within layer
- **`module`:** outer frame for the module, files in a grid inside, external imports off to the right
- **`deps`/`dependents`:** focus node centered, depth = radial distance
- **`freeform`:** Claude composes layout

### Step 4: Render

```javascript
const { path, format } = mcp__tldraw__create_diagram({
  shapes,
  format: opts.format || "png",
  width: 1920,
  height: 1080,
});
```

### Step 5: Output destination

Pick destination by flag, with mode-aware defaults:

```javascript
if (opts.noRender)   return saveShapesJson("/tmp/bruhs-doodle-shapes.json");
if (opts.out)        return moveTo(path, opts.out);
if (opts.prComment)  return postPrComment(path, opts.prComment);
if (opts.gist)       return uploadGist(path);
if (opts.commit)     return commitToRepo(path);

// Mode defaults
if (mode === "pr" && hasPr)  return postPrComment(path);
return printPath(path);
```

#### `postPrComment(path, prNumber)`

```bash
# Upload to gist (gh accepts binary files)
gist_url=$(gh gist create "$path" --desc "bruhs doodle (${mode}): PR #${prNumber}" --filename "doodle-${mode}-${prNumber}.png")
gist_id=$(basename "$gist_url")
raw_url="https://gist.githubusercontent.com/${USER}/${gist_id}/raw/doodle-${mode}-${prNumber}.png"

# Compose comment with mode-aware legend
body=$(cat <<EOF
## 🎨 Architecture diagram (${mode})

![${mode} diagram](${raw_url})

<details>
<summary>Legend</summary>
${legendForMode(mode)}

Generated by \`/bruhs:doodle ${mode}\`. Re-run on this PR to update.
</details>
EOF
)

gh pr comment "$prNumber" --body "$body"
```

#### `commitToRepo(path)`

```bash
mkdir -p .bruhs/diagrams
dest=".bruhs/diagrams/${slugForMode(mode)}.png"
cp "$path" "$dest"
git add "$dest"
git commit -m "chore(doodle): ${mode} diagram"
git push 2>/dev/null  # silently skip push if not pushable
```

### Step 6: Show summary

```
✅ doodle complete
   Mode:    pr
   Image:   <gist URL or local path>
   Comment: https://github.com/{owner}/{repo}/pull/42#issuecomment-...
   Stats:   8 modules · 23 files · 47 edges
```

---

## Reusing across other commands

The diagram pipeline is decoupled — other bruhs commands can invoke `doodle` modes without going through the slash command:

| Caller | Mode | Use case |
|--------|------|----------|
| `cook` | `freeform` or `module` | Sketch the proposed architecture before building |
| `peep` | `pr` | Quick visual reviewers can match against the diff |
| `slop` | `map` | Render module-level "smelliest neighborhoods" overlay |

When invoking from another command, prefer building shape JSON inline + calling the MCP directly (skip the orchestration layer).

---

## Edge Cases

- **PR / compare with > 100 changed files** — collapse to module-level only ("Diagram simplified to module level (130 files).")
- **`map` of huge monorepos** — limit to N=30 top modules by file count, group remainder as "other"
- **Renamed files** — render as one box with both names, label the arrow with the rename
- **Cross-repo PRs (forks)** — `gh pr view` resolves the head repo automatically
- **Cyclic dependencies** — render as bidirectional arrows; tldraw auto-routes
- **No detectable imports** — fall back to "files only" diagram with no edges and a note
- **Diff > 3000 lines in `pr`/`compare`** — render headline modules + edges; offer `--full` to render every file

---

## Config

Optional in `.claude/bruhs.json`:

```json
{
  "doodle": {
    "tldrawMcp": "tldraw",                  // MCP server name
    "defaultUpload": "gist",                // gist | commit | none
    "diagramDir": ".bruhs/diagrams",        // when commit
    "maxModules": 30,                       // collapse beyond
    "maxDepth": 2,                          // default for deps/dependents
    "modeDefaults": {
      "pr":      { "upload": "pr-comment" },
      "compare": { "upload": "gist" },
      "map":     { "upload": "commit" }
    }
  }
}
```

## Failure modes

| Error | Action |
|-------|--------|
| MCP not installed | Print install command, abort |
| `gh` not authenticated | Print `gh auth login` hint, abort (only for modes that need it) |
| PR not found (in `pr` mode) | Confirm PR# / Linear ID, abort |
| Diagram render failed | Save shape JSON to `/tmp/bruhs-doodle-shapes.json`, print path, abort |
| Gist creation failed | Fall back to `--commit`; if both fail, save locally and print path |
| Comment post failed | Print the gist URL so user can paste manually |
| Module path doesn't exist (in `module`/`map`) | List candidate paths from the workspace, abort |
