#!/usr/bin/env bash
# validate_pr_ready.sh — Run the project's standard "ready to merge" checks.
#
# Usage:
#   validate_pr_ready.sh [--stack node|rust|python|go] [--skip tests|lint|typecheck] ...
#   validate_pr_ready.sh --help
#
# Auto-detects the project stack from markers in the current directory
# (package.json, Cargo.toml, pyproject.toml, go.mod) and runs the
# standard typecheck + lint + test commands for each detected stack.
#
#   Node   : npm run typecheck / lint / test when defined, else npx tsc
#            --noEmit, npx biome check . or npx eslint ., and npx vitest
#            run or npx jest.
#   Rust   : cargo check --all-targets, cargo clippy --all-targets
#            -- -D warnings, cargo test.
#   Python : (uv run) ruff check ., (uv run) mypy ., (uv run) pytest.
#   Go     : go vet ./..., go build ./..., go test ./...
#
# Each command prints a tick (success) or cross (failure) with the first
# 20 lines of output on failure. The script exits 0 only if every check
# that ran passed, and nonzero otherwise.
#
# Flags:
#   --stack <node|rust|python|go>   Force a single stack, skip detection.
#   --skip  <tests|lint|typecheck>  Skip a category (repeatable).
#   --help                          Show this help and exit.
#
# Portable across macOS and Linux. POSIX bash + common CLIs only.

set -u

PROG="validate_pr_ready.sh"
STACK_FORCE=""
SKIP_TESTS=0
SKIP_LINT=0
SKIP_TYPECHECK=0
FAILED=0
RAN_ANY=0

usage() {
  sed -n '2,34p' "$0" | sed 's/^# \{0,1\}//'
}

die() {
  printf 'error: %s\n' "$1" >&2
  exit 2
}

while [ $# -gt 0 ]; do
  case "$1" in
    --help|-h)
      usage
      exit 0
      ;;
    --stack)
      [ $# -ge 2 ] || die "--stack requires an argument"
      STACK_FORCE="$2"
      shift 2
      ;;
    --stack=*)
      STACK_FORCE="${1#--stack=}"
      shift
      ;;
    --skip)
      [ $# -ge 2 ] || die "--skip requires an argument"
      case "$2" in
        tests) SKIP_TESTS=1 ;;
        lint) SKIP_LINT=1 ;;
        typecheck) SKIP_TYPECHECK=1 ;;
        *) die "unknown --skip value: $2 (want tests|lint|typecheck)" ;;
      esac
      shift 2
      ;;
    --skip=*)
      val="${1#--skip=}"
      case "$val" in
        tests) SKIP_TESTS=1 ;;
        lint) SKIP_LINT=1 ;;
        typecheck) SKIP_TYPECHECK=1 ;;
        *) die "unknown --skip value: $val (want tests|lint|typecheck)" ;;
      esac
      shift
      ;;
    *)
      die "unknown argument: $1 (try --help)"
      ;;
  esac
done

case "$STACK_FORCE" in
  ""|node|rust|python|go) ;;
  *) die "unknown --stack value: $STACK_FORCE (want node|rust|python|go)" ;;
esac

# has_cmd <name> — returns 0 if the command is on PATH.
has_cmd() {
  command -v "$1" >/dev/null 2>&1
}

# run_check <label> <cmd...>  — run a command, print tick/cross, collect failures.
run_check() {
  local label="$1"
  shift
  RAN_ANY=1
  local tmp
  tmp="$(mktemp 2>/dev/null || mktemp -t validate_pr_ready)"
  if "$@" >"$tmp" 2>&1; then
    printf '[PASS] %s\n' "$label"
  else
    local code=$?
    printf '[FAIL] %s (exit %d)\n' "$label" "$code"
    printf '       --- first 20 lines of output ---\n'
    sed -n '1,20p' "$tmp" | sed 's/^/       /'
    FAILED=1
  fi
  rm -f "$tmp"
}

# pkg_has_script <script-name>  — 0 if package.json defines that npm script.
pkg_has_script() {
  [ -f package.json ] || return 1
  if has_cmd jq; then
    jq -e --arg name "$1" '.scripts[$name] // empty' package.json >/dev/null 2>&1
  else
    # Fallback: crude grep. Works for typical "name": "value" script entries.
    grep -Eq "\"$1\"[[:space:]]*:" package.json
  fi
}

