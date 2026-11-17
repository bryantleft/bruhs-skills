#!/usr/bin/env bash
# run_script_tests.sh — executable test harness for the scripts in skills/bruhs/scripts/.
#
# The JSON files in tests/specs/ are specs (prose). This script runs concrete
# assertions that exercise the same behaviors. One PASS/FAIL line per
# assertion; non-zero exit if anything fails. These are deterministic and need
# no model; the model-in-the-loop suite lives in evals/ (see evals/README.md).
#
# Usage:
#     bash tests/run_script_tests.sh
#
# Covers (tests/specs/*.json → assertion groups):
#     sync_bruhs_block.py     → sync-bruhs-block-preserves-hand-written.json
#     read_bruhs_block.py     → read-bruhs-block-legacy-fallback.json,
#                                read-bruhs-block-not-found.json
#     derive_stack_rules.py   → derive-stack-rules-coverage.json
#     detect_stack.py         → detect-stack-nextjs.json
#     detect_mcp_servers.py   → detect-mcp-servers-multi-workspace.json
#     validate_pr_ready.sh    → validate-pr-ready-node.json
#     write_bruhs_config.py   → write-bruhs-config-shim.json
#     walk_video.py           → walk-video-script.json
#     record_demo.mjs         → record-demo-shots.json
#     export_evals_json.py    → every evals/<case>/ loads; export is valid JSON
#     evals/*/scaffold.sh     → each builds its workspace offline; mocks in sync
#
# All work is done in $TMPDIR/bruhs-eval-<pid>; cleaned up on exit.

set -u

PLUGIN_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
SCRIPTS="$PLUGIN_DIR/skills/bruhs/scripts"
TESTS="$PLUGIN_DIR/tests"
WORK="$(mktemp -d -t bruhs-eval-XXXXXX)"
trap 'rm -rf "$WORK"' EXIT

pass=0
fail=0
fails=()

assert() {
    local label="$1"; shift
    if "$@" >/dev/null 2>&1; then
        printf '  [PASS] %s\n' "$label"
        pass=$((pass + 1))
    else
        printf '  [FAIL] %s\n' "$label"
        fail=$((fail + 1))
        fails+=("$label")
    fi
}

assert_eq() {
    local label="$1" expected="$2" actual="$3"
    if [ "$expected" = "$actual" ]; then
        printf '  [PASS] %s\n' "$label"
        pass=$((pass + 1))
    else
        printf '  [FAIL] %s (expected %q, got %q)\n' "$label" "$expected" "$actual"
        fail=$((fail + 1))
        fails+=("$label")
    fi
}

assert_contains() {
    local label="$1" needle="$2" haystack="$3"
    if printf '%s' "$haystack" | grep -qF "$needle"; then
        printf '  [PASS] %s\n' "$label"
        pass=$((pass + 1))
    else
        printf '  [FAIL] %s (missing %q)\n' "$label" "$needle"
        fail=$((fail + 1))
        fails+=("$label")
    fi
}

assert_not_contains() {
    local label="$1" needle="$2" haystack="$3"
    if printf '%s' "$haystack" | grep -qF "$needle"; then
        printf '  [FAIL] %s (unexpectedly found %q)\n' "$label" "$needle"
        fail=$((fail + 1))
        fails+=("$label")
    else
        printf '  [PASS] %s\n' "$label"
        pass=$((pass + 1))
    fi
}

# Run a command and capture its exit code without short-circuiting the script.
# Usage: ec=$(capture_ec command args...)
capture_ec() {
    "$@" >/dev/null 2>&1
    printf '%d' "$?"
}

heading() { printf '\n== %s ==\n' "$1"; }

STATE_JSON='{
  "integrations": {"linear": {"mcpServer": "linear-test", "team": "TEAM", "teamName": "Team", "project": "P", "projectName": "P"}},
  "tooling": {"mcps": ["linear"], "skills": ["superpowers"]},
  "stack": {"structure": "single", "framework": "Next.js", "styling": ["Tailwind CSS", "shadcn/ui"], "database": ["convex"], "auth": "better-auth", "testing": ["vitest"], "tooling": ["biome"]}
}'

#─────────────────────────────────────────────────────────────────────────────
heading "sync_bruhs_block.py — atomic, mirrored, preserves hand-written"
#─────────────────────────────────────────────────────────────────────────────

root="$WORK/sync"
mkdir -p "$root"
cat > "$root/CLAUDE.md" <<'EOF'
# CLAUDE.md

## Product Vision

Hand-written intro that must survive.

## bruhs-managed

<!-- bruhs:state:begin v1 -->
<!-- old block, will be replaced -->
```json
{"old": true}
```
<!-- bruhs:state:end -->

## My Hand-Written Rules

- Rule one.
- Rule two.
EOF
cp "$root/CLAUDE.md" "$root/AGENTS.md"

echo "$STATE_JSON" | python3 "$SCRIPTS/sync_bruhs_block.py" --kind state --root "$root" >/dev/null 2>&1

claude=$(cat "$root/CLAUDE.md")
agents=$(cat "$root/AGENTS.md")

assert_contains "preserves hand-written above marker (CLAUDE.md)" "Hand-written intro that must survive." "$claude"
assert_contains "preserves hand-written below marker (CLAUDE.md)" "My Hand-Written Rules" "$claude"
assert_contains "preserves hand-written above marker (AGENTS.md)" "Hand-written intro that must survive." "$agents"
assert_contains "writes new state inside marker"            "linear-test" "$claude"
assert_not_contains "old block contents are replaced"        '"old": true' "$claude"

