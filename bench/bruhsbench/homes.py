"""Hermetic per-run agent homes, and a probe proving what each agent can see.

Every run gets ``<run_dir>/home`` as ``HOME`` (plus ``XDG_CONFIG_HOME``); the
agent's environment is rebuilt from scratch (``PATH``, ``LANG``, ``TERM``,
``USER``/``LOGNAME``, ``TMPDIR`` pass through) so nothing in the user's real
``~/.claude``, ``~/.codex``, ``~/.grok`` or ``~/.agents`` is visible. Only auth
is brought in. Mechanisms, verified live with ``pytest -m live tests/test_homes.py``:

claude
    Auth, in order of precedence:
    1. ``CLAUDE_CODE_OAUTH_TOKEN`` or ``ANTHROPIC_API_KEY`` from the process env
       or ``bench/.env`` (gitignored). If one is set it is passed to claude and
       no keychain link is made.
    2. Default when no token is set: the user's macOS login keychain. With
       ``HOME`` overridden Claude Code reports "Not logged in", because it finds
       the keychain via ``$HOME/Library/Keychains``; so
       ``<home>/Library/Keychains`` is symlinked to the real one. Nothing else
       from the real home is linked, and we never read the keychain ourselves.
       Caveat: every run then shares the one keychain login, and when claude
       refreshes the OAuth token it writes the new one back to the real
       keychain. Parallel runs can race on that refresh; if auth failures show
       up, put a ``claude setup-token`` token in ``bench/.env``.
    Skills/MCP: bruhs arm = ``--plugin-dir <home>/plugins/bruhs`` + expect in
    ``<home>/.claude/skills/expect`` + ``--mcp-config <home>/mcp.json
    --strict-mcp-config`` (chrome-devtools). Bare arm = the same flags with an
    empty ``mcp.json`` (strict mode also drops claude.ai account connectors).
    Use :func:`claude_args` to get these flags. ``<home>/.claude/settings.json``
    turns off claude.ai account skill/plugin sync in both arms: left on, the
    account's skills download asynchronously and showed up in one arm's first
    run but not the other's.
codex
    ``CODEX_HOME=<home>/.codex`` holding only a copy of ``auth.json`` and a
    generated ``config.toml`` that, in both arms, disables ``apps`` (ChatGPT
    account connectors), ``plugins`` and ``remote_plugin`` (left on, the
    account's remote plugins -- linear, github, gmail, vercel, ... -- were
    downloaded into the fresh home during the run). bruhs arm adds bruhs + expect in
    ``<home>/.agents/skills/`` and ``[mcp_servers.chrome-devtools]``.
grok
    No GROK_HOME exists; ``HOME`` override is enough. ``<home>/.grok`` holds a
    copy of ``auth.json``; bruhs arm adds bruhs + expect in
    ``<home>/.grok/skills/`` and chrome-devtools via ``grok mcp add`` run under
    the isolated env.

bruhs must reach an agent without ``bench/`` and ``docs/`` (the benchmark's own
reference solutions and plan). The runner exports it with :func:`export_bruhs`
(a filtered ``git archive`` of the pinned commit); :func:`build_home` refuses an
unfiltered ``bruhs_src`` inside ``run_dir`` and copies only the filtered tree.
``run_dir`` must be outside the user's home: the CLIs walk ancestor directories
for config, so :func:`build_home` raises ``ValueError`` for a run_dir under ``~``.

The probe takes what the CLI reports deterministically (claude's stream-json
init event, ``codex debug prompt-input`` + ``codex mcp list``, ``grok inspect``)
and unions in the skills the model itself names when asked, so a skill leak
seen by either fails. MCP servers come from the CLI report only: asked the same
question, the codex model named its built-in ``clock`` tool namespace as an
MCP server. Afterwards the probe also fails if any account-synced
skills/plugins landed in the home.
"""

from __future__ import annotations

