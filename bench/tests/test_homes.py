import json
import shutil
import subprocess
import tomllib
from pathlib import Path

import pytest

from bruhsbench.homes import (
    LeakError,
    ProbeResult,
    assert_arms_match,
    assert_isolated,
    build_home,
    claude_args,
    normalize_names,
    parse_claude_stream,
    parse_codex_prompt_skills,
    parse_grok_inspect,
    probe_isolation,
    synced_extensions,
)

CLIS = ("claude", "codex", "grok")
REPO_ROOT = Path(__file__).resolve().parents[2]
REAL_MARKER = "REAL-HOME-MARKER-should-never-be-copied"


@pytest.fixture
def real_home(tmp_path: Path) -> Path:
    """A fake 'real' home with auth plus lots of stuff that must NOT leak."""
    h = tmp_path / "realhome"
    for d in (".codex", ".grok"):
        (h / d / "skills" / "superpowers").mkdir(parents=True)
        (h / d / "skills" / "superpowers" / "SKILL.md").write_text(REAL_MARKER)
        (h / d / "config.toml").write_text(f'# {REAL_MARKER}\nmodel = "x"\n')
        (h / d / "auth.json").write_text(json.dumps({"token": f"{d}-auth"}))
    (h / ".codex" / "AGENTS.md").write_text(REAL_MARKER)
    (h / ".claude" / "skills" / "impeccable").mkdir(parents=True)
    (h / ".claude" / "skills" / "impeccable" / "SKILL.md").write_text(REAL_MARKER)
    (h / ".claude" / "settings.json").write_text(json.dumps({"x": REAL_MARKER}))
    expect = h / ".agents" / "skills" / "expect"
    expect.mkdir(parents=True)
    (expect / "SKILL.md").write_text("---\nname: expect\n---\nexpect skill\n")
    (h / ".agents" / "skills" / "superpowers").mkdir()
    (h / ".agents" / "skills" / "superpowers" / "SKILL.md").write_text(REAL_MARKER)
    (h / "Library" / "Keychains").mkdir(parents=True)
    return h


@pytest.fixture
def bruhs_src(tmp_path: Path) -> Path:
    src = tmp_path / "run" / "bruhs"
    (src / ".claude-plugin").mkdir(parents=True)
    (src / ".claude-plugin" / "plugin.json").write_text('{"name": "bruhs"}')
    (src / "SKILL.md").write_text("---\nname: bruhs\n---\nbruhs\n")
    (src / "commands").mkdir()
    (src / "commands" / "cook.md").write_text("cook\n")
    (src / "bench" / "tests" / "reference").mkdir(parents=True)
    (src / "bench" / "tests" / "reference" / "answer.py").write_text("secret\n")
    (src / "docs").mkdir()
    (src / "docs" / "plan.md").write_text("benchmark plan\n")
    return src


def _build(cli, arm, tmp_path, bruhs_src, real_home, env_file=None):
    run_dir = tmp_path / "run"
    run_dir.mkdir(exist_ok=True)
    env = build_home(cli, arm, run_dir, bruhs_src, real_home=real_home,
                     env_file=env_file or tmp_path / "missing.env")
    return env, Path(env["HOME"])


def _files(root: Path) -> list[Path]:
    return [p for p in root.rglob("*") if p.is_file() and not p.is_symlink()]


def _skill_dirs(home: Path) -> list[Path]:
    return [home / ".claude" / "skills", home / ".agents" / "skills",
            home / ".grok" / "skills", home / ".codex" / "skills"]


def _needs_grok(cli):
    if cli == "grok" and shutil.which("grok") is None:
        pytest.skip("grok CLI not installed")


@pytest.mark.parametrize("cli", CLIS)
def test_build_home_bare_has_no_skills_dir_content(cli, tmp_path, bruhs_src, real_home):
    _needs_grok(cli)
    env, home = _build(cli, "bare", tmp_path, bruhs_src, real_home)
    assert home == tmp_path / "run" / "home"
    for d in _skill_dirs(home):
        assert not d.exists() or not any(d.iterdir()), d
    assert not (home / "plugins").exists()
    if cli == "claude":
        assert json.loads((home / "mcp.json").read_text()) == {"mcpServers": {}}
        settings = json.loads((home / ".claude" / "settings.json").read_text())
        assert settings == {"syncClaudeAiSkills": False, "syncClaudeAiPlugins": False}
        args = claude_args("bare", home)
        assert "--strict-mcp-config" in args and "--plugin-dir" not in args
    if cli == "codex":
        cfg = tomllib.loads((home / ".codex" / "config.toml").read_text())
        assert "mcp_servers" not in cfg
    if cli == "grok":
        cfg_path = home / ".grok" / "config.toml"
        assert not cfg_path.exists() or "mcp_servers" not in tomllib.loads(cfg_path.read_text())


