"""Deterministic, provider-free demonstration of coding-agent primitives."""

from __future__ import annotations

import subprocess
import tempfile
from dataclasses import dataclass
from pathlib import Path

from wolfpack.coding import CodingToolkit, GitRepository, Workspace


@dataclass(frozen=True)
class DemoResult:
    read_content: str
    changed_files: tuple[str, ...]
    git_changed: tuple[str, ...]
    approval_operation: str
    requires_confirmation: bool


def _git(root: Path, *arguments: str) -> None:
    subprocess.run(["git", *arguments], cwd=root, check=True, capture_output=True)


def run_demo() -> DemoResult:
    with tempfile.TemporaryDirectory() as directory:
        root = Path(directory)
        _git(root, "init")
        _git(root, "config", "user.email", "example@example.invalid")
        _git(root, "config", "user.name", "Wolfpack Example")
        (root / "message.txt").write_text("before\n", encoding="utf-8")
        _git(root, "add", "message.txt")
        _git(root, "commit", "-m", "initial")

        workspace = Workspace(root)
        toolkit = CodingToolkit(workspace)
        read = workspace.read_file("message.txt")
        patch = """--- a/message.txt
+++ b/message.txt
@@ -1 +1 @@
-before
+after
"""
        changed = workspace.apply_patch(patch)
        status = GitRepository(workspace).status()
        approval = toolkit.functions["git_commit"]
        return DemoResult(read.content, changed.changed_files, status.changed, "git_commit", approval.requires_confirmation)


if __name__ == "__main__":
    print(run_demo())
