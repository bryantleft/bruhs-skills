import json
import shutil
import subprocess
import tomllib
from pathlib import Path

import pytest
from live_auth import need_claude_token

import bruhsbench.homes as homes_mod
from bruhsbench.homes import (
    ClaudeAuthMissing,
    LeakError,
    ProbeResult,
    assert_arms_match,
    assert_isolated,
    build_home,
    export_bruhs,
    claude_args,
    normalize_names,
    parse_claude_stream,
    parse_codex_prompt_skills,
    parse_grok_inspect,
    probe_isolation,
    sanitized_path,
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
    return h


@pytest.fixture
def bruhs_src(tmp_path: Path) -> Path:
    """An unfiltered bruhs tree OUTSIDE run_dir (build_home must filter its copy)."""
    src = tmp_path / "src" / "bruhs"
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


def _token_env(tmp_path: Path) -> Path:
    """A bench/.env stand-in holding a (fake) claude token (R20)."""
    env_file = tmp_path / "token.env"
    env_file.write_text("CLAUDE_CODE_OAUTH_TOKEN=test-token\n")
    return env_file


def _build(cli, arm, tmp_path, bruhs_src, real_home, env_file=None):
    run_dir = tmp_path / "run"
    run_dir.mkdir(exist_ok=True)
    env = build_home(cli, arm, run_dir, bruhs_src, real_home=real_home,
                     env_file=env_file or _token_env(tmp_path))
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
    assert cd["args"] == ["-y", "chrome-devtools-mcp@latest", "--headless", "--isolated",
                          "--chrome-arg=--no-sandbox"]
    # the benchmark itself (reference solutions, plan) must never ride along with the skill
    assert not (bruhs_dir / "bench").exists()
    assert not (bruhs_dir / "docs").exists()


@pytest.fixture
def bruhs_src_skills_layout(tmp_path: Path) -> Path:
    """A bruhs tree in the 1.7.0+ layout: the skill under skills/bruhs/, plugin and
    eval files at the repo root."""
    src = tmp_path / "src-skills" / "bruhs"
    (src / ".claude-plugin").mkdir(parents=True)
    (src / ".claude-plugin" / "plugin.json").write_text(
        '{"name": "bruhs", "commands": "./skills/bruhs/commands/"}')
    skill = src / "skills" / "bruhs"
    (skill / "commands").mkdir(parents=True)
    (skill / "SKILL.md").write_text("---\nname: bruhs\n---\nbruhs\n")
    (skill / "commands" / "cook.md").write_text("cook\n")
    (src / "evals" / "cook-case").mkdir(parents=True)
    (src / "evals" / "cook-case" / "prompt.md").write_text("cook it\n")
    return src


@pytest.mark.parametrize("cli", CLIS)
def test_build_home_installs_the_skill_folder_from_the_skills_layout(
        cli, tmp_path, bruhs_src_skills_layout, real_home):
    _needs_grok(cli)
    _, home = _build(cli, "bruhs", tmp_path, bruhs_src_skills_layout, real_home)
    if cli == "claude":
        # the plugin is the whole repo; its manifest points at the skill's commands
        plugin = home / "plugins" / "bruhs"
        assert (plugin / ".claude-plugin" / "plugin.json").is_file()
        assert (plugin / "skills" / "bruhs" / "SKILL.md").is_file()
        return
    skills = home / (".agents" if cli == "codex" else ".grok") / "skills"
    bruhs_dir = skills / "bruhs"
    assert (bruhs_dir / "SKILL.md").is_file()
    assert (bruhs_dir / "commands" / "cook.md").is_file()
    # only the skill folder: no plugin manifest, evals or nested skills/ tree
    assert sorted(p.name for p in bruhs_dir.iterdir()) == ["SKILL.md", "commands"]


def test_bruhs_skill_dir_needs_a_skill_md(tmp_path):
    from bruhsbench.homes import bruhs_skill_dir

    root = tmp_path / "bruhs"
    (root / "skills" / "bruhs").mkdir(parents=True)
    with pytest.raises(FileNotFoundError, match="no SKILL.md"):
        bruhs_skill_dir(root)
    (root / "SKILL.md").write_text("old layout\n")
    assert bruhs_skill_dir(root) == root
    (root / "skills" / "bruhs" / "SKILL.md").write_text("new layout\n")
    assert bruhs_skill_dir(root) == root / "skills" / "bruhs"


def test_sanitized_path_drops_bench_venv_and_repo(tmp_path):
    venv = tmp_path / "venv"
    repo = tmp_path / "repo"
    path = ":".join([str(venv / "bin"), "/usr/bin", str(repo / "bench/.venv/bin"),
                     str(tmp_path / "repo-other/bin"), "", "/bin"])
    assert sanitized_path(path, exclude=[repo, venv]) == ":".join(
        ["/usr/bin", str(tmp_path / "repo-other/bin"), "/bin"])


def test_build_home_path_excludes_virtualenv(tmp_path, bruhs_src, real_home, monkeypatch):
    venv = tmp_path / "venv"
    monkeypatch.setenv("VIRTUAL_ENV", str(venv))
    monkeypatch.setenv("PATH", f"{venv / 'bin'}:{REPO_ROOT / 'bench/.venv/bin'}:/usr/bin:/bin")
    env, _ = _build("claude", "bare", tmp_path, bruhs_src, real_home)
    assert env["PATH"] == "/usr/bin:/bin"


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
    assert not (home / "Library").exists()  # no keychain link (R20)


def test_claude_without_token_raises_before_anything(tmp_path, bruhs_src, real_home,
                                                     monkeypatch):
    """R20: no keychain fallback; a clear error naming `claude setup-token`."""
    monkeypatch.delenv("CLAUDE_CODE_OAUTH_TOKEN", raising=False)
    monkeypatch.delenv("ANTHROPIC_API_KEY", raising=False)
    run_dir = tmp_path / "run"
    run_dir.mkdir()
    with pytest.raises(ClaudeAuthMissing, match="claude setup-token"):
        build_home("claude", "bare", run_dir, bruhs_src, real_home=real_home,
                   env_file=tmp_path / "missing.env")
    assert not (run_dir / "home").exists()


def test_bench_env_file_is_gitignored():
    """bench/.env holds the real claude token; it must never be committable."""
    proc = subprocess.run(["git", "check-ignore", "-q", "bench/.env"], cwd=REPO_ROOT)
    assert proc.returncode == 0


def test_probe_detects_leaked_skill():
    with pytest.raises(LeakError):
        assert_isolated(ProbeResult({"superpowers"}, set()), "bare", real_home=Path("/nonexistent"))


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
def test_assert_isolated_rejects(result, arm, tmp_path):
    with pytest.raises(LeakError):
        assert_isolated(result, arm, real_home=tmp_path)


@pytest.mark.parametrize("result,arm", [
    (ProbeResult(set(), set()), "bare"),
    (ProbeResult({"skill-creator", "imagegen", "code-review"}, set()), "bare"),
    (ProbeResult({"bruhs:bruhs", "bruhs:cook", "expect", "pdf"}, {"chrome-devtools"}), "bruhs"),
])
def test_assert_isolated_accepts(result, arm, tmp_path):
    assert_isolated(result, arm, real_home=tmp_path)


def test_assert_isolated_flags_users_own_skills_and_plugins(real_home):
    (real_home / ".claude" / "skills" / "polish").mkdir()
    (real_home / ".codex" / "skills" / ".system" / "imagegen").mkdir(parents=True)
    (real_home / ".claude" / "plugins").mkdir()
    (real_home / ".claude" / "plugins" / "installed_plugins.json").write_text(json.dumps(
        {"version": 2, "plugins": {"code-review@official": [], "bruhs@bruhs": [],
                                   "feature-dev@official": []}}))
    ok = {"simplify", "code-review", "imagegen"}  # CLI built-ins; plugin name != skill name
    assert_isolated(ProbeResult(ok, set()), "bare", real_home=real_home)
    for leaked in ("polish", "impeccable", "feature-dev:feature-dev", "code-review:code-review"):
        with pytest.raises(LeakError, match="user's own"):
            assert_isolated(ProbeResult(ok | {leaked}, set()), "bare", real_home=real_home)
    # bruhs + expect are the bruhs arm's expected install, even though the user has them too
    bruhs = ProbeResult(ok | {"bruhs:cook", "bruhs", "expect"}, {"chrome-devtools"})
    assert_isolated(bruhs, "bruhs", real_home=real_home)
    with pytest.raises(LeakError, match="user's own"):
        assert_isolated(ProbeResult(bruhs.skills | {"polish"}, bruhs.mcps), "bruhs",
                        real_home=real_home)


def _git_repo_with_bench(root: Path) -> Path:
    repo = root / "bruhs-repo"
    for rel in ("SKILL.md", "commands/cook.md", "bench/tests/reference/answer.py",
                "docs/plan.md", "practices/docs-note.md"):
        (repo / rel).parent.mkdir(parents=True, exist_ok=True)
        (repo / rel).write_text(rel)
    git = ["git", "-c", "user.name=t", "-c", "user.email=t@localhost", "-c",
           "commit.gpgsign=false"]
    subprocess.run([*git, "init", "-q"], cwd=repo, check=True)
    subprocess.run([*git, "add", "-A"], cwd=repo, check=True)
    subprocess.run([*git, "commit", "-qm", "x"], cwd=repo, check=True)
    return repo


def test_export_bruhs_drops_bench_and_docs(tmp_path, real_home):
    repo = _git_repo_with_bench(tmp_path)
    run_dir = tmp_path / "run"
    src = export_bruhs(repo, "HEAD", run_dir / "bruhs")
    assert src == run_dir / "bruhs"
    assert (src / "SKILL.md").is_file() and (src / "practices" / "docs-note.md").is_file()
    assert not (src / "bench").exists() and not (src / "docs").exists()
    for cli in ("claude", "codex"):
        sub = run_dir / cli
        sub.mkdir()
        build_home(cli, "bruhs", sub, src, real_home=real_home, env_file=_token_env(tmp_path))
    leaked = [p for p in run_dir.rglob("*") if p.name in ("bench", "docs") or "answer.py" in p.name]
    assert leaked == []


def test_build_home_refuses_unfiltered_bruhs_inside_run_dir(tmp_path, real_home):
    run_dir = tmp_path / "run"
    raw = run_dir / "bruhs"
    (raw / "bench").mkdir(parents=True)
    (raw / "SKILL.md").write_text("x")
    with pytest.raises(ValueError, match="export_bruhs"):
        build_home("codex", "bruhs", run_dir, raw, real_home=real_home)
    assert not (run_dir / "home").exists()


def test_build_home_refuses_run_dir_inside_user_home(tmp_path, bruhs_src, real_home,
                                                     monkeypatch):
    monkeypatch.setattr(homes_mod, "real_home_dir", lambda: tmp_path / "userhome")
    run_dir = tmp_path / "userhome" / "runs" / "r1"
    with pytest.raises(ValueError, match="inside the user's home"):
        build_home("codex", "bare", run_dir, bruhs_src, real_home=real_home)
    assert not run_dir.exists()


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
    need_claude_token(cli)
    if (cli, arm) not in _LIVE:
        run_dir = tmp_path_factory.mktemp(f"{cli}-{arm}")
        bruhs_src = export_bruhs(REPO_ROOT, "HEAD", run_dir / "bruhs")
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


def test_codex_probe_missing_last_message_is_a_probe_error(tmp_path, monkeypatch):
    import bruhsbench.homes as homes
    monkeypatch.setattr(homes, "_run", lambda cmd, env, cwd: "[]")
    home = tmp_path / "run" / "home"
    home.mkdir(parents=True)
    with pytest.raises(LeakError, match="no last message"):
        probe_isolation("codex", "bare", {"HOME": str(home)})


@pytest.mark.parametrize("arm", ("bare", "bruhs"))
@pytest.mark.parametrize("cli", CLIS)
def test_agents_find_the_real_playwright_browsers_and_rust_toolchains(cli, arm, tmp_path,
                                                                     bruhs_src, real_home):
    """With HOME moved, Playwright looks for its browsers and rustup for its toolchains
    in the empty run home: agents couldn't launch Playwright (pilot) or cargo. Both
    point back at the real, sandbox-read-only installs, as for grading checks; cargo's
    own CARGO_HOME (its download cache) stays in the writable run home."""
    _needs_grok(cli)
    (real_home / "Library" / "Caches" / "ms-playwright").mkdir(parents=True)
    (real_home / ".rustup").mkdir()
    env, _ = _build(cli, arm, tmp_path, bruhs_src, real_home)
    assert env["PLAYWRIGHT_BROWSERS_PATH"] == str(real_home / "Library/Caches/ms-playwright")
    assert env["RUSTUP_HOME"] == str(real_home / ".rustup")
    assert "CARGO_HOME" not in env


def test_missing_tool_installs_are_not_pointed_at(tmp_path, bruhs_src, real_home):
    env, _ = _build("codex", "bare", tmp_path, bruhs_src, real_home)
    assert "PLAYWRIGHT_BROWSERS_PATH" not in env and "RUSTUP_HOME" not in env


def test_bruhs_content_hash_covers_what_is_installed(tmp_path):
    from bruhsbench.homes import bruhs_content_hash

    src = tmp_path / "bruhs"
    (src / "commands").mkdir(parents=True)
    (src / "SKILL.md").write_text("skill\n")
    (src / "commands" / "cook.md").write_text("cook\n")
    h = bruhs_content_hash(src)
    for excluded in ("bench", ".git", "docs", ".superpowers"):  # never installed
        (src / excluded).mkdir()
        (src / excluded / "x").write_text("x\n")
    assert bruhs_content_hash(src) == h
    (src / "commands" / "cook.md").write_text("cook v2\n")
    assert bruhs_content_hash(src) != h


def test_bruhs_scripts_dir_follows_the_skill_and_tolerates_none(tmp_path):
    from bruhsbench.homes import bruhs_scripts_dir

    root = tmp_path / "bruhs"
    root.mkdir()
    assert bruhs_scripts_dir(root) == root / "scripts"  # no skill: bare-arm placeholder
    (root / "skills" / "bruhs").mkdir(parents=True)
    (root / "skills" / "bruhs" / "SKILL.md").write_text("x\n")
    assert bruhs_scripts_dir(root) == root / "skills" / "bruhs" / "scripts"