import json
import os
import re
import shutil
import subprocess
from dataclasses import dataclass, field
from pathlib import Path

from .types import MODELS, Arm, Cli

DEFAULT_ENV_FILE = Path(__file__).resolve().parents[1] / ".env"
CLAUDE_AUTH_VARS = ("CLAUDE_CODE_OAUTH_TOKEN", "ANTHROPIC_API_KEY")
PASSTHROUGH_VARS = ("PATH", "LANG", "TERM", "USER", "LOGNAME", "TMPDIR")
BRUHS_EXCLUDE = ("bench", "docs", ".git", ".superpowers")
EXPORT_EXCLUDE = ("bench", "docs")
# Account-synced claude.ai skills/plugins download asynchronously into a fresh home, so
# they appear in some runs and not others; turn the sync off in both arms.
CLAUDE_SETTINGS = {"syncClaudeAiSkills": False, "syncClaudeAiPlugins": False}

CHROME_DEVTOOLS_CMD = "npx"
CHROME_DEVTOOLS_ARGS = ("-y", "chrome-devtools-mcp@latest", "--headless", "--isolated")
MCP_STARTUP_TIMEOUT_S = 120
CODEX_FEATURES = "[features]\napps = false\nplugins = false\nremote_plugin = false\n"

PROBE_EFFORT = "low"
PROBE_TIMEOUT_S = 600
PROBE_PROMPT = (
    "List the names of every skill and every MCP server available to you in this session, "
    'as JSON {"skills": [...], "mcps": [...]}. Skills are SKILL.md-based skills or plugin '
    "skills/commands; MCP servers are external Model Context Protocol servers (not your "
    "built-in tools). Do not run any tools. Output only the JSON object."
)
PROBE_SCHEMA = {
    "type": "object",
    "properties": {
        "skills": {"type": "array", "items": {"type": "string"}},
        "mcps": {"type": "array", "items": {"type": "string"}},
    },
    "required": ["skills", "mcps"],
    "additionalProperties": False,
}

BARE_FORBIDDEN_SKILLS = frozenset({"bruhs", "expect", "superpowers", "impeccable"})
BRUHS_FORBIDDEN_SKILLS = frozenset({"superpowers", "impeccable"})
BRUHS_REQUIRED_SKILLS = frozenset({"bruhs", "expect"})
BRUHS_MCPS = frozenset({"chrome-devtools"})


class LeakError(AssertionError):
    pass


@dataclass(frozen=True)
class ProbeResult:
    skills: set[str] = field(default_factory=set)
    mcps: set[str] = field(default_factory=set)
    # the subset of ``skills`` the CLI itself reported (deterministic, unlike the model's
    # answer); used to check the two arms differ only by the bruhs install
    cli_skills: set[str] = field(default_factory=set)

    def __or__(self, other: ProbeResult) -> ProbeResult:
        return ProbeResult(self.skills | other.skills, self.mcps | other.mcps,
                           self.cli_skills | other.cli_skills)


# --------------------------------------------------------------------------- homes


def _read_env_file(path: Path) -> dict[str, str]:
    out: dict[str, str] = {}
    if not path.is_file():
        return out
    for line in path.read_text().splitlines():
        line = line.strip()
        if not line or line.startswith("#") or "=" not in line:
            continue
        key, _, value = line.removeprefix("export ").partition("=")
        out[key.strip()] = value.strip().strip("'\"")
    return out


def _claude_auth(env_file: Path) -> dict[str, str]:
    file_vars = _read_env_file(env_file)
    found = {}
    for var in CLAUDE_AUTH_VARS:
        value = os.environ.get(var) or file_vars.get(var)
        if value:
            found[var] = value
    return found


