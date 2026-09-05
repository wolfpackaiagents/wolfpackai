"""Secure filesystem, command, Git, and toolkit primitives for coding agents."""

from .command import CommandResult, CommandRunner
from .git import ApprovalMetadata, GitOperation, GitRepository, GitStatus
from .tools import CodingToolkit
from .workspace import FileList, FileRead, PatchResult, SearchMatch, SearchResult, Workspace, WorkspaceViolation

__all__ = [
    "ApprovalMetadata",
    "CodingToolkit",
    "CommandResult",
    "CommandRunner",
    "FileList",
    "FileRead",
    "GitOperation",
    "GitRepository",
    "GitStatus",
    "PatchResult",
    "SearchMatch",
    "SearchResult",
    "Workspace",
    "WorkspaceViolation",
]