run_node() {
  if [ "$SKIP_TYPECHECK" -eq 0 ]; then
    if pkg_has_script typecheck; then
      run_check "node: npm run typecheck" npm run --silent typecheck
    elif [ -f tsconfig.json ] && has_cmd npx; then
      run_check "node: npx tsc --noEmit" npx --yes tsc --noEmit
    fi
  fi
  if [ "$SKIP_LINT" -eq 0 ]; then
    if pkg_has_script lint; then
      run_check "node: npm run lint" npm run --silent lint
    elif has_cmd npx; then
      if [ -f biome.json ] || [ -f biome.jsonc ]; then
        run_check "node: npx biome check ." npx --yes @biomejs/biome check .
      else
        run_check "node: npx eslint ." npx --yes eslint .
      fi
    fi
  fi
  if [ "$SKIP_TESTS" -eq 0 ]; then
    if pkg_has_script test; then
      run_check "node: npm test" npm test --silent
    elif has_cmd npx; then
      if grep -q '"vitest"' package.json 2>/dev/null; then
        run_check "node: npx vitest run" npx --yes vitest run
      elif grep -q '"jest"' package.json 2>/dev/null; then
        run_check "node: npx jest" npx --yes jest
      fi
    fi
  fi
}

run_rust() {
  has_cmd cargo || {
    printf '[SKIP] rust: cargo not on PATH\n' >&2
    return
  }
  if [ "$SKIP_TYPECHECK" -eq 0 ]; then
    run_check "rust: cargo check --all-targets" cargo check --all-targets
  fi
  if [ "$SKIP_LINT" -eq 0 ]; then
    run_check "rust: cargo clippy --all-targets -- -D warnings" \
      cargo clippy --all-targets -- -D warnings
  fi
  if [ "$SKIP_TESTS" -eq 0 ]; then
    run_check "rust: cargo test" cargo test
  fi
}

run_python() {
  local runner=""
  if has_cmd uv; then
    runner="uv run"
  fi
  if [ "$SKIP_LINT" -eq 0 ]; then
    if [ -n "$runner" ]; then
      run_check "python: uv run ruff check ." uv run ruff check .
    elif has_cmd ruff; then
      run_check "python: ruff check ." ruff check .
    fi
  fi
  if [ "$SKIP_TYPECHECK" -eq 0 ]; then
    if [ -n "$runner" ]; then
      run_check "python: uv run mypy ." uv run mypy .
    elif has_cmd mypy; then
      run_check "python: mypy ." mypy .
    fi
  fi
  if [ "$SKIP_TESTS" -eq 0 ]; then
    if [ -n "$runner" ]; then
      run_check "python: uv run pytest" uv run pytest
    elif has_cmd pytest; then
      run_check "python: pytest" pytest
    fi
  fi
}

run_go() {
  has_cmd go || {
    printf '[SKIP] go: go not on PATH\n' >&2
    return
  }
  if [ "$SKIP_LINT" -eq 0 ]; then
    run_check "go: go vet ./..." go vet ./...
  fi
  if [ "$SKIP_TYPECHECK" -eq 0 ]; then
    run_check "go: go build ./..." go build ./...
  fi
  if [ "$SKIP_TESTS" -eq 0 ]; then
    run_check "go: go test ./..." go test ./...
  fi
}

detect_and_run() {
  if [ -n "$STACK_FORCE" ]; then
    case "$STACK_FORCE" in
      node) run_node ;;
      rust) run_rust ;;
      python) run_python ;;
      go) run_go ;;
    esac
    return
  fi
  [ -f package.json ] && run_node
  [ -f Cargo.toml ] && run_rust
  [ -f pyproject.toml ] && run_python
  [ -f go.mod ] && run_go
}

detect_and_run

if [ "$RAN_ANY" -eq 0 ]; then
  printf 'error: no recognized project markers found (try --stack)\n' >&2
  exit 2
fi

if [ "$FAILED" -ne 0 ]; then
  printf '\nvalidate_pr_ready: FAILED\n' >&2
  exit 1
fi

printf '\nvalidate_pr_ready: OK\n'
exit 0