def export_bruhs(repo: Path, commit: str, dest: Path) -> Path:
    """Write ``commit`` of the bruhs repo to ``dest`` without bench/ and docs/."""
    dest.mkdir(parents=True, exist_ok=False)
    excludes = [f":(exclude){d}" for d in EXPORT_EXCLUDE]
    archive = subprocess.run(["git", "archive", commit, "--", ".", *excludes], cwd=repo,
                             check=True, capture_output=True).stdout
    subprocess.run(["tar", "-x", "-C", str(dest)], input=archive, check=True,
                   capture_output=True)
    return dest


def _is_within(path: Path, root: Path) -> bool:
    return path.resolve().is_relative_to(root.resolve())


def _copy_bruhs(bruhs_src: Path, dest: Path) -> None:
    def ignore(dirpath: str, names: list[str]) -> list[str]:
        return [n for n in names if n in BRUHS_EXCLUDE] if Path(dirpath) == bruhs_src else []

    shutil.copytree(bruhs_src, dest, ignore=ignore, symlinks=True)


def _install_skills(skills_dir: Path, bruhs_src: Path, expect_src: Path) -> None:
    skills_dir.mkdir(parents=True, exist_ok=True)
    _copy_bruhs(bruhs_src, skills_dir / "bruhs")
    shutil.copytree(expect_src.resolve(), skills_dir / "expect")


def _copy_auth(src: Path, dest_dir: Path) -> None:
    if not src.is_file():
        raise FileNotFoundError(f"missing auth file {src}; log in to the CLI first")
    dest_dir.mkdir(parents=True, exist_ok=True)
    shutil.copy2(src, dest_dir / src.name)


def _toml_str(s: str) -> str:
    return json.dumps(s)  # a JSON string literal is a valid TOML basic string


def claude_args(arm: Arm, home: Path) -> list[str]:
    """Isolation flags every claude invocation in ``home`` must carry."""
    args = ["--mcp-config", str(home / "mcp.json"), "--strict-mcp-config"]
    if arm == "bruhs":
        args = ["--plugin-dir", str(home / "plugins" / "bruhs"), *args]
    return args


def build_home(
    cli: Cli,
    arm: Arm,
    run_dir: Path,
    bruhs_src: Path,
    *,
    real_home: Path | None = None,
    env_file: Path = DEFAULT_ENV_FILE,
) -> dict[str, str]:
    """Create ``run_dir/home`` for one run and return the full env for the CLI."""
    if _is_within(run_dir, Path.home()):
        raise ValueError(f"run_dir {run_dir} is inside the user's home; the CLIs would "
                         "discover ~/ config from its ancestors")
    if _is_within(bruhs_src, run_dir) and (
            bad := [d for d in EXPORT_EXCLUDE if (bruhs_src / d).exists()]):
        raise ValueError(f"bruhs_src {bruhs_src} is inside run_dir but still has {bad}; "
                         "export it with export_bruhs()")
    real = real_home or Path.home()
    home = run_dir / "home"
    home.mkdir(parents=True, exist_ok=False)
    (home / ".config").mkdir()
    expect_src = real / ".agents" / "skills" / "expect"

    env = {k: os.environ[k] for k in PASSTHROUGH_VARS if os.environ.get(k)}
    env["HOME"] = str(home)
    env["XDG_CONFIG_HOME"] = str(home / ".config")

    if cli == "claude":
        auth = _claude_auth(env_file)
        if auth:
            env.update(auth)
        else:
            (home / "Library").mkdir()
            (home / "Library" / "Keychains").symlink_to(real / "Library" / "Keychains")
        (home / ".claude").mkdir()
        settings = json.dumps(CLAUDE_SETTINGS, indent=2) + "\n"
        (home / ".claude" / "settings.json").write_text(settings)
        servers = {}
        if arm == "bruhs":
            _copy_bruhs(bruhs_src, home / "plugins" / "bruhs")
            (home / ".claude" / "skills").mkdir()
            shutil.copytree(expect_src.resolve(), home / ".claude" / "skills" / "expect")
            servers = {"chrome-devtools": {"command": CHROME_DEVTOOLS_CMD,
                                           "args": list(CHROME_DEVTOOLS_ARGS)}}
        (home / "mcp.json").write_text(json.dumps({"mcpServers": servers}, indent=2) + "\n")

    elif cli == "codex":
        codex_home = home / ".codex"
        _copy_auth(real / ".codex" / "auth.json", codex_home)
        config = CODEX_FEATURES
        if arm == "bruhs":
            _install_skills(home / ".agents" / "skills", bruhs_src, expect_src)
            args = ", ".join(_toml_str(a) for a in CHROME_DEVTOOLS_ARGS)
            config += (
                "\n[mcp_servers.chrome-devtools]\n"
                f"command = {_toml_str(CHROME_DEVTOOLS_CMD)}\n"
                f"args = [{args}]\n"
                f"startup_timeout_sec = {MCP_STARTUP_TIMEOUT_S}\n"
            )
        (codex_home / "config.toml").write_text(config)
        env["CODEX_HOME"] = str(codex_home)

    elif cli == "grok":
        _copy_auth(real / ".grok" / "auth.json", home / ".grok")
        if arm == "bruhs":
            _install_skills(home / ".grok" / "skills", bruhs_src, expect_src)
            subprocess.run(
                ["grok", "mcp", "add", "chrome-devtools", CHROME_DEVTOOLS_CMD, "--",
                 *CHROME_DEVTOOLS_ARGS],
                env=env, cwd=home, check=True, capture_output=True, text=True, timeout=120,
            )
    else:
        raise ValueError(f"unknown cli {cli!r}")
    return env