@pytest.mark.parametrize("cli", CLIS)
def test_build_home_bruhs_installs_bruhs_and_expect(cli, tmp_path, bruhs_src, real_home):
    _needs_grok(cli)
    env, home = _build(cli, "bruhs", tmp_path, bruhs_src, real_home)
    if cli == "claude":
        bruhs_dir = home / "plugins" / "bruhs"
        expect_dir = home / ".claude" / "skills" / "expect"
        servers = json.loads((home / "mcp.json").read_text())["mcpServers"]
        args = claude_args("bruhs", home)
        assert args[args.index("--plugin-dir") + 1] == str(bruhs_dir)
        assert args[args.index("--mcp-config") + 1] == str(home / "mcp.json")
        assert "--strict-mcp-config" in args
        assert (bruhs_dir / ".claude-plugin" / "plugin.json").is_file()
    elif cli == "codex":
        bruhs_dir = home / ".agents" / "skills" / "bruhs"
        expect_dir = home / ".agents" / "skills" / "expect"
        servers = tomllib.loads((home / ".codex" / "config.toml").read_text())["mcp_servers"]
        assert env["CODEX_HOME"] == str(home / ".codex")
    else:
        bruhs_dir = home / ".grok" / "skills" / "bruhs"
        expect_dir = home / ".grok" / "skills" / "expect"
        servers = tomllib.loads((home / ".grok" / "config.toml").read_text())["mcp_servers"]
    assert (bruhs_dir / "SKILL.md").is_file()
    assert (bruhs_dir / "commands" / "cook.md").is_file()
    assert (expect_dir / "SKILL.md").read_text().startswith("---\nname: expect")
    assert set(servers) == {"chrome-devtools"}
    cd = servers["chrome-devtools"]
    assert cd["command"] == "npx"
    assert cd["args"] == ["-y", "chrome-devtools-mcp@latest", "--headless", "--isolated"]
    # the benchmark itself (reference solutions, plan) must never ride along with the skill
    assert not (bruhs_dir / "bench").exists()
    assert not (bruhs_dir / "docs").exists()


@pytest.mark.parametrize("cli", CLIS)
@pytest.mark.parametrize("arm", ("bare", "bruhs"))
def test_only_auth_copied(cli, arm, tmp_path, bruhs_src, real_home):
    _needs_grok(cli)
    env, home = _build(cli, arm, tmp_path, bruhs_src, real_home)
    for f in _files(home):
        assert REAL_MARKER not in f.read_text(errors="ignore"), f
    if cli == "codex":
        assert json.loads((home / ".codex" / "auth.json").read_text()) == {"token": ".codex-auth"}
        assert not (home / ".grok").exists()
    if cli == "grok":
        assert json.loads((home / ".grok" / "auth.json").read_text()) == {"token": ".grok-auth"}
        assert not (home / ".codex").exists()
    if cli == "claude":
        assert not (home / ".codex").exists() and not (home / ".grok").exists()


@pytest.mark.parametrize("cli", CLIS)
def test_env_is_minimal_and_points_at_isolated_home(cli, tmp_path, bruhs_src, real_home,
                                                     monkeypatch):
    _needs_grok(cli)
    monkeypatch.setenv("LEAKY_VAR", "1")
    monkeypatch.setenv("CODEX_HOME", "/real/.codex")
    env, home = _build(cli, "bare", tmp_path, bruhs_src, real_home)
    assert "LEAKY_VAR" not in env
    assert env["HOME"] == str(home)
    assert env["XDG_CONFIG_HOME"] == str(home / ".config")
    assert env["PATH"]
    if cli == "codex":
        assert env["CODEX_HOME"] == str(home / ".codex")
    else:
        assert "CODEX_HOME" not in env