# Mirror invariant: extract just the bruhs:state blocks and compare
extract_block() { sed -n '/<!-- bruhs:state:begin/,/<!-- bruhs:state:end/p' "$1"; }
assert_eq "CLAUDE.md and AGENTS.md state blocks are identical" "$(extract_block "$root/CLAUDE.md")" "$(extract_block "$root/AGENTS.md")"

# Idempotency
cp "$root/CLAUDE.md" "$root/CLAUDE.md.snap"
echo "$STATE_JSON" | python3 "$SCRIPTS/sync_bruhs_block.py" --kind state --root "$root" >/dev/null 2>&1
assert "idempotent — second run produces identical file" diff -q "$root/CLAUDE.md" "$root/CLAUDE.md.snap"

# Validation: invalid JSON exits 2 and does NOT modify the file
cp "$root/CLAUDE.md" "$root/CLAUDE.md.before"
err=$(echo "not valid json" | python3 "$SCRIPTS/sync_bruhs_block.py" --kind state --root "$root" 2>&1 >/dev/null; printf 'ec=%d' "$?")
ec="${err##*ec=}"
assert_eq "invalid JSON exits non-zero" "2" "$ec"
assert "invalid JSON does not touch file" diff -q "$root/CLAUDE.md" "$root/CLAUDE.md.before"

# Missing required field: stack
cp "$root/CLAUDE.md" "$root/CLAUDE.md.before2"
err=$(echo '{"tooling": {}}' | python3 "$SCRIPTS/sync_bruhs_block.py" --kind state --root "$root" 2>&1 >/dev/null; printf 'ec=%d' "$?")
ec="${err##*ec=}"
assert_eq "missing stack exits 2" "2" "$ec"
assert_contains "validation error mentions missing field" "stack" "$err"
assert "missing field does not touch file" diff -q "$root/CLAUDE.md" "$root/CLAUDE.md.before2"

# Creates missing files
fresh="$WORK/sync-fresh"
mkdir -p "$fresh"
echo "$STATE_JSON" | python3 "$SCRIPTS/sync_bruhs_block.py" --kind state --root "$fresh" >/dev/null 2>&1
assert "creates CLAUDE.md when missing" test -f "$fresh/CLAUDE.md"
assert "creates AGENTS.md when missing" test -f "$fresh/AGENTS.md"

# Empty rules input (a stack derive_stack_rules has no rules for) writes the placeholder
empty_root="$WORK/sync-empty-rules"
mkdir -p "$empty_root"
printf '' | python3 "$SCRIPTS/sync_bruhs_block.py" --kind rules --root "$empty_root" >/dev/null 2>&1
assert_eq "empty rules input exits 0" "0" "$?"
assert "empty rules input writes the placeholder" grep -q "No stack-specific rules detected" "$empty_root/CLAUDE.md"
printf '' | python3 "$SCRIPTS/sync_bruhs_block.py" --kind state --root "$empty_root" >/dev/null 2>&1
assert_eq "empty state input still exits 2" "2" "$?"

#─────────────────────────────────────────────────────────────────────────────
heading "read_bruhs_block.py — legacy fallback, not-found, kind isolation"
#─────────────────────────────────────────────────────────────────────────────

read_root="$WORK/read-legacy"
mkdir -p "$read_root/.claude"
echo "$STATE_JSON" > "$read_root/.claude/bruhs.json"

out=$(python3 "$SCRIPTS/read_bruhs_block.py" --kind state --root "$read_root" 2>/dev/null)
ec=$?
assert_eq "legacy fallback exits 0" "0" "$ec"
assert "legacy fallback prints valid JSON" python3 -c "import json,sys; json.loads(sys.argv[1])" "$out"
warn=$(python3 "$SCRIPTS/read_bruhs_block.py" --kind state --root "$read_root" 2>&1 >/dev/null)
assert_contains "legacy fallback warns on stderr" "legacy" "$warn"

# Not-found
nf_root="$WORK/read-notfound"
mkdir -p "$nf_root"
out=$(python3 "$SCRIPTS/read_bruhs_block.py" --kind state --root "$nf_root" 2>/dev/null)
ec=$?
assert_eq "not-found exits 1" "1" "$ec"
assert_eq "not-found stdout is empty" "" "$out"

# Marker block takes priority over legacy file
prio_root="$WORK/read-priority"
mkdir -p "$prio_root/.claude"
echo '{"bogus": "legacy"}' > "$prio_root/.claude/bruhs.json"
echo "$STATE_JSON" | python3 "$SCRIPTS/sync_bruhs_block.py" --kind state --root "$prio_root" >/dev/null 2>&1
out=$(python3 "$SCRIPTS/read_bruhs_block.py" --kind state --root "$prio_root" 2>/dev/null)
assert_contains "marker block wins over legacy file" "linear-test" "$out"
assert_not_contains "legacy bogus value is ignored" "bogus" "$out"

# Kind isolation: --kind rules from a project that only has state returns exit 1
echo "$STATE_JSON" | python3 "$SCRIPTS/sync_bruhs_block.py" --kind state --root "$fresh" >/dev/null 2>&1
out=$(python3 "$SCRIPTS/read_bruhs_block.py" --kind rules --root "$fresh" 2>/dev/null)
ec=$?
assert_eq "--kind rules exits 1 when only state exists" "1" "$ec"

#─────────────────────────────────────────────────────────────────────────────
heading "derive_stack_rules.py — matched signals only, deterministic, synonyms"
#─────────────────────────────────────────────────────────────────────────────