# --------------------------------------------------------------------------- probe


def normalize_names(names) -> set[str]:
    out = set()
    for raw in names:
        name = str(raw).strip().lower().lstrip("/")
        if name.startswith("mcp__"):
            name = name.split("__")[1]
        if name:
            out.add(name)
    return out


def _json_objects(text: str):
    decoder = json.JSONDecoder()
    for m in re.finditer(r"\{", text):
        try:
            obj, _ = decoder.raw_decode(text, m.start())
        except json.JSONDecodeError:
            continue
        yield obj


def _find_listing(obj) -> ProbeResult | None:
    """Find a {"skills": [...], "mcps": [...]} answer anywhere in ``obj``."""
    if isinstance(obj, dict):
        if isinstance(obj.get("skills"), list) and isinstance(obj.get("mcps"), list):
            return ProbeResult(normalize_names(obj["skills"]), normalize_names(obj["mcps"]))
        children = obj.values()
    elif isinstance(obj, list):
        children = obj
    elif isinstance(obj, str) and "skills" in obj:
        children = list(_json_objects(obj))
    else:
        return None
    for child in children:
        found = _find_listing(child)
        if found is not None:
            return found
    return None


def _model_listing(text: str) -> ProbeResult:
    """The skills the model names in its answer (its MCP names are not trusted)."""
    for obj in _json_objects(text):
        found = _find_listing(obj)
        if found is not None:
            return ProbeResult(found.skills)
    raise LeakError(f"probe: no skills/mcps JSON in model output:\n{text[-2000:]}")


def parse_claude_stream(stdout: str) -> ProbeResult:
    events = [json.loads(line) for line in stdout.splitlines() if line.startswith("{")]
    init = next((e for e in events if e.get("subtype") == "init"), None)
    final = next((e for e in reversed(events) if e.get("type") == "result"), None)
    if init is None or final is None:
        raise LeakError(f"probe: claude stream missing init/result:\n{stdout[-2000:]}")
    if final.get("is_error"):
        raise LeakError(f"probe: claude error: {final.get('result')}")
    skills = normalize_names(init.get("skills", []))
    seen = ProbeResult(
        skills, normalize_names(s["name"] for s in init.get("mcp_servers", [])), skills)
    answer = final.get("structured_output") or final.get("result", "")
    return seen | _model_listing(answer if isinstance(answer, str) else json.dumps(answer))


