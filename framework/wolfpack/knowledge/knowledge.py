"""Knowledge / RAG: reads sources (text/md/html/pdf), chunks, embeds and searches a
VectorDb. Search results are made available as system context or as the
`search_knowledge_base` tool (agno pattern).

MVP:
- `Knowledge` with a VectorDb + EmbeddingModel.
- Chunking controls (fixed_size or recursive).
- `Knowledge.search(query)` to retrieve relevant docs.
"""

from __future__ import annotations

import os
import re
from dataclasses import dataclass, field
from typing import Any, Dict, List, Optional

from ..vectordb.base import VectorDb
from ..vectordb.embeddings import EmbeddingModel


def _default_chunk_size(content: str, chunk_size: int = 1000, overlap: int = 100) -> List[str]:
    if len(content) <= chunk_size:
        return [content]
    chunks: List[str] = []
    step = chunk_size - overlap
    for i in range(0, len(content), step):
        chunk_parts = content[i : i + chunk_size]
        if chunk_parts.strip():
            chunks.append(chunk_parts)
    return chunks


def _split_markdown_sections(content: str) -> List[str]:
    """Split by level-2 headers in markdown (for `load_text` with md format)."""
    lines = content.splitlines()
    sections: List[str] = []
    current: List[str] = []
    for line in lines:
        if line.startswith("## "):
            if current:
                sections.append("\n".join(current))
                current = []
        current.append(line)
    if current:
        sections.append("\n".join(current))
    return sections if len(sections) > 1 else [content]


def _read_file(path: str) -> str:
    ext = os.path.splitext(path)[1].lower()
    if ext == ".pdf":
        try:
            from pypdf import PdfReader

            reader = PdfReader(path)
            return "\n".join(page.extract_text() or "" for page in reader.pages)
        except ImportError as e:
            raise ImportError('Instalá "pypdf>=4.0" para leer PDFs.') from e
    if ext == ".docx":
        try:
            from docx import Document as WDocument

            doc = WDocument(path)
            return "\n".join(p.text for p in doc.paragraphs)
        except ImportError as e:
            raise ImportError('Instalá "python-docx>=1.1" para leer DOCX.') from e
    with open(path, "r", encoding="utf-8", errors="ignore") as f:
        return f.read()


@dataclass
class Knowledge:
    vector_db: VectorDb
    embedding_model: EmbeddingModel
    chunk_size: int = 1000
    max_results: int = 5

    def __post_init__(self):
        self._paths: List[str] = []
        self._contents: List[str] = []

    # --- loading ---

    def add_text(self, text: str, metadata: Optional[Dict[str, Any]] = None, chunk: bool = True) -> None:
        chunks = _default_chunk_size(text, self.chunk_size) if chunk else [text]
        self._load_chunks(chunks, metadata)

    def add_from_path(self, path: str, metadata: Optional[Dict[str, Any]] = None) -> None:
        content = _read_file(path)
        self._paths.append(path)
        base_meta = {"source": path, **(metadata or {})}
        if path.lower().endswith(".md"):
            for sec in _split_markdown_sections(content):
                chunks = _default_chunk_size(sec, self.chunk_size)
                self._load_chunks(chunks, {**base_meta, "section": True})
        else:
            chunks = _default_chunk_size(content, self.chunk_size)
            self._load_chunks(chunks, base_meta)

    def _load_chunks(self, chunks: List[str], metadata: Optional[Dict[str, Any]]):
        from ..vectordb.base import Document

        docs = [Document(content=c, metadata=metadata) for c in chunks]
        embeddings = self.embedding_model.embed(chunks)
        self.vector_db.upsert(docs, embeddings)
        self._contents.extend(chunks)

    # --- search ---

    def search(self, query: str, limit: Optional[int] = None, filters: Optional[Dict[str, Any]] = None) -> List[Any]:
        emb = self.embedding_model.embed([query])[0]
        k = limit or self.max_results
        return self.vector_db.search(emb, limit=k, filters=filters)

    def count(self) -> int:
        return self.vector_db.count()