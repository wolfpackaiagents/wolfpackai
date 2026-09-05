"""Markdown reader for Knowledge - reads from file paths or raw strings."""

from __future__ import annotations

import re
from dataclasses import dataclass, field
from typing import Any, Callable, List, Optional


@dataclass
class Chunk:
    content: str
    metadata: dict[str, Any]


@dataclass
class MarkdownReader:
    chunk_size: int = 1000
    overlap: int = 100
    split_by_headings: bool = True

    def read_file(self, path: str) -> List[Chunk]:
        with open(path, "r", encoding="utf-8", errors="ignore") as f:
            return self.read_string(f.read(), metadata={"source": path})

    def read_string(self, text: str, metadata: Optional[dict] = None) -> List[Chunk]:
        sections = self._split_headings(text) if self.split_by_headings else [text]
        chunks: List[Chunk] = []
        base = metadata or {}
        for section in sections:
            heading = self._extract_heading(section)
            meta = {**base}
            if heading:
                meta["heading"] = heading
            for content in self._chunk_text(section):
                chunks.append(Chunk(content=content, metadata=meta))
        return chunks

    def _split_headings(self, text: str) -> List[str]:
        lines = text.splitlines()
        sections: List[str] = []
        current: List[str] = []
        for line in lines:
            if line.startswith("## ") and current:
                sections.append("\n".join(current))
                current = []
            current.append(line)
        if current:
            sections.append("\n".join(current))
        return sections if len(sections) > 1 else [text]

    def _extract_heading(self, text: str) -> Optional[str]:
        for line in text.splitlines():
            if line.startswith("## "):
                return line[3:].strip()
        return None

    def _chunk_text(self, text: str) -> List[str]:
        if len(text) <= self.chunk_size:
            return [text]
        chunks: List[str] = []
        step = self.chunk_size - self.overlap
        for i in range(0, len(text), step):
            part = text[i : i + self.chunk_size]
            if part.strip():
                chunks.append(part)
        return chunks