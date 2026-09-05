"""Git primitives with stable metadata suitable for human approval UIs."""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path

from .command import CommandResult, CommandRunner
from .workspace import Workspace


@dataclass(frozen=True)
class ApprovalMetadata:
    operation: str
    required: bool
    command: tuple[str, ...]
    summary: str


@dataclass(frozen=True)
class GitOperation:
    result: CommandResult
    approval: ApprovalMetadata

    @property
    def output(self) -> str:
        return self.result.output

    @property
    def returncode(self) -> int | None:
        return self.result.returncode


@dataclass(frozen=True)
class GitStatus:
    branch: str
    changed: tuple[str, ...]
    result: CommandResult


class GitRepository:
    def __init__(self, workspace: Workspace, *, runner: CommandRunner | None = None) -> None:
        self.workspace = workspace
        self.runner = runner or CommandRunner(workspace)
        probe = self._run("rev-parse", "--is-inside-work-tree")
        if probe.returncode != 0 or probe.output.strip() != "true":
            raise ValueError("Workspace root is not inside a Git worktree")

    def status(self) -> GitStatus:
        result = self._run("status", "--porcelain=v1", "--branch")
        lines = result.output.splitlines()
        branch = lines[0][3:] if lines and lines[0].startswith("## ") else ""
        changed = tuple(line[3:] for line in lines[1:] if len(line) > 3)
        return GitStatus(branch, changed, result)

    def diff(self, *, staged: bool = False) -> GitOperation:
        arguments = ("diff", "--cached") if staged else ("diff",)
        return self._operation("git_diff", False, "Show staged diff" if staged else "Show working tree diff", *arguments)

    def apply_patch(self, patch: str) -> GitOperation:
        if len(patch.encode("utf-8")) > self.workspace.max_patch_bytes:
            raise ValueError("Patch exceeds workspace byte limit")
        return self._operation("git_apply_patch", True, "Apply a Git patch to the working tree", "apply", "--whitespace=nowarn", input_text=patch)

    def worktree_add(self, path: str | Path, branch: str | None = None) -> GitOperation:
        target = self.workspace.resolve(path)
        arguments = ["worktree", "add", self.workspace.relative(target)]
        if branch:
            arguments.append(branch)
        return self._operation("git_worktree_add", True, f"Create worktree at {self.workspace.relative(target)}", *arguments)

    def commit(self, message: str) -> GitOperation:
        if not message.strip():
            raise ValueError("Commit message must not be empty")
        return self._operation("git_commit", True, "Commit currently staged changes", "commit", "-m", message)

    def _run(self, *arguments: str, input_text: str | None = None) -> CommandResult:
        return self.runner.run(("git", *arguments), input_text=input_text)

    def _operation(self, operation: str, required: bool, summary: str, *arguments: str, input_text: str | None = None) -> GitOperation:
        command = ("git", *arguments)
        return GitOperation(self.runner.run(command, input_text=input_text), ApprovalMetadata(operation, required, command, summary))
