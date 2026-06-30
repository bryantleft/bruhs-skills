# bruhs utility scripts

Self-contained helper scripts invoked by the bruhs plugin commands
(`claim`, `spawn`, `cook`, `yeet`, `peep`, `slop`, `doodle`). Stdlib /
POSIX-bash only — no installs required. All scripts are non-destructive:
they only read project files or write to known paths (`CLAUDE.md`,
`AGENTS.md`, or legacy `.claude/bruhs.json`).

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
`auth`, `testing`, `tooling`, `animation`, `libraries`, `confidence`.

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

### `sync_bruhs_block.py`

Atomically write a marker-bounded block (`bruhs:state` or `bruhs:rules`)
into `CLAUDE.md` and `AGENTS.md`. Replaces the older flow that wrote
`.claude/bruhs.json`. Used by `claim`, `spawn`, and `cook` (for skill
persistence).

Invocation:

    # State block (validated JSON)
    cat state.json | python3 <PLUGIN_DIR>/scripts/sync_bruhs_block.py --kind state --root <PROJECT_ROOT>

    # Rules block (pre-rendered markdown — usually piped from derive_stack_rules.py)
    cat rules.md  | python3 <PLUGIN_DIR>/scripts/sync_bruhs_block.py --kind rules --root <PROJECT_ROOT>

    # Flags
    --files CLAUDE.md,AGENTS.md   files to sync (default: both)
    --dry-run                      print would-be writes; touch nothing

For `--kind state`, validates: top-level object, required `stack` and
`tooling` objects, and (when present) `integrations.linear.mcpServer` +
`.team` as non-empty strings. Writes via `<file>.tmp` + `os.replace()`;
creates the target files with a minimal header if missing. Content
outside the markers is never touched.

Exit codes: `0` success, `2` usage / validation error, `3` filesystem
error.

### `read_bruhs_block.py`

Read a marker block back out and print its body to stdout. Used by
`cook`, `yeet`, `slop`, `doodle`.

Invocation:

    python3 <PLUGIN_DIR>/scripts/read_bruhs_block.py --kind state --root <PROJECT_ROOT>
    python3 <PLUGIN_DIR>/scripts/read_bruhs_block.py --kind rules --root <PROJECT_ROOT>

For `--kind state`, the JSON inside the ` ```json ` fence is printed
(suitable for piping into `jq` or `JSON.parse`). For `--kind rules`,
the markdown body is printed.

Read order: `CLAUDE.md`, then `AGENTS.md`. For `--kind state`, falls
back to legacy `.claude/bruhs.json` if neither file contains a block —
eases the transition for un-migrated projects.

Exit codes: `0` found, `1` no block found (and no legacy file for
`--kind state`), `2` usage error.

### `derive_stack_rules.py`

Read state JSON on stdin, emit stack-specific behavioral rules as
markdown on stdout. Pipe the output into
`sync_bruhs_block.py --kind rules`.

Invocation:

    cat state.json | python3 <PLUGIN_DIR>/scripts/derive_stack_rules.py
    cat state.json | python3 <PLUGIN_DIR>/scripts/derive_stack_rules.py --json   # debug

The rules are short, high-signal, and **only** stack-derived. Universal
behavioral rules should be hand-written by the user, outside the bruhs
blocks (the rules tuned to *their* failure modes).

Exit codes: `0` always (empty output when nothing matches), `2` invalid
JSON on stdin.

### `write_bruhs_config.py` (deprecated)

Thin shim that forwards stdin JSON to `sync_bruhs_block.py --kind state`
and prints a deprecation warning to stderr. Kept around for one release
so external callers don't break. Migrate to `sync_bruhs_block.py`
directly.

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