out=$(echo "$STATE_JSON" | python3 "$SCRIPTS/derive_stack_rules.py" 2>/dev/null)
assert_contains "emits Next.js rules"     "Next.js"      "$out"
assert_contains "emits Convex rules"      "Convex"       "$out"
assert_contains "emits Tailwind rules"    "Tailwind"     "$out"
assert_contains "emits shadcn rules"      "shadcn"       "$out"
assert_contains "emits Better Auth rules" "Better Auth"  "$out"
assert_contains "emits Biome rules"       "Biome"        "$out"
assert_contains "emits Vitest rules"      "Vitest"       "$out"
assert_not_contains "does NOT emit Drizzle heading (not in stack)"  "#### Drizzle" "$out"
assert_not_contains "does NOT emit Prisma heading (not in stack)"   "#### Prisma"  "$out"
# Effect appears in prose ("don't fall back to client useEffect"); check the heading specifically
assert_not_contains "does NOT emit Effect heading (not in stack)"   "#### Effect"  "$out"

# Deterministic — two runs produce identical output
out2=$(echo "$STATE_JSON" | python3 "$SCRIPTS/derive_stack_rules.py" 2>/dev/null)
assert_eq "derive output is deterministic" "$out" "$out2"

# Empty stack produces empty output, exit 0
out=$(echo '{"stack": {}, "tooling": {}}' | python3 "$SCRIPTS/derive_stack_rules.py" 2>/dev/null)
ec=$?
assert_eq "empty stack exits 0" "0" "$ec"
assert_eq "empty stack stdout is empty" "" "$(echo "$out" | tr -d '[:space:]')"

# Invalid JSON exits 2
echo "not json" | python3 "$SCRIPTS/derive_stack_rules.py" >/dev/null 2>&1
ec=$?
assert_eq "invalid JSON exits 2" "2" "$ec"

# Synonym handling: 'Next.js' (canonical) and 'nextjs' should both emit the same group exactly once
synonym_state='{"stack": {"framework": "nextjs", "frameworks": ["Next.js"]}, "tooling": {}}'
out=$(echo "$synonym_state" | python3 "$SCRIPTS/derive_stack_rules.py" 2>/dev/null)
nextjs_count=$(printf '%s' "$out" | grep -c '#### Next.js')
assert_eq "Next.js / nextjs synonym deduped to one group" "1" "$nextjs_count"

motion_state='{"stack": {"animation": ["framer-motion", "motion"]}, "tooling": {}}'
out=$(echo "$motion_state" | python3 "$SCRIPTS/derive_stack_rules.py" 2>/dev/null)
motion_count=$(printf '%s' "$out" | grep -c '#### Motion / Animation')
assert_eq "framer-motion / motion synonym deduped to one group" "1" "$motion_count"
assert_contains "motion rules mention reduced motion" "prefers-reduced-motion" "$out"

#─────────────────────────────────────────────────────────────────────────────
heading "detect_stack.py — Next.js + Tailwind + Drizzle + Convex"
#─────────────────────────────────────────────────────────────────────────────

ds_root="$WORK/detect-stack"
mkdir -p "$ds_root/components/ui"
touch "$ds_root/next.config.ts" "$ds_root/tailwind.config.ts" "$ds_root/drizzle.config.ts" "$ds_root/vitest.config.ts" "$ds_root/biome.json"
touch "$ds_root/components/ui/button.tsx"
cat > "$ds_root/package.json" <<'EOF'
{
  "name": "test-app",
  "dependencies": {
    "next": "16.0.0",
    "react": "19.0.0",
    "tailwindcss": "4.0.0",
    "@ai-sdk/react": "3.0.75",
    "better-auth": "1.0.0",
    "zod": "3.23.0",
    "@tanstack/react-query": "5.0.0",
    "zustand": "5.0.0",
    "framer-motion": "12.0.0",
    "drizzle-orm": "0.30.0"
  }
}
EOF

out=$(python3 "$SCRIPTS/detect_stack.py" "$ds_root" 2>/dev/null)
ec=$?
assert_eq "detect_stack exits 0" "0" "$ec"

# stdout is parseable JSON
assert "detect_stack stdout is JSON" python3 -c "import json,sys; json.loads(sys.argv[1])" "$out"

structure=$(printf '%s' "$out" | python3 -c "import json,sys; print(json.load(sys.stdin).get('structure',''))")
assert_eq "structure=single (no monorepo markers)" "single" "$structure"

# detect_stack emits short canonical forms — agents normalize to display names elsewhere
frameworks=$(printf '%s' "$out" | python3 -c "import json,sys; print(json.dumps(json.load(sys.stdin).get('frameworks', [])))")
assert_contains "frameworks includes 'nextjs' (short canonical form)" "nextjs" "$frameworks"

styling=$(printf '%s' "$out" | python3 -c "import json,sys; print(json.dumps(json.load(sys.stdin).get('styling', [])))")
assert_contains "styling includes 'tailwind' (from tailwindcss dep)" "tailwind" "$styling"
assert_contains "styling includes 'shadcn' (from components/ui marker)" "shadcn" "$styling"

database=$(printf '%s' "$out" | python3 -c "import json,sys; print(json.dumps(json.load(sys.stdin).get('database', [])))")
assert_contains "database includes 'drizzle' (from drizzle-orm dep)" "drizzle" "$database"

animation=$(printf '%s' "$out" | python3 -c "import json,sys; print(json.dumps(json.load(sys.stdin).get('animation', [])))")
assert_contains "animation includes 'framer-motion' (from framer-motion dep)" "framer-motion" "$animation"

# Missing package.json is graceful
np_root="$WORK/detect-stack-nopkg"
mkdir -p "$np_root"
touch "$np_root/next.config.ts"
out=$(python3 "$SCRIPTS/detect_stack.py" "$np_root" 2>/dev/null)
ec=$?
assert_eq "missing package.json still exits 0" "0" "$ec"
assert "missing package.json still emits JSON" python3 -c "import json,sys; json.loads(sys.argv[1])" "$out"

#─────────────────────────────────────────────────────────────────────────────
heading "detect_mcp_servers.py — multi-workspace, missing config, grouping"
#─────────────────────────────────────────────────────────────────────────────

