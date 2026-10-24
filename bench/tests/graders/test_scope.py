from bruhsbench.graders import scope
from bruhsbench.graders.scope import parse_diff

from conftest import make_task


def test_scope_counts_lines_outside_allowed(tmp_path, make_run):
    task = make_task(tmp_path, allowed_paths=("app/**", "components/*.tsx"))
    run = make_run({"app/page.tsx": "a\nb\n", "lib/util.ts": "x\ny\nz\n", "README.md": "r\n"})
    run.write({
        "app/page.tsx": "a\nB\nc\n",           # allowed: -1 +2
        "components/Button.tsx": "btn\n",      # allowed (new)
        "lib/util.ts": "x\nY\nz\n",            # outside: -1 +1 = 2
        "lib/new.ts": "1\n2\n3\n",             # outside: +3
    })
    (run.workspace / "README.md").unlink()     # outside: -1
    g = scope.grade(task, run.finish())
    assert g["files_outside"] == ["README.md", "lib/new.ts", "lib/util.ts"]
    assert g["lines_outside"] == 6
    assert g["files_changed"] == 5
    assert g["lines_changed"] == 6 + 3 + 1


def test_scope_everything_allowed_when_no_globs(tmp_path, make_run):
    run = make_run({"a.txt": "a\n"})
    run.write({"a.txt": "b\n", "z/y.txt": "c\n"})
    g = scope.grade(make_task(tmp_path), run.finish())
    assert (g["files_outside"], g["lines_outside"]) == ([], 0)


def test_parse_diff_renames_and_binary():
    diff = (
        "diff --git a/old.txt b/new.txt\n"
        "similarity index 100%\n"
        "rename from old.txt\n"
        "rename to new.txt\n"
        "diff --git a/img.png b/img.png\n"
        "new file mode 100644\n"
        "index 0000000..1111111\n"
        "GIT binary patch\n"
        "literal 3\n"
        "Kc${NkU;qFB0RR91\n"
        "\n"
        "literal 0\n"
        "HcmV?d00001\n"
        "\n"
        "diff --git \"a/sp ace.txt\" \"b/sp ace.txt\"\n"
        "--- \"a/sp ace.txt\"\n"
        "+++ \"b/sp ace.txt\"\n"
        "@@ -1 +1 @@\n"
        "--- dashes\n"
        "+++ pluses\n"
    )
    files = parse_diff(diff)
    assert [(f.paths, f.lines) for f in files] == [
        (("old.txt", "new.txt"), 0), (("img.png",), 0), (("sp ace.txt",), 2)]


def test_scope_unquoted_paths_with_spaces_from_real_git_diff(tmp_path, make_run):
    task = make_task(tmp_path, allowed_paths=("assets/*",))
    run = make_run({"assets/keep.txt": "k\n"})
    (run.workspace / "assets" / "my logo.png").write_bytes(b"\x89PNG\x00\x01\x02")
    run.write({"my notes.txt": "a\nb\n", "assets/new b/x.txt": "x\n"})
    run_dir = run.finish()
    assert 'diff --git a/assets/my logo.png b/assets/my logo.png' in (
        run_dir / "diff.patch").read_text(errors="replace")
    files = {f.paths: f.lines for f in parse_diff((run_dir / "diff.patch").read_text())}
    assert files == {("assets/my logo.png",): 0, ("assets/new b/x.txt",): 1,
                     ("my notes.txt",): 2}
    g = scope.grade(task, run_dir)
    assert (g["files_outside"], g["lines_outside"]) == (["my notes.txt"], 2)


def test_parse_diff_malformed_header_has_no_paths():
    files = parse_diff("diff --git garbage\n@@ -1 +1 @@\n+x\n")
    assert [(f.paths, f.lines) for f in files] == [((), 1)]