def parse_codex_prompt_skills(stdout: str) -> set[str]:
    names: set[str] = set()
    for item in json.loads(stdout):
        for content in item.get("content", []):
            text = content.get("text", "")
            if "### Available skills" not in text:
                continue
            section = text.split("### Available skills", 1)[1].split("\n###", 1)[0]
            names |= {m.group(1) for m in re.finditer(r"^- ([^:\n]+):", section, re.MULTILINE)}
    return normalize_names(names)


def parse_grok_inspect(stdout: str) -> ProbeResult:
    data = json.loads(stdout)
    skills = [s["name"] for s in data.get("skills", [])]
    skills += [p["name"] for p in data.get("plugins", [])]
    names = normalize_names(skills)
    return ProbeResult(names, normalize_names(s["name"] for s in data.get("mcpServers", [])),
                       names)


def _run(cmd: list[str], env: dict[str, str], cwd: Path) -> str:
    proc = subprocess.run(cmd, env=env, cwd=cwd, capture_output=True, text=True,
                          timeout=PROBE_TIMEOUT_S)
    if proc.returncode != 0:
        raise LeakError(f"probe command failed ({proc.returncode}): {cmd[:3]}\n"
                        f"{proc.stdout[-2000:]}\n{proc.stderr[-2000:]}")
    return proc.stdout


def probe_isolation(cli: Cli, arm: Arm, env: dict[str, str]) -> ProbeResult:
    """Ask the CLI, headlessly and inside its isolated env, what skills and MCPs it has."""
    home = Path(env["HOME"])
    work = home.parent / "probe"
    work.mkdir(exist_ok=True)
    model = next(m.model for m in MODELS if m.cli == cli)
    schema = json.dumps(PROBE_SCHEMA)

    if cli == "claude":
        result = parse_claude_stream(_run(
            ["claude", "-p", PROBE_PROMPT, "--model", model, "--effort", PROBE_EFFORT,
             "--output-format", "stream-json", "--verbose", "--json-schema", schema,
             *claude_args(arm, home)], env, work))

    elif cli == "codex":
        schema_file = work / "schema.json"
        schema_file.write_text(schema)
        last = work / "last-message.txt"
        _run(["codex", "exec", "--json", "--skip-git-repo-check", "--ephemeral", "-m", model,
              "-c", f'model_reasoning_effort="{PROBE_EFFORT}"', "--output-schema",
              str(schema_file), "-o", str(last), PROBE_PROMPT], env, work)
        skills = parse_codex_prompt_skills(
            _run(["codex", "debug", "prompt-input", "probe"], env, work))
        mcps = normalize_names(
            s["name"] for s in json.loads(_run(["codex", "mcp", "list", "--json"], env, work)))
        if not last.is_file():
            raise LeakError(f"probe: codex exited 0 but wrote no last message to {last}")
        result = ProbeResult(skills, mcps, skills) | _model_listing(last.read_text())

    elif cli == "grok":
        out = _run(["grok", "-p", PROBE_PROMPT, "-m", model, "--effort", PROBE_EFFORT,
                    "--output-format", "json", "--json-schema", schema, "--cwd", str(work)],
                   env, work)
        seen = parse_grok_inspect(_run(["grok", "inspect", "--json"], env, work))
        result = seen | _model_listing(out)
    else:
        raise ValueError(f"unknown cli {cli!r}")

    if synced := synced_extensions(home):
        raise LeakError(f"account-synced extensions landed in {home}: {synced}")
    return result


SYNC_DIRS = (".claude/skills/synced", ".claude/plugins", ".codex/plugins",
             ".grok/installed-plugins")


def synced_extensions(home: Path) -> list[str]:
    """Files the CLI downloaded from the user's account into ``home`` (should be none)."""
    found = []
    for rel in SYNC_DIRS:
        root = home / rel
        if root.is_dir():
            found += [str(f.relative_to(home)) for f in root.rglob("*")
                      if f.is_file() and f.name != "registry.lock"]
    return sorted(found)