mcp_cfg="$WORK/mcp.json"
cat > "$mcp_cfg" <<'EOF'
{
  "mcpServers": {
    "linear-perdix": {"command": "npx", "args": ["-y", "mcp-server-linear"]},
    "linear-sonner": {"command": "npx", "args": ["-y", "mcp-server-linear"]},
    "notion":        {"command": "npx", "args": ["-y", "mcp-server-notion"]},
    "github":        {"command": "npx", "args": ["-y", "mcp-server-github"]},
    "context7":      {"command": "npx", "args": ["-y", "context7"]},
    "shadcn":        {"command": "npx", "args": ["-y", "shadcn-mcp"]}
  }
}
EOF

out=$(python3 "$SCRIPTS/detect_mcp_servers.py" --config "$mcp_cfg" 2>/dev/null)
ec=$?
assert_eq "detect_mcp_servers exits 0" "0" "$ec"
assert "detect_mcp_servers stdout is JSON" python3 -c "import json,sys; json.loads(sys.argv[1])" "$out"

linear=$(printf '%s' "$out" | python3 -c "import json,sys; print(json.dumps(json.load(sys.stdin).get('linear', [])))")
assert_contains "linear array includes linear-perdix" "linear-perdix" "$linear"
assert_contains "linear array includes linear-sonner" "linear-sonner" "$linear"

other=$(printf '%s' "$out" | python3 -c "import json,sys; print(json.dumps(json.load(sys.stdin).get('other', [])))")
assert_contains "other includes context7" "context7" "$other"
assert_contains "other includes shadcn"   "shadcn"   "$other"

# Missing config — exit 0, empty arrays
out=$(python3 "$SCRIPTS/detect_mcp_servers.py" --config "$WORK/does-not-exist.json" 2>/dev/null)
ec=$?
assert_eq "missing config exits 0" "0" "$ec"

# Determinism — re-read with valid config, twice
out_a=$(python3 "$SCRIPTS/detect_mcp_servers.py" --config "$mcp_cfg" 2>/dev/null)
out_b=$(python3 "$SCRIPTS/detect_mcp_servers.py" --config "$mcp_cfg" 2>/dev/null)
assert_eq "detect_mcp_servers stable across two consecutive calls" "$out_a" "$out_b"

# Other agents' formats: Codex/Grok TOML, Cursor/Gemini JSON, VS Code "servers"
mcp_home="$WORK/mcp-home"; mcp_proj="$WORK/mcp-proj"
mkdir -p "$mcp_home/.codex" "$mcp_home/.grok" "$mcp_proj/.cursor" "$mcp_proj/.vscode" "$mcp_proj/.gemini"
printf '[mcp_servers.linear-bnle]\ncommand = "npx"\n\n[mcp_servers."notion-work".env]\nKEY = "x"\n' > "$mcp_home/.codex/config.toml"
printf '[mcp_servers.github]\nurl = "https://example.invalid"\n' > "$mcp_home/.grok/config.toml"
echo '{"mcpServers": {"linear-perdix": {}}}' > "$mcp_proj/.cursor/mcp.json"
echo '{"servers": {"shadcn": {}}}' > "$mcp_proj/.vscode/mcp.json"
echo '{"mcpServers": {"context7": {}}}' > "$mcp_proj/.gemini/settings.json"
echo '{"mcpServers": {"linear-perdix": {}}}' > "$mcp_proj/.mcp.json"
out=$(HOME="$mcp_home" python3 "$SCRIPTS/detect_mcp_servers.py" --root "$mcp_proj" 2>/dev/null)
ec=$?
assert_eq "default scan exits 0" "0" "$ec"
scan=$(printf '%s' "$out" | python3 -c "import json,sys; d=json.load(sys.stdin); print(' '.join(d['linear']+d['notion']+d['github']+d['other']))")
assert_eq "default scan finds every agent's servers" "linear-bnle linear-perdix notion-work github context7 shadcn" "$scan"
srcs=$(printf '%s' "$out" | python3 -c "import json,sys; print(' '.join(json.load(sys.stdin)['sources']['linear-perdix']))")
assert_contains "sources lists the cursor config" "cursor:" "$srcs"
assert_contains "sources lists the project .mcp.json" "claude-code:" "$srcs"
fallback=$(python3 -B -c "import sys; sys.modules['tomllib']=None; sys.path.insert(0, sys.argv[1]); import detect_mcp_servers as d; print(sorted(d.names_from_toml(open(sys.argv[2]).read())))" "$SCRIPTS" "$mcp_home/.codex/config.toml" 2>&1)
assert_eq "TOML fallback without tomllib finds both tables" "['linear-bnle', 'notion-work']" "$fallback"

# A broken file: explicit --config fails, the default scan skips it
echo '{not json' > "$mcp_proj/.cursor/mcp.json"
HOME="$mcp_home" python3 "$SCRIPTS/detect_mcp_servers.py" --root "$mcp_proj" >/dev/null 2>&1
assert_eq "default scan skips an invalid file" "0" "$?"
python3 "$SCRIPTS/detect_mcp_servers.py" --config "$mcp_proj/.cursor/mcp.json" >/dev/null 2>&1
assert_eq "explicit invalid --config exits 2" "2" "$?"

#─────────────────────────────────────────────────────────────────────────────
heading "validate_pr_ready.sh — node stack, partial failure"
#─────────────────────────────────────────────────────────────────────────────

# Skip if not in a node project root with the deps to actually run typecheck/lint/test.
# Instead, test the script's auto-detect + flag handling at the surface.
val_root="$WORK/val"
mkdir -p "$val_root"
cat > "$val_root/package.json" <<'EOF'
{
  "name": "val-test",
  "scripts": {
    "typecheck": "true",
    "lint":      "false",
    "test":      "true"
  }
}
EOF

