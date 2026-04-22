# bruhs utility scripts

Self-contained helper scripts invoked by the bruhs plugin commands
(`claim`, `spawn`, `cook`, `yeet`, `peep`). Stdlib / POSIX-bash only —
no installs required. All scripts are non-destructive: they only read
project files or write to known paths under `.claude/`.

## Platform support

Tested on macOS and Linux. No GNU-only or BSD-only flags; Python
scripts use `python3` (3.8+), the shell script uses portable `bash`
with a `mktemp` fallback.

## Scripts

### `detect_stack.py`

Detect a project's tech stack from config files (package.json,
tsconfig.json, Cargo.toml, pyproject.toml, go.mod, Rojo, etc.). Used by
`claim` and `spawn`.

Invocation from bruhs commands:

    python3 <PLUGIN_DIR>/scripts/detect_stack.py <PROJECT_ROOT>

Output: pretty-printed JSON to stdout with keys `root`, `structure`,
`monorepo_tool`, `languages`, `frameworks`, `styling`, `database`,
`auth`, `testing`, `tooling`, `libraries`, `confidence`.

Exit codes: `0` on success, `2` on usage error.

### `detect_mcp_servers.py`

List installed MCP servers from `~/.claude.json`, grouped into
`linear`, `notion`, `github`, and `other`. Used by `claim`.

Invocation:

    python3 <PLUGIN_DIR>/scripts/detect_mcp_servers.py
    python3 <PLUGIN_DIR>/scripts/detect_mcp_servers.py --config <PATH>

Output: JSON object with four array-valued keys. Missing config file is
treated as empty (exit 0).

Exit codes: `0` on success or missing file, `2` on invalid JSON / IO
error.

### `write_bruhs_config.py`

Validate a JSON config on stdin and atomically write it to
`<root>/.claude/bruhs.json`. Used by `claim` and `spawn`.

Invocation:

    cat config.json | python3 <PLUGIN_DIR>/scripts/write_bruhs_config.py --root <PROJECT_ROOT>
    cat config.json | python3 <PLUGIN_DIR>/scripts/write_bruhs_config.py --dry-run

Validates: top-level object, required `stack` and `tooling` objects,
and (when present) `integrations.linear.mcpServer` + `.team` as
non-empty strings. Writes via `<file>.tmp` + `os.replace()`; creates
`.claude/` if missing. Prints the final file path to stdout on
success.

Exit codes: `0` success, `2` usage / validation error, `3`
filesystem error.

### `validate_pr_ready.sh`

Run the project's standard "ready to merge" checks (typecheck + lint +
tests) for every detected stack. Used by `yeet`, `peep`, and `cook`.

Invocation:

    bash <PLUGIN_DIR>/scripts/validate_pr_ready.sh
    bash <PLUGIN_DIR>/scripts/validate_pr_ready.sh --stack node
    bash <PLUGIN_DIR>/scripts/validate_pr_ready.sh --skip tests

Auto-detects stacks from `package.json`, `Cargo.toml`, `pyproject.toml`,
`go.mod` in the current directory. Each check prints `[PASS] <label>`
or `[FAIL] <label>` (with the first 20 lines of output). The script is
executable (`chmod +x`).

Exit codes: `0` every check passed, `1` at least one check failed,
`2` usage error or no recognized stack found.

## Notes

- JSON output is pretty-printed so callers can pipe through `jq` or
  re-parse without guesswork.
- Errors always go to stderr; success payloads always go to stdout.
- No script deletes files or runs destructive git commands.
