# bruhs utility scripts

Self-contained helper scripts invoked by the bruhs plugin commands
(`claim`, `spawn`, `cook`, `yeet`, `peep`, `slop`, `doodle`, `walk`). Stdlib /
POSIX-bash only — no installs required, except `walk_video.py`, which shells
out to ffmpeg and a local text-to-speech engine, and `record_demo.mjs`, which
needs Node 18+, Playwright with Chromium, and ffmpeg. All scripts are non-destructive:
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

    python3 <SKILL_DIR>/scripts/detect_stack.py <PROJECT_ROOT>

Output: pretty-printed JSON to stdout with keys `root`, `structure`,
`monorepo_tool`, `languages`, `frameworks`, `styling`, `database`,
`auth`, `testing`, `tooling`, `animation`, `libraries`, `confidence`.

Exit codes: `0` on success, `2` on usage error.

### `detect_mcp_servers.py`

List installed MCP servers, grouped into `linear`, `notion`, `github`,
and `other`, from every agent's MCP config: Claude Code, Codex, Grok
CLI, Cursor, Gemini CLI, VS Code and Windsurf, at user level and for
the project at `--root`. Used by `claim` and `spawn`.

Invocation:

    python3 <SKILL_DIR>/scripts/detect_mcp_servers.py --root <PROJECT_ROOT>
    python3 <SKILL_DIR>/scripts/detect_mcp_servers.py --config <PATH> [--config <PATH>]

Output: JSON object with the four array-valued keys plus `sources`,
mapping each server name to the configs it was found in. Missing files
are skipped. In the default scan an invalid file is reported on stderr
and skipped; TOML is parsed with `tomllib` on Python 3.11+ and with a
table-header scan before that.

Exit codes: `0` on success, `2` when a file named with `--config` is
invalid JSON/TOML or unreadable.

### `sync_bruhs_block.py`

Atomically write a marker-bounded block (`bruhs:state` or `bruhs:rules`)
into `CLAUDE.md` and `AGENTS.md`. Replaces the older flow that wrote
`.claude/bruhs.json`. Used by `claim`, `spawn`, and `cook` (for skill
persistence).

Invocation:

    # State block (validated JSON)
    cat state.json | python3 <SKILL_DIR>/scripts/sync_bruhs_block.py --kind state --root <PROJECT_ROOT>

    # Rules block (pre-rendered markdown — usually piped from derive_stack_rules.py)
    cat rules.md  | python3 <SKILL_DIR>/scripts/sync_bruhs_block.py --kind rules --root <PROJECT_ROOT>

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

    python3 <SKILL_DIR>/scripts/read_bruhs_block.py --kind state --root <PROJECT_ROOT>
    python3 <SKILL_DIR>/scripts/read_bruhs_block.py --kind rules --root <PROJECT_ROOT>

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

    cat state.json | python3 <SKILL_DIR>/scripts/derive_stack_rules.py
    cat state.json | python3 <SKILL_DIR>/scripts/derive_stack_rules.py --json   # debug

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

    bash <SKILL_DIR>/scripts/validate_pr_ready.sh
    bash <SKILL_DIR>/scripts/validate_pr_ready.sh --stack node
    bash <SKILL_DIR>/scripts/validate_pr_ready.sh --skip tests

Auto-detects stacks from `package.json`, `Cargo.toml`, `pyproject.toml`,
`go.mod` in the current directory. Each check prints `[PASS] <label>`
or `[FAIL] <label>` (with the first 20 lines of output). The script is
executable (`chmod +x`).

Exit codes: `0` every check passed, `1` at least one check failed,
`2` usage error or no recognized stack found.

### `walk_video.py`

Check a walkthrough scene script and render it to a narrated, captioned
1920x1080 MP4. Used by `walk --video`; the scene schema and narration rules
live in `commands/walk.md` → *Video Mode*.