(cd "$val_root" && bash "$SCRIPTS/validate_pr_ready.sh") >"$WORK/val.out" 2>"$WORK/val.err"
ec=$?
val_out=$(cat "$WORK/val.out")
assert_eq "validate_pr_ready exits 1 when lint fails" "1" "$ec"
assert_contains "validate_pr_ready labels PASS/FAIL"  "PASS" "$val_out"
assert_contains "validate_pr_ready marks the failed check" "FAIL" "$val_out"
assert_contains "validate_pr_ready ran typecheck"  "typecheck" "$val_out"
assert_contains "validate_pr_ready ran test"       "test"      "$val_out"

# --skip lint passes
(cd "$val_root" && bash "$SCRIPTS/validate_pr_ready.sh" --skip lint) >"$WORK/val2.out" 2>"$WORK/val2.err"
ec=$?
assert_eq "--skip lint exits 0 when other checks pass" "0" "$ec"

# No recognized stack
nostack="$WORK/nostack"
mkdir -p "$nostack"
(cd "$nostack" && bash "$SCRIPTS/validate_pr_ready.sh") >"$WORK/nostack.out" 2>"$WORK/nostack.err"
ec=$?
assert_eq "no stack found exits 2" "2" "$ec"

#─────────────────────────────────────────────────────────────────────────────
heading "write_bruhs_config.py — deprecation shim"
#─────────────────────────────────────────────────────────────────────────────

shim_root="$WORK/shim"
mkdir -p "$shim_root"
out=$(echo "$STATE_JSON" | python3 "$SCRIPTS/write_bruhs_config.py" --root "$shim_root" 2>"$WORK/shim.err")
ec=$?
shim_err=$(cat "$WORK/shim.err")
assert_eq "shim exits 0 on success" "0" "$ec"
assert_contains "shim warns on stderr" "deprecated" "$shim_err"
assert "shim writes CLAUDE.md" test -f "$shim_root/CLAUDE.md"
assert "shim writes AGENTS.md" test -f "$shim_root/AGENTS.md"
assert "shim does NOT write .claude/bruhs.json" sh -c "! test -f '$shim_root/.claude/bruhs.json'"

# Validation still flows through
err=$(echo "not json" | python3 "$SCRIPTS/write_bruhs_config.py" --root "$shim_root" 2>&1 >/dev/null; printf 'ec=%d' "$?")
ec="${err##*ec=}"
assert_eq "shim exits 2 on invalid input" "2" "$ec"

# --dry-run forwarded
shim_dry="$WORK/shim-dry"
mkdir -p "$shim_dry"
out=$(echo "$STATE_JSON" | python3 "$SCRIPTS/write_bruhs_config.py" --root "$shim_dry" --dry-run 2>/dev/null)
assert "shim --dry-run does not write CLAUDE.md" sh -c "! test -f '$shim_dry/CLAUDE.md'"
assert "shim --dry-run does not write AGENTS.md" sh -c "! test -f '$shim_dry/AGENTS.md'"

#─────────────────────────────────────────────────────────────────────────────
heading "walk_video.py — script tripwires, engine choice, captions-only render"
#─────────────────────────────────────────────────────────────────────────────

wv="$WORK/walk-video"
mkdir -p "$wv"
cat > "$wv/script.json" <<'EOF'
{
  "pr": {"number": 42, "title": "feat(api): rate-limit /v1/search per client", "base": "main", "head": "feat/api-rate-limit", "additions": 74, "deletions": 9, "files": 8},
  "scenes": [
    {"kind": "intent", "heading": "Enforce the search quota", "visual": {"type": "title"},
     "narration": "Our docs promise one hundred searches per minute. Nothing enforced it."},
    {"kind": "change", "heading": "A fixed window per client", "visual": {"type": "diff", "path": "src/server.ts",
      "text": "@@ -14,6 +16,9 @@\n+    if (!decision.allowed) {\n+      return send(res, 429, { error: \"rate_limited\" }); // \\n stays literal\n+    }"},
     "narration": "Over the limit, search answers four twenty nine."},
    {"kind": "implications", "heading": "Per process", "visual": {"type": "points", "items": ["3 replicas, so up to 3x the quota"]},
     "narration": "Counters are per process."},
    {"kind": "validation", "heading": "What was checked", "visual": {"type": "claims"},
     "claims": [
       {"text": "Limiter unit tests pass", "status": "shown", "receipt": "npm test: 2 passed | 0 failed"},
       {"text": "The 101st request returns 429", "status": "unchecked"},
       {"text": "Quota holds across replicas", "status": "intended"}],
     "narration": "Unit tests pass. The live endpoint was not checked."}
  ]
}
EOF
# mutate SCRIPT EXPR: copy script.json with a Python expression applied to `s`.
mutate() {
    python3 - "$wv/script.json" "$wv/$1.json" "$2" <<'PY'
import json, sys
s = json.load(open(sys.argv[1]))
exec(sys.argv[3])
json.dump(s, open(sys.argv[2], "w"))
PY
}

out=$(python3 "$SCRIPTS/walk_video.py" check "$wv/script.json" --tts none 2>&1); ec=$?
assert_eq "walk_video check accepts a well-formed script" "0" "$ec"
assert_contains "check reports ok" '"ok": true' "$out"

mutate no-receipt 's["scenes"][3]["claims"][0].pop("receipt")'
out=$(python3 "$SCRIPTS/walk_video.py" check "$wv/no-receipt.json" --tts none 2>&1); ec=$?
assert_eq "a shown claim without a receipt exits 2" "2" "$ec"
assert_contains "the error asks for a receipt or a weaker status" "mark it intended or unchecked" "$out"

