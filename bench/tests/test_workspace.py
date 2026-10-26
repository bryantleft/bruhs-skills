import subprocess
from dataclasses import replace
from pathlib import Path

import pytest

from bruhsbench.tasks import load_task
from bruhsbench.workspace import (
    BASE_MESSAGE,
    BASE_TAG,
    SetupFailed,
    check_task_setup,
    insert_bruhs_blocks,
    prepare_workspace,
    strip_bruhs_blocks,
)

GIT = ["git", "-c", "user.name=t", "-c", "user.email=t@localhost", "-c", "commit.gpgsign=false",
       "-c", "tag.gpgsign=false"]


def git(cwd: Path, *args: str) -> str:
    return subprocess.run(
        [*GIT, *args], cwd=cwd, check=True, capture_output=True, text=True
    ).stdout


def make_repo(root: Path) -> tuple[Path, str]:
    repo = root / "src-repo"
    repo.mkdir()
    git(repo, "init", "-q", "-b", "main")
    (repo / "package.json").write_text(
        '{"name":"x","dependencies":{"next":"15.0.0","react":"19.0.0"}}\n'
    )
    (repo / "app.txt").write_text("hello\n")
    (repo / "CLAUDE.md").write_text("# CLAUDE.md\n\nHand-written rule.\n")
    git(repo, "add", "-A")
    git(repo, "commit", "-q", "-m", "init")
    base = git(repo, "rev-parse", "HEAD").strip()
    # a later commit so checkout of base is observable
    (repo / "app.txt").write_text("later\n")
    git(repo, "commit", "-qam", "later")
    return repo, base


def make_task(root: Path, repo: Path | None, base: str | None, setup: str | None = None,
              after_base: str | None = None):
    d = root / "task-x"
    d.mkdir()
    (d / "task.toml").write_text('id = "task-x"\ncategory = "feature"\n')
    (d / "prompt.md").write_text("do it\n")
    t = load_task(d)
    if setup is not None:
        (d / "setup.sh").write_text(setup)
    if after_base is not None:
        (d / "after_base.sh").write_text(after_base)
    return replace(t, repo=repo, base=base, setup=(d / "setup.sh") if setup is not None else None,
                   after_base=(d / "after_base.sh") if after_base is not None else None)


BLOCKS = (
    "<!-- bruhs:state:begin v1 -->\nstuff\n<!-- bruhs:state:end -->\n\n"
    "<!-- bruhs:rules:begin v1 -->\nrules\n<!-- bruhs:rules:end -->\n"
)


def test_strip_removes_all_kinds_and_empty_heading():
    text = "# CLAUDE.md\n\nHand-written rule.\n\n## bruhs-managed\n\n" + BLOCKS
    assert strip_bruhs_blocks(text) == "# CLAUDE.md\n\nHand-written rule.\n"


def test_strip_keeps_heading_with_other_content():
    text = "## bruhs-managed\n\nmine\n\n" + BLOCKS
    out = strip_bruhs_blocks(text)
    assert "bruhs:" not in out
    assert "## bruhs-managed" in out and "mine" in out


def test_strip_noop_without_markers():
    text = "# Title\n\n## bruhs-managed\n\nnot ours\n\n\n"
    assert strip_bruhs_blocks(text) == text


def test_strip_only_blocks_leaves_empty():
    assert strip_bruhs_blocks("## bruhs-managed\n\n" + BLOCKS).strip() == ""


def test_insert_creates_blocks(tmp_path):
    repo, _ = make_repo(tmp_path)
    insert_bruhs_blocks(repo)
    text = (repo / "CLAUDE.md").read_text()
    assert "bruhs:state:begin" in text and "bruhs:rules:begin" in text
    assert "integrations" not in text
    assert "Hand-written rule." in text
    assert (repo / "AGENTS.md").exists()


def test_insert_with_no_detected_stack_writes_state_only(tmp_path):
    root = tmp_path / "plain"
    root.mkdir()
    (root / "notes.txt").write_text("no manifest here\n")
    insert_bruhs_blocks(root)
    text = (root / "CLAUDE.md").read_text()
    assert "bruhs:state:begin" in text
    assert "bruhs:rules:begin" not in text


