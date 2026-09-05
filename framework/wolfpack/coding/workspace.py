"""Bounded filesystem access confined to one resolved workspace root."""

from __future__ import annotations

import re
from dataclasses import dataclass
from pathlib import Path


class WorkspaceViolation(ValueError):
    """Raised when an operation would access data outside the workspace."""


@dataclass(frozen=True)
class FileRead:
    path: str
    content: str
    truncated: bool


@dataclass(frozen=True)
class FileList:
    paths: tuple[str, ...]
    truncated: bool


@dataclass(frozen=True)
class SearchMatch:
    path: str
    line: int
    content: str


@dataclass(frozen=True)
class SearchResult:
    matches: tuple[SearchMatch, ...]
    truncated: bool


@dataclass(frozen=True)
class PatchResult:
    changed_files: tuple[str, ...]


class Workspace:
    """A root directory with path, size, and result-count safety limits."""

    def __init__(
        self,
        root: str | Path,
        *,
        max_read_bytes: int = 64 * 1024,
        max_list_entries: int = 1_000,
        max_search_results: int = 1_000,
        max_patch_bytes: int = 256 * 1024,
    ) -> None:
        self.root = Path(root).resolve()
        if not self.root.is_dir():
            raise ValueError(f"Workspace root is not a directory: {root}")
        if min(max_read_bytes, max_list_entries, max_search_results, max_patch_bytes) < 1:
            raise ValueError("Workspace limits must be positive")
        self.max_read_bytes = max_read_bytes
        self.max_list_entries = max_list_entries
        self.max_search_results = max_search_results
        self.max_patch_bytes = max_patch_bytes

    def resolve(self, path: str | Path = ".") -> Path:
        candidate = Path(path)
        resolved = (candidate if candidate.is_absolute() else self.root / candidate).resolve()
        try:
            resolved.relative_to(self.root)
        except ValueError as error:
            raise WorkspaceViolation(f"Path escapes workspace: {path}") from error
        return resolved

    def relative(self, path: Path) -> str:
        return path.relative_to(self.root).as_posix()

    def read_file(self, path: str | Path, *, max_bytes: int | None = None) -> FileRead:
        target = self.resolve(path)
        if not target.is_file():
            raise WorkspaceViolation(f"Not a regular file: {path}")
        limit = self._limit(max_bytes, self.max_read_bytes)
        with target.open("rb") as source:
            data = source.read(limit + 1)
        return FileRead(self.relative(target), data[:limit].decode("utf-8", errors="replace"), len(data) > limit)

    def list_files(self, path: str | Path = ".", *, max_entries: int | None = None) -> FileList:
        target = self.resolve(path)
        if not target.is_dir():
            raise WorkspaceViolation(f"Not a directory: {path}")
        limit = self._limit(max_entries, self.max_list_entries)
        paths: list[str] = []
        for item in sorted(target.rglob("*")):
            # Resolve each item so a symlink cannot disclose an external target.
            try:
                safe_item = self.resolve(item)
            except WorkspaceViolation:
                continue
            paths.append(self.relative(safe_item))
            if len(paths) > limit:
                return FileList(tuple(paths[:limit]), True)
        return FileList(tuple(paths), False)

    def search(self, pattern: str, path: str | Path = ".", *, max_results: int | None = None) -> SearchResult:
        if not pattern:
            raise ValueError("Search pattern must not be empty")
        expression = re.compile(pattern)
        target = self.resolve(path)
        limit = self._limit(max_results, self.max_search_results)
        matches: list[SearchMatch] = []
        files = [target] if target.is_file() else sorted(target.rglob("*"))
        for item in files:
            try:
                safe_item = self.resolve(item)
            except WorkspaceViolation:
                continue
            if not safe_item.is_file():
                continue
            content = self.read_file(safe_item).content
            for line_number, line in enumerate(content.splitlines(), start=1):
                if expression.search(line):
                    matches.append(SearchMatch(self.relative(safe_item), line_number, line))
                    if len(matches) > limit:
                        return SearchResult(tuple(matches[:limit]), True)
        return SearchResult(tuple(matches), False)

    def apply_patch(self, patch: str) -> PatchResult:
        """Apply a bounded unified diff without invoking a shell or external patch tool."""
        if len(patch.encode("utf-8")) > self.max_patch_bytes:
            raise WorkspaceViolation("Patch exceeds workspace byte limit")
        lines = patch.splitlines(keepends=True)
        changed: list[str] = []
        index = 0
        while index < len(lines):
            if not lines[index].startswith("--- "):
                index += 1
                continue
            old_path = self._patch_path(lines[index][4:].strip())
            index += 1
            if index >= len(lines) or not lines[index].startswith("+++ "):
                raise ValueError("Invalid unified diff: missing new file header")
            new_path = self._patch_path(lines[index][4:].strip())
            path = new_path or old_path
            if path is None:
                raise ValueError("Invalid unified diff: no file path")
            target = self.resolve(path)
            original = target.read_text(encoding="utf-8").splitlines(keepends=True) if target.exists() else []
            output: list[str] = []
            cursor = 0
            index += 1
            while index < len(lines) and not lines[index].startswith("--- "):
                header = lines[index]
                if not header.startswith("@@ "):
                    index += 1
                    continue
                match = re.match(r"@@ -(\d+)(?:,\d+)? \+\d+(?:,\d+)? @@", header)
                if not match:
                    raise ValueError("Invalid unified diff hunk header")
                start = int(match.group(1)) - 1
                output.extend(original[cursor:start])
                cursor = start
                index += 1
                while index < len(lines) and lines[index][:1] in {" ", "+", "-", "\\"}:
                    line = lines[index]
                    marker = line[:1]
                    text = line[1:]
                    if marker == " ":
                        if cursor >= len(original) or original[cursor] != text:
                            raise ValueError(f"Patch context does not match {path}")
                        output.append(text)
                        cursor += 1
                    elif marker == "-":
                        if cursor >= len(original) or original[cursor] != text:
                            raise ValueError(f"Patch removal does not match {path}")
                        cursor += 1
                    elif marker == "+":
                        output.append(text)
                    index += 1
            output.extend(original[cursor:])
            if new_path is None:
                if target.exists():
                    target.unlink()
            else:
                target.parent.mkdir(parents=True, exist_ok=True)
                target.write_text("".join(output), encoding="utf-8")
            changed.append(path)
        if not changed:
            raise ValueError("Patch contains no unified diff files")
        return PatchResult(tuple(changed))

    def _patch_path(self, value: str) -> str | None:
        path = value.split("\t", 1)[0]
        if path == "/dev/null":
            return None
        if path.startswith("a/") or path.startswith("b/"):
            path = path[2:]
        self.resolve(path)
        return path

    @staticmethod
    def _limit(value: int | None, default: int) -> int:
        limit = default if value is None else min(value, default)
        if limit < 1:
            raise ValueError("Requested limit must be positive")
        return limit