mutate bad-status 's["scenes"][3]["claims"][1]["status"] = "verified"'
ec=$(capture_ec python3 "$SCRIPTS/walk_video.py" check "$wv/bad-status.json" --tts none)
assert_eq "an unknown claim status exits 2" "2" "$ec"

mutate no-validation 's["scenes"].pop()'
out=$(python3 "$SCRIPTS/walk_video.py" check "$wv/no-validation.json" --tts none 2>&1); ec=$?
assert_eq "a script without a validation scene exits 2" "2" "$ec"
assert_contains "the error names the missing validation scene" "last scene must be a validation scene" "$out"

mutate out-of-order 's["scenes"].insert(2, dict(s["scenes"][0]))'
out=$(python3 "$SCRIPTS/walk_video.py" check "$wv/out-of-order.json" --tts none 2>&1); ec=$?
assert_eq "an intent scene after a change scene exits 2" "2" "$ec"
assert_contains "the error states the scene order" "intent → change → implications → validation" "$out"

mutate long-code 's["scenes"][1]["visual"]["text"] = "\n".join(["x"] * 40)'
out=$(python3 "$SCRIPTS/walk_video.py" check "$wv/long-code.json" --tts none 2>&1); ec=$?
assert_eq "a diff taller than the slide exits 2" "2" "$ec"
assert_contains "the error says how many lines fit" "the slide holds" "$out"

mutate missing-image 's["scenes"][1]["visual"] = {"type": "image", "src": "nope.png"}'
out=$(python3 "$SCRIPTS/walk_video.py" check "$wv/missing-image.json" --tts none 2>&1); ec=$?
assert_eq "a missing image exits 2" "2" "$ec"
assert_contains "the error names the missing file" "nope.png" "$out"

mutate backticks 's["scenes"][1]["narration"] = "It calls `checkSearchLimit` first."'
out=$(python3 "$SCRIPTS/walk_video.py" check "$wv/backticks.json" --tts none 2>&1); ec=$?
assert_eq "backticks in narration warn but pass" "0" "$ec"
assert_contains "the warning explains backticks are read aloud" "backticks" "$out"

# No piper binary and no voice: asking for piper by name fails loudly; auto falls back.
nopiper_path="$(dirname "$(command -v python3)"):/usr/bin:/bin"
out=$(env PATH="$nopiper_path" XDG_DATA_HOME="$wv/empty" BRUHS_PIPER_VOICE= python3 "$SCRIPTS/walk_video.py" check "$wv/script.json" --tts piper 2>&1); ec=$?
assert_eq "--tts piper without piper exits 3" "3" "$ec"
assert_contains "the error says how to get piper" "uv tool install piper-tts" "$out"
out=$(env PATH="$nopiper_path" XDG_DATA_HOME="$wv/empty" BRUHS_PIPER_VOICE= python3 "$SCRIPTS/walk_video.py" engines 2>&1)
assert_contains "engines reports the auto choice" '"auto":' "$out"
assert "engines prints valid JSON" python3 -c "import json,sys; json.loads(sys.argv[1])" "$out"

if command -v ffmpeg >/dev/null 2>&1 && ffmpeg -hide_banner -filters 2>/dev/null | grep -qE '^ *\S+ +ass '; then
    out=$(python3 "$SCRIPTS/walk_video.py" render "$wv/script.json" --tts none --out "$wv/out" 2>"$wv/render.err"); ec=$?
    assert_eq "captions-only render exits 0" "0" "$ec"
    [ "$ec" -ne 0 ] && sed 's/^/      /' "$wv/render.err" | tail -5
    assert "render writes walkthrough.mp4" test -s "$wv/out/walkthrough.mp4"
    assert "render writes captions.srt" test -s "$wv/out/captions.srt"
    assert "render removes its work directory" sh -c "! test -d '$wv/out/work'"
    streams=$(ffprobe -v error -show_entries stream=codec_type,width,height -of csv=p=0 "$wv/out/walkthrough.mp4" 2>/dev/null | sort | tr '\n' ' ')
    assert_eq "the video is 1080p with an audio track" "audio video,1920,1080 " "$streams"
    assert "video length matches the manifest within 0.2s" python3 - "$wv/out/walkthrough.mp4" "$wv/out/manifest.json" <<'PY'
import json, subprocess, sys
probed = float(subprocess.check_output(["ffprobe", "-v", "error", "-show_entries", "format=duration", "-of", "csv=p=0", sys.argv[1]]))
assert abs(probed - json.load(open(sys.argv[2]))["seconds"]) < 0.2, probed
PY
    transcript=$(cat "$wv/out/transcript.md")
    assert_contains "transcript keeps the receipt (pipes escaped)" 'npm test: 2 passed \| 0 failed' "$transcript"
    assert_contains "transcript labels unchecked claims" "| Not checked |" "$transcript"
    assert_contains "transcript says the narration engine" "none (captions only)" "$transcript"
else
    printf '  [SKIP] walk_video render (ffmpeg with libass not on PATH)\n'
fi

mutate fill-not-bool 's["scenes"][1]["visual"] = {"type": "image", "src": "script.json", "fill": "yes"}'
out=$(python3 "$SCRIPTS/walk_video.py" check "$wv/fill-not-bool.json" --tts none 2>&1); ec=$?
assert_eq "a non-boolean fill exits 2" "2" "$ec"
assert_contains "the error names fill" 'must be true or false' "$out"

#─────────────────────────────────────────────────────────────────────────────
heading "record_demo.mjs — shot-list tripwires, resolution, desktop + touch recordings"
#─────────────────────────────────────────────────────────────────────────────

if ! command -v node >/dev/null 2>&1; then
    printf '  [SKIP] record_demo (node not on PATH)\n'