@pytest.mark.parametrize("arm", ("bare", "bruhs"))
def test_codex_account_extensions_disabled(arm, tmp_path, bruhs_src, real_home):
    env, home = _build("codex", arm, tmp_path, bruhs_src, real_home)
    features = tomllib.loads((home / ".codex" / "config.toml").read_text())["features"]
    assert features == {"apps": False, "plugins": False, "remote_plugin": False}


def test_synced_extensions(tmp_path):
    home = tmp_path / "home"
    (home / ".grok" / "installed-plugins").mkdir(parents=True)
    (home / ".grok" / "installed-plugins" / "registry.lock").write_text("")
    (home / ".claude" / "skills" / "expect").mkdir(parents=True)
    (home / ".claude" / "skills" / "expect" / "SKILL.md").write_text("x")
    assert synced_extensions(home) == []
    synced = home / ".codex" / "plugins" / "cache" / "openai-curated-remote" / "linear"
    synced.mkdir(parents=True)
    (synced / "plugin.json").write_text("{}")
    (home / ".claude" / "skills" / "synced" / "id" / "pdf").mkdir(parents=True)
    (home / ".claude" / "skills" / "synced" / "id" / "pdf" / "SKILL.md").write_text("x")
    assert synced_extensions(home) == [
        ".claude/skills/synced/id/pdf/SKILL.md",
        ".codex/plugins/cache/openai-curated-remote/linear/plugin.json",
    ]


def test_build_home_refuses_existing_home(tmp_path, bruhs_src, real_home):
    _build("codex", "bare", tmp_path, bruhs_src, real_home)
    with pytest.raises(FileExistsError):
        _build("codex", "bare", tmp_path, bruhs_src, real_home)


def test_claude_auth_from_env_file(tmp_path, bruhs_src, real_home, monkeypatch):
    monkeypatch.delenv("CLAUDE_CODE_OAUTH_TOKEN", raising=False)
    monkeypatch.delenv("ANTHROPIC_API_KEY", raising=False)
    env_file = tmp_path / ".env"
    env_file.write_text("# comment\nCLAUDE_CODE_OAUTH_TOKEN='tok-123'\nOTHER=x\n")
    env, home = _build("claude", "bare", tmp_path, bruhs_src, real_home, env_file)
    assert env["CLAUDE_CODE_OAUTH_TOKEN"] == "tok-123"
    assert "OTHER" not in env
    assert not (home / "Library" / "Keychains").exists()


def test_claude_auth_falls_back_to_keychain_link(tmp_path, bruhs_src, real_home, monkeypatch):
    monkeypatch.delenv("CLAUDE_CODE_OAUTH_TOKEN", raising=False)
    monkeypatch.delenv("ANTHROPIC_API_KEY", raising=False)
    env, home = _build("claude", "bare", tmp_path, bruhs_src, real_home)
    link = home / "Library" / "Keychains"
    assert link.is_symlink() and link.resolve() == (real_home / "Library" / "Keychains").resolve()
    assert "CLAUDE_CODE_OAUTH_TOKEN" not in env and "ANTHROPIC_API_KEY" not in env


def test_probe_detects_leaked_skill():
    with pytest.raises(LeakError):
        assert_isolated(ProbeResult({"superpowers"}, set()), "bare")


@pytest.mark.parametrize("result,arm", [
    (ProbeResult({"bruhs:cook"}, set()), "bare"),
    (ProbeResult({"expect"}, set()), "bare"),
    (ProbeResult(set(), {"chrome-devtools"}), "bare"),
    (ProbeResult(set(), {"linear"}), "bare"),
    (ProbeResult({"bruhs"}, {"chrome-devtools"}), "bruhs"),  # missing expect
    (ProbeResult({"expect"}, {"chrome-devtools"}), "bruhs"),  # missing bruhs
    (ProbeResult({"bruhs", "expect"}, set()), "bruhs"),  # missing chrome-devtools
    (ProbeResult({"bruhs", "expect", "superpowers:brainstorming"}, {"chrome-devtools"}), "bruhs"),
    (ProbeResult({"bruhs", "expect", "impeccable"}, {"chrome-devtools"}), "bruhs"),
    (ProbeResult({"bruhs", "expect"}, {"chrome-devtools", "linear"}), "bruhs"),
])
def test_assert_isolated_rejects(result, arm):
    with pytest.raises(LeakError):
        assert_isolated(result, arm)


