#!/usr/bin/env bash
# run_script_tests.sh — executable test harness for the 7 script-level evals.
#
# The JSON eval files in this directory are specs (prose). This script runs
# concrete assertions that exercise the same behaviors. One PASS/FAIL line per
# assertion; non-zero exit if anything fails.
#
# Usage:
#     bash evals/run_script_tests.sh
#
# Covers (script-level evals → assertion groups):
#     sync_bruhs_block.py     → sync-bruhs-block-preserves-hand-written.json
#     read_bruhs_block.py     → read-bruhs-block-legacy-fallback.json,
#                                read-bruhs-block-not-found.json
#     derive_stack_rules.py   → derive-stack-rules-coverage.json
#     detect_stack.py         → detect-stack-nextjs.json
#     detect_mcp_servers.py   → detect-mcp-servers-multi-workspace.json
#     validate_pr_ready.sh    → validate-pr-ready-node.json
#     write_bruhs_config.py   → write-bruhs-config-shim.json
#
# All work is done in $TMPDIR/bruhs-eval-<pid>; cleaned up on exit.

set -u

PLUGIN_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
SCRIPTS="$PLUGIN_DIR/scripts"
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
heading "Summary"
#─────────────────────────────────────────────────────────────────────────────
printf '\n  PASS: %d\n  FAIL: %d\n  Total: %d\n' "$pass" "$fail" "$((pass + fail))"

if [ "$fail" -gt 0 ]; then
    printf '\nFailed assertions:\n'
    for f in "${fails[@]}"; do printf '  - %s\n' "$f"; done
    exit 1
fi
exit 0