else
rd="$WORK/record-demo"
mkdir -p "$rd"
app_url="file://$TESTS/fixtures/demo-app/index.html"
cat > "$rd/shots.json" <<EOF
{
  "url": "$app_url",
  "redact": ["[data-sensitive]"],
  "steps": [
    {"mark": "save"},
    {"type": {"label": "Requests per minute"}, "text": "250", "clear": true},
    {"click": {"role": "button", "name": "Save limit"}},
    {"waitFor": {"text": "Saved: 250"}},
    {"zoom": "#status", "hold": 600},
    {"press": "Meta+K", "pause": 300}
  ]
}
EOF
# shots_mutate NAME EXPR: copy shots.json with a Python expression applied to `s`.
shots_mutate() {
    python3 - "$rd/shots.json" "$rd/$1.json" "$2" <<'PY'
import json, sys
s = json.load(open(sys.argv[1]))
exec(sys.argv[3])
json.dump(s, open(sys.argv[2], "w"))
PY
}

out=$(node "$SCRIPTS/record_demo.mjs" check "$rd/shots.json" 2>&1); ec=$?
assert_eq "record_demo check accepts a well-formed shot list" "0" "$ec"
assert_contains "check reports the device-pixel capture size" '"pixels": "2560x1440"' "$out"

shots_mutate two-actions 's["steps"][1]["click"] = "#save"'
out=$(node "$SCRIPTS/record_demo.mjs" check "$rd/two-actions.json" 2>&1); ec=$?
assert_eq "a step with two actions exits 2" "2" "$ec"
assert_contains "the error asks for exactly one action" "needs exactly one action" "$out"

shots_mutate bad-target 's["steps"][2]["click"] = {"role": "button", "label": "Save"}'
out=$(node "$SCRIPTS/record_demo.mjs" check "$rd/bad-target.json" 2>&1); ec=$?
assert_eq "a target with two kinds exits 2" "2" "$ec"
assert_contains "the error lists the target kinds" "needs exactly one of role" "$out"

shots_mutate relative-url 's["url"] = "/settings"'
ec=$(capture_ec node "$SCRIPTS/record_demo.mjs" check "$rd/relative-url.json")
assert_eq "a relative start url exits 2" "2" "$ec"

shots_mutate odd-size 's["output"] = {"size": "1921x1080"}'
out=$(node "$SCRIPTS/record_demo.mjs" check "$rd/odd-size.json" 2>&1); ec=$?
assert_eq "an odd output size exits 2" "2" "$ec"
assert_contains "the error explains even sizes" "even numbers" "$out"

shots_mutate nothing-visible 's["steps"] = [{"wait": 500}]'
ec=$(capture_ec node "$SCRIPTS/record_demo.mjs" check "$rd/nothing-visible.json")
assert_eq "a shot list with no visible step exits 2" "2" "$ec"

shots_mutate deep-zoom 's["steps"][4]["scale"] = 3'
out=$(node "$SCRIPTS/record_demo.mjs" check "$rd/deep-zoom.json" 2>&1); ec=$?
assert_eq "a zoom deeper than the capture supports warns but passes" "0" "$ec"
assert_contains "the warning names the scale that keeps it sharp" 'zoomed detail blurs' "$out"

shots_mutate low-scale 's["scale"] = 1'
out=$(node "$SCRIPTS/record_demo.mjs" check "$rd/low-scale.json" 2>&1)
assert_contains "an upscaled capture warns that it will look soft" "it will look soft" "$out"

can_record=0
if command -v ffmpeg >/dev/null 2>&1 && node -e "require('playwright').chromium.launch().then(b => b.close()).catch(() => process.exit(1))" >/dev/null 2>&1; then
    can_record=1
fi
if [ "$can_record" -eq 1 ]; then
    node "$SCRIPTS/record_demo.mjs" record "$rd/shots.json" --out "$rd/out" >/dev/null 2>"$rd/record.err"; ec=$?
    assert_eq "desktop record exits 0" "0" "$ec"
    [ "$ec" -ne 0 ] && sed 's/^/      /' "$rd/record.err" | tail -8
    assert "record writes demo.mp4" test -s "$rd/out/demo.mp4"
    assert "record writes poster.png" test -s "$rd/out/poster.png"
    assert "record removes its work directory" sh -c "! test -d '$rd/out/work'"
    vstream=$(ffprobe -v error -select_streams v:0 -show_entries stream=width,height,r_frame_rate -of csv=p=0 "$rd/out/demo.mp4" 2>/dev/null)
    assert_eq "desktop video is 1920x1080 at 60 fps" "1920,1080,60/1" "$vstream"
    assert "manifest: device pixels, cursor moves, clicks, a key chip, a zoom, the chapter" python3 - "$rd/out/manifest.json" "$rd/out/demo.mp4" <<'PY'
import json, subprocess, sys
m = json.load(open(sys.argv[1]))
assert m["capture"]["pixels"] == {"width": 2560, "height": 1440}, m["capture"]
i = m["interactions"]
assert i["cursor_moves"] >= 2 and i["clicks"] >= 2 and i["keys"] == 1 and i["touches"] == 0, i
assert m["zooms"] and max(z["z"] for z in m["zooms"]) >= 1.15, m["zooms"]
assert m["chapters"] and m["chapters"][0]["label"] == "save", m["chapters"]
probed = float(subprocess.check_output(["ffprobe", "-v", "error", "-show_entries", "format=duration", "-of", "csv=p=0", sys.argv[2]]))
assert abs(probed - m["seconds"]) < 0.2, (probed, m["seconds"])
PY

    printf '{"url": "%s", "device": "mobile", "steps": [{"tap": {"role": "button", "name": "Save limit"}}, {"scroll": 400}]}\n' "$app_url" > "$rd/mobile.json"
    node "$SCRIPTS/record_demo.mjs" record "$rd/mobile.json" --out "$rd/mobile" >/dev/null 2>"$rd/mobile.err"; ec=$?
    assert_eq "mobile record exits 0" "0" "$ec"
    [ "$ec" -ne 0 ] && sed 's/^/      /' "$rd/mobile.err" | tail -8
    vstream=$(ffprobe -v error -select_streams v:0 -show_entries stream=width,height -of csv=p=0 "$rd/mobile/demo.mp4" 2>/dev/null)
    assert_eq "a phone recording defaults to 1080x1920 portrait" "1080,1920" "$vstream"
    assert "a touch device shows touches, never a cursor, at 3x pixels" python3 - "$rd/mobile/manifest.json" <<'PY'
