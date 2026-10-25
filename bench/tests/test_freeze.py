"""Task freeze: what is hashed, the frozen files, and the run-time check."""

from __future__ import annotations

import json

import pytest

from bruhsbench import freeze as F
from bruhsbench.tasks import load_task


@pytest.fixture
def frozen_files(tmp_path, monkeypatch):
    pub, priv = tmp_path / "frozen.sha256", tmp_path / "tasks-private" / "_frozen.sha256"
    monkeypatch.setattr(F, "FROZEN_PUBLIC", pub)
    monkeypatch.setattr(F, "FROZEN_PRIVATE", priv)
    return pub, priv


def _write(path, text="x\n"):
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(text)


def seeded(tmp_path, tid="seed-a"):
    d = tmp_path / "tasks" / tid
    _write(d / "task.toml", f'id = "{tid}"\ncategory = "feature"\n')
    _write(d / "prompt.md", "do it\n")
    _write(d / "fixture" / "app.txt", "hello\n")
    _write(d / "hidden" / "tests" / "h.test.ts", "test\n")
    return load_task(d)


def private(tmp_path, tid="real-a"):
    root = tmp_path / "tasks-private"
    d = root / tid
    _write(d / "task.toml", f'id = "{tid}"\ncategory = "ui"\nrepo = "/nowhere"\nbase = "abc"\n')
    _write(d / "prompt.md", "make it nice\n")
    _write(d / "setup.sh", 'bash "$(dirname "$0")/../_shared/fam/install.sh"\n')
    _write(d / "checklist.json", '{"items": []}\n')
    _write(d / "checklist_src.py", "ITEMS = []\n")
    _write(d / "NOTES.md", "notes\n")
    _write(d / "__pycache__" / "checklist_src.cpython-312.pyc", "pyc")
    _write(d / ".DS_Store", "ds")
    (d / "seed").mkdir()
    (d / "seed" / "db.sqlite3").write_bytes(b"\0" * (3 << 20))
    _write(root / "_shared" / "fam" / "install.sh", "pnpm install\n")
    _write(root / "_shared" / "fam" / "NOTES.md", "shared notes\n")
    _write(root / "_shared" / "other" / "dev.sh", "unrelated\n")
    return load_task(d)


def test_manifest_follows_the_documented_rule(tmp_path):
    assert sorted(F.manifest(private(tmp_path))) == [
        "shared/fam/install.sh", "task/checklist.json", "task/prompt.md",
        "task/seed/db.sqlite3", "task/setup.sh", "task/task.toml"]
    assert sorted(F.manifest(seeded(tmp_path))) == [
        "task/fixture/app.txt", "task/hidden/tests/h.test.ts", "task/prompt.md",
        "task/task.toml"]


@pytest.mark.parametrize("rel, changes", [
    ("prompt.md", True), ("checklist.json", True), ("task.toml", True),
    ("seed/db.sqlite3", True), ("../_shared/fam/install.sh", True),
    ("hidden/new.spec.ts", True),
    ("NOTES.md", False), ("checklist_src.py", False), ("__pycache__/x.pyc", False),
    ("../_shared/other/dev.sh", False), ("../_shared/fam/NOTES.md", False),
])
def test_what_changes_the_hash(tmp_path, rel, changes):
    task = private(tmp_path)
    before = F.task_hash(task)
    _write((task.dir / rel), "edited\n")
    F._file_hashes.clear()
    assert (F.task_hash(task) != before) is changes


def test_symlinks_are_hashed_as_links_never_followed(tmp_path):
    task = seeded(tmp_path)
    outside = tmp_path / "outside"
    _write(outside / "secret.txt", "a\n")
    (task.dir / "fixture" / "link").symlink_to(outside)
    h = F.task_hash(task)
    assert "task/fixture/link" in F.manifest(task)
    assert not any("secret" in label for label in F.manifest(task))
    _write(outside / "secret.txt", "b\n")
    assert F.task_hash(task) == h


def test_freeze_then_check(tmp_path, frozen_files):
    pub, priv = frozen_files
    s, p = seeded(tmp_path), private(tmp_path)
    res = F.freeze([s, p])
    assert sorted(res.added) == [p.id, s.id]
    assert F.read_frozen(pub) == {s.id: F.task_hash(s)}
    assert F.read_frozen(priv) == {p.id: F.task_hash(p)}
    assert json.loads(priv.with_suffix(".manifest.json").read_text())[p.id]
    status = F.check([s, p])
    assert status.unfrozen == {} and status.hashes == {s.id: F.task_hash(s),
                                                       p.id: F.task_hash(p)}
    _write(p.dir / "checklist.json", '{"items": [{"id": "x"}]}\n')
    _write(s.dir / "hidden" / "more.ts", "t\n")
    status = F.check([s, p])
    assert "changed task/checklist.json" in status.unfrozen[p.id]
    assert "added task/hidden/more.ts" in status.unfrozen[s.id]
    assert F.check([seeded(tmp_path, "seed-new")]).unfrozen["seed-new"].startswith("not frozen")
    assert F.freeze([s, p]).changed == [s.id, p.id]
    assert F.check([s, p]).unfrozen == {}


def test_partial_refreeze_keeps_other_entries_and_full_freeze_drops_stale(tmp_path,
                                                                           frozen_files):
    pub, _ = frozen_files
    a, b = seeded(tmp_path, "seed-a"), seeded(tmp_path, "seed-b")
    F.freeze([a, b])
    old_b = F.read_frozen(pub)["seed-b"]
    _write(a.dir / "prompt.md", "new\n")
    _write(b.dir / "prompt.md", "new too\n")
    res = F.freeze([a, b], only=["seed-a"])
    assert res.changed == ["seed-a"] and F.read_frozen(pub)["seed-b"] == old_b
    assert list(F.check([a, b]).unfrozen) == ["seed-b"]
    assert F.freeze([a]).dropped == ["seed-b"] and list(F.read_frozen(pub)) == ["seed-a"]


def test_malformed_frozen_file_names_file_and_line(tmp_path, frozen_files):
    pub, _ = frozen_files
    pub.write_text("# header\n" + "a" * 64 + "  seed-a\nnot a hash line\n")
    with pytest.raises(F.FreezeError, match=r"frozen.sha256:3: malformed line"):
        F.read_frozen(pub)
    pub.write_text("")
    pub.with_suffix(".manifest.json").write_text("{oops")
    with pytest.raises(F.FreezeError, match=r"frozen.manifest.json:1: malformed manifest"):
        F.check([seeded(tmp_path)])


def test_pinned_mismatches_and_matrices_using(tmp_path):
    a, b = seeded(tmp_path, "seed-a"), seeded(tmp_path, "seed-b")
    pinned = {"seed-a": F.task_hash(a)}
    assert F.pinned_mismatches([a], pinned) == {}
    assert "not in matrix.json" in F.pinned_mismatches([b], pinned)["seed-b"]
    _write(a.dir / "prompt.md", "changed\n")
    assert "changed since its runs ran" in F.pinned_mismatches([a], pinned)["seed-a"]
    results = tmp_path / "results"
    _write(results / "full" / "matrix.json", json.dumps(
        {"tasks": ["seed-a", "seed-b"], "task_hashes": {"seed-a": "old", "seed-b": "hb"}}))
    _write(results / "legacy" / "matrix.json", json.dumps({"tasks": ["seed-b"]}))
    assert F.matrices_using({"seed-a": "new", "seed-b": "hb"}, results) == {
        "seed-a": [str(results / "full")], "seed-b": [str(results / "legacy")]}
