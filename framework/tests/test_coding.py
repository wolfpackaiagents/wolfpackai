"""Contract tests for the coding-agent primitives."""

from __future__ import annotations

import subprocess
import sys
from pathlib import Path

import pytest

from wolfpack.coding import CommandRunner, GitRepository, Workspace, WorkspaceViolation


def git(repo: Path, *args: str) -> None:
    subprocess.run(["git", *args], cwd=repo, check=True, capture_output=True)


@pytest.fixture
def repository(tmp_path: Path) -> Path:
    git(tmp_path, "init")
    git(tmp_path, "config", "user.email", "tests@example.invalid")
    git(tmp_path, "config", "user.name", "Wolfpack Tests")
    (tmp_path / "hello.txt").write_text("hello\n", encoding="utf-8")
    git(tmp_path, "add", "hello.txt")
    git(tmp_path, "commit", "-m", "initial")
    return tmp_path


def test_workspace_confines_paths_and_symlink_escapes(tmp_path: Path) -> None:
    root = tmp_path / "workspace"
    root.mkdir()
    workspace = Workspace(root, max_read_bytes=4)
    (workspace.root / "small.txt").write_text("hello", encoding="utf-8")
    outside = tmp_path / "outside.txt"
    outside.write_text("secret", encoding="utf-8")
    (workspace.root / "escape").symlink_to(outside)

    assert workspace.read_file("small.txt").content == "hell"
    assert workspace.read_file("small.txt").truncated is True
    with pytest.raises(WorkspaceViolation):
        workspace.read_file("../outside.txt")
    with pytest.raises(WorkspaceViolation):
        workspace.read_file("escape")


def test_workspace_bounded_list_search_and_patch(repository: Path) -> None:
    workspace = Workspace(repository, max_list_entries=1, max_search_results=1)
    (repository / "second.txt").write_text("needle\nneedle\n", encoding="utf-8")

    listing = workspace.list_files(".")
    search = workspace.search("needle")
    patch = """--- a/hello.txt
+++ b/hello.txt
@@ -1 +1 @@
-hello
+updated
"""

    assert listing.truncated is True
    assert len(search.matches) == 1
    assert search.truncated is True
    assert workspace.apply_patch(patch).changed_files == ("hello.txt",)
    assert (repository / "hello.txt").read_text(encoding="utf-8") == "updated\n"


def test_command_runner_uses_argv_timeout_and_output_limit(repository: Path) -> None:
    runner = CommandRunner(Workspace(repository), default_timeout_seconds=0.5, max_output_bytes=5)

    output = runner.run([sys.executable, "-c", "print('abcdefgh')"])
    timed_out = runner.run([sys.executable, "-c", "import time; time.sleep(1)"], timeout_seconds=0.1)

    assert output.command == (sys.executable, "-c", "print('abcdefgh')")
    assert output.output == "abcde"
    assert output.output_truncated is True
    assert timed_out.timed_out is True


def test_git_operations_return_approval_metadata_and_change_repository(repository: Path) -> None:
    workspace = Workspace(repository)
    git_repo = GitRepository(workspace)
    (repository / "hello.txt").write_text("changed\n", encoding="utf-8")

    status = git_repo.status()
    diff = git_repo.diff()
    git(repository, "add", "hello.txt")
    commit = git_repo.commit("change greeting")

    assert status.changed == ("hello.txt",)
    assert "-hello" in diff.output
    assert commit.approval.required is True
    assert commit.approval.operation == "git_commit"
    assert commit.result.returncode == 0


def test_git_apply_patch_and_worktree_are_confined_and_annotated(repository: Path) -> None:
    workspace = Workspace(repository)
    git_repo = GitRepository(workspace)
    patch = """diff --git a/added.txt b/added.txt
new file mode 100644
index 0000000..ce01362
--- /dev/null
+++ b/added.txt
@@ -0,0 +1 @@
+added
"""

    applied = git_repo.apply_patch(patch)
    worktree = git_repo.worktree_add("linked")

    assert applied.returncode == 0
    assert applied.approval.required is True
    assert (repository / "added.txt").read_text(encoding="utf-8") == "added\n"
    assert worktree.returncode == 0
    assert worktree.approval.operation == "git_worktree_add"
    assert (repository / "linked").is_dir()


def test_coding_toolkit_marks_mutating_operations_for_confirmation(repository: Path) -> None:
    from wolfpack.coding import CodingToolkit

    toolkit = CodingToolkit(Workspace(repository))

    assert toolkit.functions["read_file"].requires_confirmation is False
    for name in ("apply_patch", "run_command", "git_apply_patch", "git_worktree_add", "git_commit"):
        assert toolkit.functions[name].requires_confirmation is True