import json, sys
m = json.load(open(sys.argv[1]))
assert m["capture"]["touch"] and m["capture"]["scale"] == 3, m["capture"]
i = m["interactions"]
assert i["touches"] >= 2 and i["cursor_moves"] == 0 and i["clicks"] == 0, i
PY

    shots_mutate missing-target 's["steps"] = [{"click": {"role": "button", "name": "Nope"}, "timeout": 1000}]'
    out=$(node "$SCRIPTS/record_demo.mjs" record "$rd/missing-target.json" --out "$rd/fail" 2>&1); ec=$?
    assert_eq "a step whose target never appears exits 4" "4" "$ec"
    assert_contains "the error names the failed step" 'step 1 (click role=button[name="Nope"])' "$out"
    assert_contains "the error shows what the page has instead" 'button "Save limit"' "$out"
    assert "the failure leaves a screenshot" test -s "$rd/fail/failed-step-1.png"
    printf '%s' "$out" > "$rd/fail.out"
    assert "redacted text stays out of the failure snapshot" sh -c "! grep -q sk_live '$rd/fail.out'"
    assert "a failed record removes its work directory" sh -c "! test -d '$rd/fail/work'"
else
    printf '  [SKIP] record_demo record (playwright with chromium, or ffmpeg, not available)\n'
fi
fi

#─────────────────────────────────────────────────────────────────────────────
heading "export_evals_json.py"
#─────────────────────────────────────────────────────────────────────────────

case_count=$(find "$PLUGIN_DIR/evals" -mindepth 2 -maxdepth 2 \( -name prompt.md -o -name case.yaml \) -exec dirname {} \; | sort -u | wc -l | tr -d ' ')
assert "every eval case passes --check" python3 "$TESTS/export_evals_json.py" --check
out=$(python3 "$TESTS/export_evals_json.py" 2>/dev/null)
# The export is larger than one argv string may be (128 KiB on Linux): read it from a file.
printf '%s' "$out" > "$WORK/evals-export.json"
assert "export prints valid JSON" python3 -c "import json,sys; json.load(open(sys.argv[1]))" "$WORK/evals-export.json"
exported=$(python3 -c "import json,sys; d=json.load(open(sys.argv[1])); print(len(d['evals']))" "$WORK/evals-export.json" 2>/dev/null)
assert_eq "export holds one entry per case folder" "$case_count" "$exported"
assert "every exported case has a prompt and assertions" python3 -c "import json,sys; d=json.load(open(sys.argv[1])); assert all(e['prompt'] and e['assertions'] for e in d['evals'])" "$WORK/evals-export.json"

bad_evals="$WORK/bad-evals"
mkdir -p "$bad_evals/broken-case/graders"
printf -- '---\nmax_turns: 5\nbogus_key: 1\n---\n\nhello\n' > "$bad_evals/broken-case/prompt.md"
python3 "$TESTS/export_evals_json.py" --evals-dir "$bad_evals" --check >/dev/null 2>&1
assert_eq "--check exits 1 on an unknown frontmatter key and no grader" "1" "$?"

#─────────────────────────────────────────────────────────────────────────────
heading "eval scaffolds — every case builds its workspace offline, under 120s"
#─────────────────────────────────────────────────────────────────────────────

assert "Linear mocks match each scaffold's mcpServer" python3 "$TESTS/sync_eval_mocks.py" --check
for scaffold in "$PLUGIN_DIR"/evals/*/scaffold.sh; do
    case_name="$(basename "$(dirname "$scaffold")")"
    run_home="$WORK/scaffold-$case_name"
    mkdir -p "$run_home/cwd"
    start=$(date +%s)
    # The same bare environment claude plugin eval gives a scaffold: PATH, HOME, TMPDIR.
    (cd "$run_home/cwd" && env -i PATH="$PATH" HOME="$run_home" TMPDIR="${TMPDIR:-/tmp}" TERM=dumb \
        bash "$scaffold" >"$run_home/out.log" 2>&1)
    ec=$?
    elapsed=$(( $(date +%s) - start ))
    assert_eq "$case_name: scaffold exits 0" "0" "$ec"
    [ "$ec" -ne 0 ] && sed 's/^/      /' "$run_home/out.log" | tail -5
    assert "$case_name: scaffold leaves a git repo" test -d "$run_home/cwd/.git"
    assert "$case_name: scaffold finishes under 120s (took ${elapsed}s)" test "$elapsed" -lt 120
done

#─────────────────────────────────────────────────────────────────────────────
heading "Summary"
#─────────────────────────────────────────────────────────────────────────────
printf '\n  PASS: %d\n  FAIL: %d\n  Total: %d\n' "$pass" "$fail" "$((pass + fail))"

if [ "$fail" -gt 0 ]; then
    printf '\nFailed assertions:\n'
    for f in "${fails[@]}"; do printf '  - %s\n' "$f"; done
    exit 1
fi
exit 0