Invocation:

    python3 <SKILL_DIR>/scripts/walk_video.py engines [--voice FILE.onnx]
    python3 <SKILL_DIR>/scripts/walk_video.py check  script.json [--tts ENGINE] [--slides MODE]
    python3 <SKILL_DIR>/scripts/walk_video.py render script.json --out DIR \
        [--tts auto|piper|say|espeak-ng|none] [--voice FILE.onnx] \
        [--slides auto|html|ass] [--say-voice NAME] [--no-burn-captions] [--keep-work]

`check` reports every problem at once: scenes out of intent → change →
implications → validation order, a `shown` claim without a receipt, code or
points that don't fit the slide, missing image or video files. It also warns
about backticks in narration and walkthroughs estimated past 90 seconds.

`render` narrates each sentence separately, so captions match the voice
exactly, draws the slides, burns captions in with libass and joins the
scenes with 0.35 s cross-fades that fall in the silence between them.

Slides: `html` draws them in Chromium through `render_slides.mjs` (measured
layout, highlighted code, code shrinks from 30 px to 22 px before a scene is
refused); `ass` draws them with libass from estimated character widths.
`auto` uses `html` when Node can start Playwright's Chromium and warns when
it falls back. Naming `html` when it's unavailable exits 3.
It writes `walkthrough.mp4`, `captions.srt`, `transcript.md` (the PR comment
body, with the claims table) and `manifest.json` into `--out`.

Engines: `auto` picks piper (needs `piper` on PATH and a voice from
`--voice`, `BRUHS_PIPER_VOICE`, or `~/.local/share/bruhs/voices/*.onnx`),
then macOS `say`, then `espeak-ng`, then `none` (silent, captions only),
and warns when it falls back. Naming an unavailable engine is an error.

Exit codes: `0` success, `2` usage or script validation error, `3` ffmpeg
(with libass), the requested engine, or its voice is missing, `4` ffmpeg or
the TTS engine failed mid-render.

### `render_slides.mjs`

Internal to `walk_video.py --slides html`: takes the validated scenes and the
slide geometry as JSON, draws each slide as HTML in Chromium, measures what
overflows (heading, title lines, code rows and columns at the smallest code
size, points and claims height) and screenshots each slide to a 1920x1080
PNG. `probe` checks that Chromium starts. Shares Playwright discovery with
`record_demo.mjs`.

### `record_demo.mjs`

Record a browser demo from a shot list (URL, device, steps) and render an MP4
that a reviewer can read. Used by `walk --video`, `verify --keep-artifacts` and
UI previews; the shot-list format lives in `practices/demo-recording.md`.

Invocation:

    node <SKILL_DIR>/scripts/record_demo.mjs check   shots.json
    node <SKILL_DIR>/scripts/record_demo.mjs observe URL|shots.json [--device NAME] [--steps]
    node <SKILL_DIR>/scripts/record_demo.mjs record  shots.json --out DIR [--headed] [--keep-work]

`check` validates the shot list without a browser: one action per step, valid
targets, sizes and zooms. It warns when the capture resolution can't keep zoomed
detail sharp (fewer than 0.8 captured pixels per output pixel) and names the
scale that would.

`observe` opens the page (after any `setup` steps) and prints its accessibility
snapshot, so targets can be written from real roles and names.

`record` drives Chromium through the steps with `--force-device-scale-factor`
so the screencast delivers device pixels, moves the real mouse along the same
eased path it draws, and logs a timeline. A second offscreen Chromium page
composites each output frame (camera zoom, cursor or touch indicators, click
ripples, key chips) and pipes it to ffmpeg. It writes `demo.mp4`, `poster.png`
and `manifest.json` into `--out`.

Exit codes: `0` success, `2` usage or shot-list error, `3` Playwright,
Chromium or ffmpeg missing, `4` a step failed (the error names the step, saves
`failed-step-N.png` and prints the page's accessibility snapshot) or the render
failed.

## Notes

- JSON output is pretty-printed so callers can pipe through `jq` or
  re-parse without guesswork.
- Errors always go to stderr; success payloads always go to stdout.
- No script deletes files or runs destructive git commands. `walk_video.py` and `record_demo.mjs` remove only the `work/` folder they create under `--out`.
