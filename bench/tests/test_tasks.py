from pathlib import Path

import pytest

from bruhsbench.tasks import TaskError, load_task, load_tasks
from bruhsbench.types import MODELS

FIX = Path(__file__).parent / "fixtures" / "tasks"


def make(root: Path, name: str, extra: str = "", category: str = "feature") -> Path:
    d = root / name
    d.mkdir(parents=True)
    (d / "task.toml").write_text(f'id = "{name}"\ncategory = "{category}"\n{extra}')
    (d / "prompt.md").write_text("do it\n")
    return d


def test_load_task_reads_toml_and_prompt():
    t = load_task(FIX / "sample-feature")
    assert t.id == "sample-feature"
    assert t.category == "feature"
    assert t.repo == Path.home() / "Documents/bryantleft/mints"
    assert t.base == "55ddb370"
    assert t.prompt == "Add a leaderboard page.\n"
    assert t.allowed_paths == ("app/**", "components/**")
    assert t.pages == ("/grade",)
    assert t.dev_cmd == "pnpm dev --port {port}"
    assert t.dev_port == 3100
    assert t.checks == {"build": "pnpm build", "test": "pnpm test"}
    assert t.setup == FIX / "sample-feature/setup.sh"
    assert t.hidden_tests == FIX / "sample-feature/hidden"
    assert t.known_issues == FIX / "sample-feature/known_issues.json"
    assert t.checklist is None
    assert t.heldout is False


def test_seeded_task_defaults(tmp_path):
    t = load_task(make(tmp_path, "seeded"))
    assert t.repo is None and t.base is None
    assert t.allowed_paths == () and t.pages == ()
    assert t.dev_cmd is None and t.dev_port is None and t.checks == {}
    assert t.setup is None and t.hidden_tests is None and t.checklist is None
    assert t.after_base is None


def test_after_base_discovered(tmp_path):
    d = make(tmp_path, "t")
    (d / "after_base.sh").write_text("true\n")
    assert load_task(d).after_base == d / "after_base.sh"


def test_toml_overrides_paths(tmp_path):
    d = make(tmp_path, "t", 'checklist = "x/cl.json"\nsetup = "bin/s.sh"\n')
    t = load_task(d)
    assert t.checklist == d / "x/cl.json"
    assert t.setup == d / "bin/s.sh"


def test_missing_prompt_raises(tmp_path):
    d = make(tmp_path, "t")
    (d / "prompt.md").unlink()
    with pytest.raises(TaskError):
        load_task(d)


def test_unknown_category_raises(tmp_path):
    with pytest.raises(TaskError):
        load_task(make(tmp_path, "t", category="bogus"))


def test_load_tasks_excludes_heldout_dir_by_default(tmp_path):
    make(tmp_path / "tasks", "open")
    make(tmp_path / "tasks-heldout", "sealed")
    assert [t.id for t in load_tasks(tmp_path)] == ["open"]
    all_ = {t.id: t for t in load_tasks(tmp_path, include_heldout=True)}
    assert set(all_) == {"open", "sealed"}
    assert all_["sealed"].heldout and not all_["open"].heldout


def test_load_tasks_excludes_heldout_toml_flag(tmp_path):
    make(tmp_path, "open")
    make(tmp_path, "flagged", "heldout = true\n")
    assert [t.id for t in load_tasks(tmp_path)] == ["open"]
    assert {t.id for t in load_tasks(tmp_path, include_heldout=True)} == {"open", "flagged"}


def test_models_constant():
    assert [(m.cli, m.model, m.effort) for m in MODELS] == [
        ("claude", "claude-opus-5-5", "high"),
        ("codex", "gpt-6.1-sol", "high"),
        ("grok", "grok-4.7", "high"),
    ]