def test_bare_and_bruhs_differ_only_in_blocks(tmp_path):
    repo, base = make_repo(tmp_path)
    task = make_task(tmp_path, repo, base)
    bare = prepare_workspace(task, "bare", tmp_path / "bare")
    bruhs = prepare_workspace(task, "bruhs", tmp_path / "bruhs")
    out = subprocess.run(
        ["diff", "-rq", "--exclude=.git", str(bare), str(bruhs)],
        capture_output=True, text=True,
    ).stdout
    changed = {Path(l.split()[1] if l.startswith("Files") else l.split()[-1]).name
               for l in out.splitlines()}
    assert changed <= {"CLAUDE.md", "AGENTS.md"} and changed
    assert (bare / "app.txt").read_text() == "hello\n"  # base checked out
    assert "bruhs:" not in (bare / "CLAUDE.md").read_text()
    assert git(bare, "rev-parse", BASE_TAG).strip() == git(bare, "rev-parse", "HEAD").strip()
    assert git(bare, "log", "-1", "--format=%s").strip() == BASE_MESSAGE
    assert git(bruhs, "status", "--porcelain") == ""


def test_bruhs_json_removed(tmp_path):
    repo, base = make_repo(tmp_path)
    (repo / ".claude").mkdir()
    (repo / ".claude/bruhs.json").write_text("{}")
    git(repo, "add", "-A")
    git(repo, "commit", "-qm", "cfg")
    base = git(repo, "rev-parse", "HEAD").strip()
    ws = prepare_workspace(make_task(tmp_path, repo, base), "bare", tmp_path / "ws")
    assert not (ws / ".claude/bruhs.json").exists()


def test_remotes_removed(tmp_path):
    repo, base = make_repo(tmp_path)
    ws = prepare_workspace(make_task(tmp_path, repo, base), "bare", tmp_path / "ws")
    assert git(ws, "remote").strip() == ""


def test_repo_checkout_holds_only_base_history(tmp_path):
    repo, base = make_repo(tmp_path)
    later = git(repo, "rev-parse", "HEAD").strip()
    ws = prepare_workspace(make_task(tmp_path, repo, base[:10]), "bare", tmp_path / "ws")
    assert (ws / "app.txt").read_text() == "hello\n"
    assert git(ws, "rev-parse", "HEAD~1").strip() == base
    # the future solution is unreachable and absent; nothing names the source repo
    missing = subprocess.run([*GIT, "cat-file", "-e", later], cwd=ws, capture_output=True)
    assert missing.returncode != 0
    assert git(ws, "for-each-ref", "--format=%(refname)").split() == [f"refs/tags/{BASE_TAG}"]
    for f in (ws / ".git").rglob("*"):
        if f.is_file() and "objects" not in f.parts:
            assert str(repo) not in f.read_text(errors="replace"), f


def test_seeded_task_uses_fixture(tmp_path):
    task = make_task(tmp_path, None, None)
    (task.dir / "fixture").mkdir()
    (task.dir / "fixture/a.txt").write_text("a\n")
    ws = prepare_workspace(task, "bare", tmp_path / "ws")
    assert (ws / "a.txt").read_text() == "a\n"
    assert git(ws, "log", "-1", "--format=%s").strip() == BASE_MESSAGE
    assert git(ws, "rev-parse", BASE_TAG).strip()


def test_seeded_missing_fixture_errors(tmp_path):
    task = make_task(tmp_path, None, None)
    with pytest.raises(FileNotFoundError, match="fixture"):
        prepare_workspace(task, "bare", tmp_path / "ws")


def test_setup_runs_in_dest(tmp_path):
    repo, base = make_repo(tmp_path)
    task = make_task(tmp_path, repo, base, setup="touch ran.marker\n")
    ws = prepare_workspace(task, "bare", tmp_path / "ws")
    assert (ws / "ran.marker").exists()


def test_setup_failure_raises(tmp_path):
    repo, base = make_repo(tmp_path)
    task = make_task(tmp_path, repo, base, setup="exit 1\n")
    with pytest.raises(SetupFailed):
        prepare_workspace(task, "bare", tmp_path / "ws")


def test_setup_failure_excludes_task(tmp_path):
    repo, base = make_repo(tmp_path)
    bad = make_task(tmp_path, repo, base, setup="exit 1\n")
    assert check_task_setup(bad, tmp_path / "scratch") is False


def test_setup_failing_only_in_bruhs_arm_excludes_task(tmp_path):
    repo, base = make_repo(tmp_path)
    # setup runs after the bruhs blocks are inserted, so it can tell the arms apart
    bad = make_task(tmp_path, repo, base, setup="! grep -q bruhs:state CLAUDE.md\n")
    prepare_workspace(bad, "bare", tmp_path / "ws")  # bare arm alone is fine
    assert check_task_setup(bad, tmp_path / "scratch") is False