def _skill_tokens(name: str) -> set[str]:
    return set(re.split(r"[:/]", name))


REAL_SKILL_ROOTS = (".claude/skills", ".agents/skills", ".codex/skills", ".grok/skills")
REAL_PLUGINS_FILE = ".claude/plugins/installed_plugins.json"


def real_extension_names(real_home: Path | None = None) -> tuple[set[str], set[str]]:
    """(skill dir names, installed claude plugin names) in the user's real home."""
    home = real_home or Path.home()
    skills: set[str] = set()
    for rel in REAL_SKILL_ROOTS:
        root = home / rel
        if root.is_dir():
            skills |= {d.name.lower() for d in root.iterdir()
                       if d.is_dir() and not d.name.startswith(".")}
    plugins: set[str] = set()
    plugins_file = home / REAL_PLUGINS_FILE
    if plugins_file.is_file():
        installed = json.loads(plugins_file.read_text()).get("plugins", {})
        plugins = {key.split("@", 1)[0].lower() for key in installed}
    return skills, plugins


def _real_leaks(result: ProbeResult, arm: Arm, real_home: Path | None) -> set[str]:
    """Probe skills that are the user's own skills or plugins (by name).

    A user skill shows up under its own name; a user plugin's skills show up as
    ``<plugin>:<skill>``, so plugins are matched on the namespace only (plugin
    ``code-review`` must not flag claude's built-in ``code-review`` skill).
    """
    skills, plugins = real_extension_names(real_home)
    if arm == "bruhs":
        skills -= BRUHS_REQUIRED_SKILLS
        plugins -= BRUHS_REQUIRED_SKILLS
    return {s for s in result.skills
            if s in skills or (":" in s and s.split(":", 1)[0] in plugins)}


def assert_isolated(result: ProbeResult, arm: Arm, *, real_home: Path | None = None) -> None:
    """Raise LeakError unless ``result`` is exactly what ``arm`` should see.

    ``real_home`` (default ``~``) is where the user's own skills/plugins live; any
    of them in the result is a leak, except bruhs/expect in the bruhs arm.
    """
    tokens = set().union(*(_skill_tokens(s) for s in result.skills)) if result.skills else set()
    problems = []
    if real := _real_leaks(result, arm, real_home):
        problems.append(f"user's own skills/plugins {sorted(real)}")
    if arm == "bare":
        if leaked := tokens & BARE_FORBIDDEN_SKILLS:
            problems.append(f"forbidden skills {sorted(leaked)}")
        if result.mcps:
            problems.append(f"MCP servers present {sorted(result.mcps)}")
    else:
        if leaked := tokens & BRUHS_FORBIDDEN_SKILLS:
            problems.append(f"forbidden skills {sorted(leaked)}")
        if missing := BRUHS_REQUIRED_SKILLS - tokens:
            problems.append(f"missing skills {sorted(missing)}")
        if result.mcps != BRUHS_MCPS:
            problems.append(f"MCP servers {sorted(result.mcps)} != {sorted(BRUHS_MCPS)}")
    if problems:
        raise LeakError(f"{arm} arm not isolated: " + "; ".join(problems)
                        + f" (skills={sorted(result.skills)}, mcps={sorted(result.mcps)})")


def assert_arms_match(bare: ProbeResult, bruhs: ProbeResult) -> None:
    """Raise LeakError unless the CLI-reported skills differ only by the bruhs install."""
    extra = {s for s in bruhs.cli_skills - bare.cli_skills
             if not _skill_tokens(s) & BRUHS_REQUIRED_SKILLS}
    missing = bare.cli_skills - bruhs.cli_skills
    if extra or missing:
        raise LeakError(f"arms differ beyond bruhs: only in bruhs {sorted(extra)}, "
                        f"only in bare {sorted(missing)}")
