"""Wolfpack Toolkit adapter for coding-agent primitives."""

from __future__ import annotations

from pathlib import Path

from ..tools.toolkit import Toolkit
from .command import CommandRunner
from .git import GitRepository
from .workspace import Workspace


class CodingToolkit(Toolkit):
    def __init__(self, workspace: Workspace) -> None:
        super().__init__("coding")
        self.workspace = workspace
        self.commands = CommandRunner(workspace)
        self.git = GitRepository(workspace, runner=self.commands)
        self.register(self.read_file, description="Read a UTF-8 file within the workspace.")
        self.register(self.list_files, description="List bounded workspace paths.")
        self.register(self.search, description="Search bounded workspace text files.")
        self.register(self.apply_patch, description="Apply a unified patch within the workspace.", requires_confirmation=True)
        self.register(self.run_command, description="Run an argv command without a shell.", requires_confirmation=True)
        self.register(self.git_status, description="Read Git working tree status.")
        self.register(self.git_diff, description="Read the Git working tree diff.")
        self.register(self.git_apply_patch, description="Apply a Git patch.", requires_confirmation=True)
        self.register(self.git_worktree_add, description="Create a Git worktree.", requires_confirmation=True)
        self.register(self.git_commit, description="Commit staged Git changes.", requires_confirmation=True)

    def read_file(self, path: str) -> dict:
        return self.workspace.read_file(path).__dict__

    def list_files(self, path: str = ".") -> dict:
        return self.workspace.list_files(path).__dict__

    def search(self, pattern: str, path: str = ".") -> dict:
        return self.workspace.search(pattern, path).__dict__

    def apply_patch(self, patch: str) -> dict:
        return self.workspace.apply_patch(patch).__dict__

    def run_command(self, command: list[str], cwd: str = ".") -> dict:
        return self.commands.run(command, cwd=cwd).__dict__

    def git_status(self) -> dict:
        return self.git.status().__dict__

    def git_diff(self, staged: bool = False) -> dict:
        return self.git.diff(staged=staged).__dict__

    def git_apply_patch(self, patch: str) -> dict:
        return self.git.apply_patch(patch).__dict__

    def git_worktree_add(self, path: str, branch: str | None = None) -> dict:
        return self.git.worktree_add(Path(path), branch).__dict__

    def git_commit(self, message: str) -> dict:
        return self.git.commit(message).__dict__