@pytest.mark.parametrize("result,arm", [
    (ProbeResult(set(), set()), "bare"),
    (ProbeResult({"skill-creator", "imagegen", "code-review"}, set()), "bare"),
    (ProbeResult({"bruhs:bruhs", "bruhs:cook", "expect", "pdf"}, {"chrome-devtools"}), "bruhs"),
])
def test_assert_isolated_accepts(result, arm):
    assert_isolated(result, arm)


def test_normalize_names_strips_tool_prefixes():
    assert normalize_names(["mcp__chrome-devtools__click", "chrome-devtools", " Expect ",
                            "/bruhs:cook", ""]) == {"chrome-devtools", "expect", "bruhs:cook"}


def test_parse_claude_stream():
    lines = [
        {"type": "system", "subtype": "init", "skills": ["expect", "bruhs:bruhs"],
         "mcp_servers": [{"name": "chrome-devtools", "status": "connected"}]},
        {"type": "assistant"},
        {"type": "result", "result": 'Here:\n```json\n{"skills": ["simplify"], "mcps": ["x"]}\n```'},
    ]
    r = parse_claude_stream("\n".join(json.dumps(x) for x in lines))
    # MCPs come only from the CLI's own report; the model's "x" is not trusted
    assert r == ProbeResult({"expect", "bruhs:bruhs", "simplify"}, {"chrome-devtools"},
                            {"expect", "bruhs:bruhs"})


def test_parse_codex_prompt_skills():
    items = [{"type": "message", "role": "developer", "content": [{"type": "input_text", "text":
             "<skills_instructions>\n### Available skills\n- imagegen: Generate (file: r0/a)\n"
             "- bruhs: End-to-end (file: r1/bruhs/SKILL.md)\n### How to use skills\n- Trigger "
             "rules: x\n</skills_instructions>"}]}]
    assert parse_codex_prompt_skills(json.dumps(items)) == {"imagegen", "bruhs"}


def test_parse_grok_inspect():
    out = json.dumps({"skills": [{"name": "bruhs"}], "plugins": [{"name": "p"}],
                      "mcpServers": [{"name": "chrome-devtools"}]})
    assert parse_grok_inspect(out) == ProbeResult({"bruhs", "p"}, {"chrome-devtools"},
                                                  {"bruhs", "p"})


def test_assert_arms_match():
    bare = ProbeResult(cli_skills={"simplify", "pdf"})
    assert_arms_match(bare, ProbeResult(cli_skills={"simplify", "pdf", "bruhs:cook", "expect"}))
    with pytest.raises(LeakError):  # something besides bruhs only in the bruhs arm
        assert_arms_match(bare, ProbeResult(cli_skills={"simplify", "pdf", "bruhs", "xlsx"}))
    with pytest.raises(LeakError):  # bruhs arm lost a skill the bare arm has
        assert_arms_match(bare, ProbeResult(cli_skills={"simplify", "bruhs"}))


_LIVE: dict[tuple[str, str], ProbeResult] = {}


def _live_probe(cli, arm, tmp_path_factory) -> ProbeResult:
    if (cli, arm) not in _LIVE:
        run_dir = tmp_path_factory.mktemp(f"{cli}-{arm}")
        bruhs_src = run_dir / "bruhs"
        bruhs_src.mkdir()
        archive = subprocess.run(["git", "archive", "HEAD"], cwd=REPO_ROOT, check=True,
                                 capture_output=True).stdout
        subprocess.run(["tar", "-x", "-C", str(bruhs_src)], input=archive, check=True)
        env = build_home(cli, arm, run_dir, bruhs_src)
        _LIVE[(cli, arm)] = r = probe_isolation(cli, arm, env)
        print(f"\nPROBE {cli}/{arm}: skills={sorted(r.skills)} mcps={sorted(r.mcps)} "
              f"cli_skills={sorted(r.cli_skills)}")
    return _LIVE[(cli, arm)]


@pytest.mark.live
@pytest.mark.parametrize("arm", ("bare", "bruhs"))
@pytest.mark.parametrize("cli", CLIS)
def test_live_isolation(cli, arm, tmp_path_factory):
    assert_isolated(_live_probe(cli, arm, tmp_path_factory), arm)


@pytest.mark.live
@pytest.mark.parametrize("cli", CLIS)
def test_live_arms_differ_only_by_bruhs(cli, tmp_path_factory):
    assert_arms_match(_live_probe(cli, "bare", tmp_path_factory),
                      _live_probe(cli, "bruhs", tmp_path_factory))