def test_check_task_setup_true(tmp_path):
    repo, base = make_repo(tmp_path)
    good = make_task(tmp_path, repo, base, setup="true\n")
    assert check_task_setup(good, tmp_path / "scratch") is True


def test_setup_output_is_part_of_base(tmp_path):
    repo, base = make_repo(tmp_path)
    task = make_task(tmp_path, repo, base, setup="echo x > generated.txt\n")
    ws = prepare_workspace(task, "bare", tmp_path / "ws")
    assert (ws / "generated.txt").exists()
    git(ws, "add", "-A")
    assert git(ws, "diff", "--cached", BASE_TAG) == ""


def test_after_base_leaves_uncommitted_work(tmp_path):
    repo, base = make_repo(tmp_path)
    task = make_task(tmp_path, repo, base, setup="echo dep > installed.txt\n",
                     after_base="echo wip > staged.txt && git add staged.txt\n"
                                "echo changed > app.txt\necho new > untracked.txt\n")
    ws = prepare_workspace(task, "bare", tmp_path / "ws")
    # setup output is in base; after_base output is not
    assert git(ws, "show", f"{BASE_TAG}:installed.txt") == "dep\n"
    assert git(ws, "rev-parse", "HEAD") == git(ws, "rev-parse", BASE_TAG)
    status = git(ws, "status", "--porcelain").splitlines()
    assert sorted(status) == [" M app.txt", "?? untracked.txt", "A  staged.txt"]


def test_after_base_failure_raises(tmp_path):
    repo, base = make_repo(tmp_path)
    task = make_task(tmp_path, repo, base, after_base="exit 3\n")
    with pytest.raises(SetupFailed, match="after_base.sh exited 3"):
        prepare_workspace(task, "bare", tmp_path / "ws")


def test_future_commits_unreachable(tmp_path):
    repo, base = make_repo(tmp_path)
    later = git(repo, "rev-parse", "HEAD").strip()
    git(repo, "tag", "v-later")
    assert later != base
    ws = prepare_workspace(make_task(tmp_path, repo, base), "bare", tmp_path / "ws")
    revs = git(ws, "rev-list", "--all").split()
    assert later not in revs and base in revs and len(revs) == 2
    assert git(ws, "for-each-ref", "--format=%(refname)").split() == [f"refs/tags/{BASE_TAG}"]
    assert subprocess.run(["git", "cat-file", "-e", later], cwd=ws).returncode != 0


def test_prepare_fails_fast_when_tmpdirs_would_be_too_long(tmp_path, monkeypatch):
    from bruhsbench.sandbox import TmpDirTooLong

    d = tmp_path / "task"
    (d / "fixture").mkdir(parents=True)
    (d / "task.toml").write_text('id = "t"\ncategory = "feature"\n')
    (d / "prompt.md").write_text("p\n")
    monkeypatch.setenv("BRUHSBENCH_TMP", "/private/tmp/" + "x" * 70)
    with pytest.raises(TmpDirTooLong, match="77"):
        prepare_workspace(load_task(d), "bare", tmp_path / "ws")
    assert not (tmp_path / "ws").exists()


HINTS = ("bench", "bruhs", "bare")


@pytest.mark.parametrize("seeded", (True, False))
def test_workspace_git_metadata_names_neither_benchmark_nor_arm(tmp_path, seeded):
    """R42: author, messages, tags and branches an agent sees in git are neutral, in both
    arms, for seeded fixtures and real-repo checkouts."""
    for arm in ("bare", "bruhs"):
        root = tmp_path / arm
        root.mkdir()
        if seeded:
            task = make_task(root, None, None, setup="echo dep > installed.txt\n")
            (task.dir / "fixture").mkdir()
            (task.dir / "fixture" / "a.txt").write_text("a\n")
        else:
            repo, base = make_repo(root)
            task = make_task(root, repo, base, setup="echo dep > installed.txt\n")
        ws = prepare_workspace(task, arm, root / "ws")
        seen = "\n".join([git(ws, "log", "--format=%an %ae %cn %ce %s %b", "--all"),
                          git(ws, "tag"), git(ws, "branch", "-a"),
                          git(ws, "for-each-ref", "--format=%(refname)")]).lower()
        assert not [h for h in HINTS if h in seen], (arm, seen)
        assert git(ws, "rev-parse", BASE_TAG).strip() == git(ws, "rev-parse", "HEAD").strip()
