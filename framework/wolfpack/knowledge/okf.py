"""Open Knowledge Format (OKF) — vendor-neutral knowledge bundles.

OKF is a portable format for representing metadata, context, and curated
knowledge that AI agents can consume. A bundle is a directory of markdown
files with YAML frontmatter. File path = concept identity. Markdown links
between files = knowledge graph relationships.

Three storage backends:
- LocalOKFStorage: filesystem directory
- ArchiveOKFStorage: .tar.gz file (portable, downloadable)
- S3OKFStorage: S3/MinIO bucket (production, shared)

Usage:
    storage = LocalOKFStorage("/path/to/bundle")
    bundle = OKFBundle(storage)
    concepts = await bundle.search("revenue by customer")
"""

from __future__ import annotations

import io
import json
import re
import tarfile
from dataclasses import dataclass, field
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Dict, List, Optional, Protocol
from urllib.parse import urlparse


# ---------------------------------------------------------------------------
# Data models
# ---------------------------------------------------------------------------


@dataclass
class Concept:
    """A single concept in an OKF bundle (one .md file)."""

    path: str  # relative path within bundle, e.g. "tables/orders.md"
    type: str  # required by spec: "BigQuery Table", "Metric", "API"...
    title: str = ""
    description: str = ""
    resource: str = ""  # URL or URN
    tags: List[str] = field(default_factory=list)
    timestamp: str = ""  # ISO 8601
    body: str = ""  # markdown body
    links: List[str] = field(default_factory=list)  # target paths from markdown links


@dataclass
class BundleMeta:
    """Metadata for the entire bundle (from index.md)."""

    title: str = ""
    description: str = ""
    version: str = "0.1.0"
    tags: List[str] = field(default_factory=list)
    timestamp: str = ""


# ---------------------------------------------------------------------------
# Storage protocol
# ---------------------------------------------------------------------------


class OKFStorage(Protocol):
    """Contract for OKF bundle storage backends."""

    async def list_concepts(self) -> List[Concept]:
        """List all concepts in the bundle."""
        ...

    async def read_concept(self, path: str) -> Concept | None:
        """Read a single concept by its relative path."""
        ...

    async def write_concept(self, concept: Concept) -> None:
        """Write (create or update) a concept."""
        ...

    async def delete_concept(self, path: str) -> None:
        """Delete a concept by its relative path."""
        ...

    async def read_meta(self) -> BundleMeta:
        """Read bundle metadata (from index.md)."""
        ...

    async def write_meta(self, meta: BundleMeta) -> None:
        """Write bundle metadata to index.md."""
        ...


# ---------------------------------------------------------------------------
# Frontmatter parsing helpers
# ---------------------------------------------------------------------------

_FM_RE = re.compile(r"^---\s*\n(.*?)(?:\n?---)\s*\n?", re.DOTALL)


def _parse_frontmatter(text: str) -> tuple[dict[str, Any], str]:
    """Split YAML frontmatter from markdown body. Returns (metadata, body)."""
    m = _FM_RE.match(text)
    if not m:
        return {}, text
    raw = m.group(1)
    body = text[m.end() :]
    meta = _yaml_safe_load(raw)
    return meta, body


def _yaml_safe_load(text: str) -> dict[str, Any]:
    """Parse YAML frontmatter without pyyaml dependency (simple impl)."""
    result: dict[str, Any] = {}
    for line in text.splitlines():
        line = line.rstrip()
        if ":" in line:
            key, _, value = line.partition(":")
            key = key.strip()
            value = value.strip()
            if value.startswith("[") and value.endswith("]"):
                value = [v.strip().strip('"').strip("'") for v in value[1:-1].split(",") if v.strip()]
            result[key] = value
    return result


def _yaml_dump(data: dict[str, Any]) -> str:
    """Dump dict to YAML-ish frontmatter."""
    lines: list[str] = []
    for k, v in data.items():
        if isinstance(v, list):
            items = ", ".join(f'"{x}"' for x in v)
            lines.append(f"{k}: [{items}]")
        else:
            lines.append(f"{k}: {v}")
    return "\n".join(lines)


def _render_concept(concept: Concept) -> str:
    """Render a Concept to .md with YAML frontmatter."""
    meta: dict[str, Any] = {"type": concept.type}
    if concept.title:
        meta["title"] = concept.title
    if concept.description:
        meta["description"] = concept.description
    if concept.resource:
        meta["resource"] = concept.resource
    if concept.tags:
        meta["tags"] = concept.tags
    if concept.timestamp:
        meta["timestamp"] = concept.timestamp
    front = _yaml_dump(meta)
    return f"---\n{front}\n---\n\n{concept.body}"


def _parse_concept(path: str, text: str) -> Concept:
    """Parse a .md file back to a Concept."""
    meta, body = _parse_frontmatter(text)
    links = _extract_markdown_links(body)
    return Concept(
        path=path,
        type=meta.get("type", "unknown"),
        title=meta.get("title", ""),
        description=meta.get("description", ""),
        resource=meta.get("resource", ""),
        tags=meta.get("tags", []),
        timestamp=meta.get("timestamp", ""),
        body=body.strip(),
        links=links,
    )


def _extract_markdown_links(body: str) -> list[str]:
    """Extract relative markdown link targets from body."""
    links: list[str] = []
    for m in re.finditer(r"\[([^\]]+)\]\(([^)]+)\)", body):
        target = m.group(2)
        if not target.startswith("http") and not target.startswith("#"):
            links.append(target.split("#")[0].split("?")[0])
    return links


def _now() -> str:
    return datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")


# ---------------------------------------------------------------------------
# Local directory storage
# ---------------------------------------------------------------------------


class LocalOKFStorage:
    """OKF bundle stored as files in a local directory."""

    def __init__(self, path: str | Path) -> None:
        self._root = Path(path)

    async def list_concepts(self) -> List[Concept]:
        if not self._root.exists():
            return []
        concepts: list[Concept] = []
        for f in sorted(self._root.rglob("*.md")):
            rel = str(f.relative_to(self._root))
            text = f.read_text(encoding="utf-8")
            concepts.append(_parse_concept(rel, text))
        return concepts

    async def read_concept(self, path: str) -> Concept | None:
        fp = self._root / path
        # Security: prevent path traversal
        try:
            fp = fp.resolve().relative_to(self._root.resolve())
        except ValueError:
            return None
        fp = self._root / fp
        if not fp.exists() or not fp.is_file():
            return None
        text = fp.read_text(encoding="utf-8")
        return _parse_concept(path, text)

    async def write_concept(self, concept: Concept) -> None:
        fp = self._root / concept.path
        fp.parent.mkdir(parents=True, exist_ok=True)
        fp.write_text(_render_concept(concept), encoding="utf-8")

    async def delete_concept(self, path: str) -> None:
        fp = self._root / path
        if fp.exists():
            fp.unlink()

    async def read_meta(self) -> BundleMeta:
        index = await self.read_concept("index.md")
        if index is None:
            return BundleMeta()
        return BundleMeta(
            title=index.title,
            description=index.description,
            version=index.tags[0] if index.tags else "0.1.0",
            tags=index.tags,
            timestamp=index.timestamp or _now(),
        )

    async def write_meta(self, meta: BundleMeta) -> None:
        concept = Concept(
            path="index.md",
            type="bundle",
            title=meta.title,
            description=meta.description,
            tags=meta.tags,
            timestamp=meta.timestamp or _now(),
            body=f"# {meta.title}\n\n{meta.description}",
        )
        await self.write_concept(concept)


# ---------------------------------------------------------------------------
# Archive (.tar.gz) storage
# ---------------------------------------------------------------------------


class ArchiveOKFStorage:
    """OKF bundle stored as a .tar.gz file. Portable and downloadable."""

    def __init__(self, path: str | Path) -> None:
        self._path = Path(path)

    async def list_concepts(self) -> List[Concept]:
        if not self._path.exists():
            return []
        concepts: list[Concept] = []
        with tarfile.open(self._path, "r:gz") as tar:
            for member in tar.getmembers():
                if member.name.endswith(".md") and not member.name.startswith("."):
                    f = tar.extractfile(member)
                    if f is None:
                        continue
                    text = f.read().decode("utf-8")
                    concepts.append(_parse_concept(member.name, text))
        return concepts

    async def read_concept(self, path: str) -> Concept | None:
        if not self._path.exists():
            return None
        with tarfile.open(self._path, "r:gz") as tar:
            try:
                member = tar.getmember(path)
            except KeyError:
                return None
            f = tar.extractfile(member)
            if f is None:
                return None
            text = f.read().decode("utf-8")
            return _parse_concept(path, text)

    async def write_concept(self, concept: Concept) -> None:
        raise NotImplementedError("ArchiveOKFStorage is read-only; use ArchiveOKFStorage.pack() to create")

    async def delete_concept(self, path: str) -> None:
        raise NotImplementedError("ArchiveOKFStorage is read-only")

    async def read_meta(self) -> BundleMeta:
        index = await self.read_concept("index.md")
        if index is None:
            return BundleMeta()
        return BundleMeta(
            title=index.title,
            description=index.description,
            tags=index.tags,
            timestamp=index.timestamp,
        )

    async def write_meta(self, meta: BundleMeta) -> None:
        raise NotImplementedError("ArchiveOKFStorage is read-only; use ArchiveOKFStorage.pack() to create")

    @staticmethod
    async def pack(source: LocalOKFStorage, dest: str | Path) -> Path:
        """Pack a local bundle into a .tar.gz archive."""
        dest_path = Path(dest)
        with tarfile.open(dest_path, "w:gz") as tar:
            concepts = await source.list_concepts()
            for c in concepts:
                text = _render_concept(c)
                info = tarfile.TarInfo(name=c.path)
                data = text.encode("utf-8")
                info.size = len(data)
                info.mtime = 0
                tar.addfile(info, io.BytesIO(data))
        return dest_path


# ---------------------------------------------------------------------------
# S3 / MinIO storage
# ---------------------------------------------------------------------------


class S3OKFStorage:
    """OKF bundle stored in an S3 bucket or MinIO."""

    def __init__(self, bucket: str, prefix: str, client: Any, endpoint_url: str | None = None) -> None:
        self._bucket = bucket
        self._prefix = prefix.rstrip("/")
        self._client = client

    def _key(self, path: str) -> str:
        return f"{self._prefix}/{path}" if self._prefix else path

    def _path_from_key(self, key: str) -> str:
        prefix = self._prefix + "/" if self._prefix else ""
        return key[len(prefix) :] if key.startswith(prefix) else key

    async def list_concepts(self) -> List[Concept]:
        import asyncio

        paginator = self._client.get_paginator("list_objects_v2")
        concepts: list[Concept] = []
        for page in paginator.paginate(Bucket=self._bucket, Prefix=f"{self._prefix}/"):
            for obj in page.get("Contents", []):
                key = obj["Key"]
                if key.endswith(".md"):
                    resp = await asyncio.to_thread(
                        self._client.get_object, Bucket=self._bucket, Key=key
                    )
                    text = resp["Body"].read().decode("utf-8")
                    concepts.append(_parse_concept(self._path_from_key(key), text))
        return concepts

    async def read_concept(self, path: str) -> Concept | None:
        import asyncio

        key = self._key(path)
        try:
            resp = await asyncio.to_thread(self._client.get_object, Bucket=self._bucket, Key=key)
        except self._client.exceptions.NoSuchKey:
            return None
        text = resp["Body"].read().decode("utf-8")
        return _parse_concept(path, text)

    async def write_concept(self, concept: Concept) -> None:
        import asyncio

        text = _render_concept(concept)
        await asyncio.to_thread(
            self._client.put_object,
            Bucket=self._bucket,
            Key=self._key(concept.path),
            Body=text.encode("utf-8"),
            ContentType="text/markdown",
        )

    async def delete_concept(self, path: str) -> None:
        import asyncio

        await asyncio.to_thread(self._client.delete_object, Bucket=self._bucket, Key=self._key(path))

    async def read_meta(self) -> BundleMeta:
        index = await self.read_concept("index.md")
        if index is None:
            return BundleMeta()
        return BundleMeta(
            title=index.title,
            description=index.description,
            tags=index.tags,
            timestamp=index.timestamp,
        )

    async def write_meta(self, meta: BundleMeta) -> None:
        concept = Concept(
            path="index.md",
            type="bundle",
            title=meta.title,
            description=meta.description,
            tags=meta.tags,
            timestamp=meta.timestamp or _now(),
            body=f"# {meta.title}\n\n{meta.description}",
        )
        await self.write_concept(concept)


# ---------------------------------------------------------------------------
# OKF Bundle — high-level API
# ---------------------------------------------------------------------------


class OKFBundle:
    """A portable knowledge bundle following the Open Knowledge Format.

    Usage:
        storage = LocalOKFStorage("/path/to/bundle")
        bundle = OKFBundle(storage)
        all = await bundle.list()
        results = await bundle.search("customer orders")
        concept = await bundle.get("tables/orders.md")
    """

    def __init__(self, storage: OKFStorage) -> None:
        self._storage = storage

    async def list(self) -> List[Concept]:
        """List all concepts in the bundle."""
        return await self._storage.list_concepts()

    async def get(self, path: str) -> Concept | None:
        """Get a single concept by its relative path."""
        return await self._storage.read_concept(path)

    async def search(self, query: str) -> List[Concept]:
        """Search concepts by title, tags, and body content."""
        results: list[Concept] = []
        q = query.lower()
        for c in await self._storage.list_concepts():
            if q in c.title.lower():
                results.append(c)
                continue
            if any(q in t.lower() for t in c.tags):
                results.append(c)
                continue
            if q in c.description.lower():
                results.append(c)
                continue
            if q in c.body.lower():
                results.append(c)
        return results

    async def neighbours(self, path: str, max_depth: int = 1) -> dict[str, list[str]]:
        """Get the graph neighbourhood of a concept via markdown links."""
        concept = await self.get(path)
        if concept is None:
            return {"outbound": [], "inbound": []}
        all_concepts = await self._storage.list_concepts()
        all_paths = {c.path for c in all_concepts}
        outbound = [link for link in concept.links if link.lstrip("/") in all_paths]
        inbound = [c.path for c in all_concepts if any(link.lstrip("/") == path for link in c.links)]
        return {"outbound": outbound, "inbound": inbound}

    async def to_context(self, query: str = "", max_concepts: int = 10) -> str:
        """Render concepts as markdown context for an LLM prompt."""
        if query:
            concepts = await self.search(query)
        else:
            concepts = await self.list()
        concepts = concepts[:max_concepts]
        parts: list[str] = []
        meta = await self._storage.read_meta()
        if meta.title:
            parts.append(f"# Knowledge Bundle: {meta.title}\n")
        for c in concepts:
            header = f"## {c.path}"
            if c.title:
                header += f" — {c.title}"
            parts.append(header)
            parts.append(f"Type: {c.type}")
            if c.description:
                parts.append(c.description)
            if c.tags:
                parts.append(f"Tags: {', '.join(c.tags)}")
            parts.append("")
            if c.body:
                # Only first 500 chars to keep context tight
                parts.append(c.body[:500])
            parts.append("---")
        return "\n".join(parts)

    async def add(self, concept: Concept) -> None:
        """Add a new concept to the bundle."""
        await self._storage.write_concept(concept)

    async def remove(self, path: str) -> None:
        """Remove a concept from the bundle."""
        await self._storage.delete_concept(path)

    @staticmethod
    async def generate(
        documents: list[tuple[str, str]],
        storage: OKFStorage,
        type_label: str = "Document",
    ) -> OKFBundle:
        """Generate an OKF bundle from documents.

        Args:
            documents: list of (title, content) tuples
            storage: where to store the generated bundle
            type_label: OKF type for all concepts
        Returns:
            OKFBundle instance
        """
        meta = BundleMeta(title="Generated Knowledge Bundle", timestamp=_now())
        await storage.write_meta(meta)
        for i, (title, content) in enumerate(documents):
            safe_name = re.sub(r"[^a-z0-9_-]", "", title.lower().replace(" ", "_"))[:60] or f"doc_{i}"
            path = f"docs/{safe_name}.md"
            body = content[:2000]
            concept = Concept(
                path=path,
                type=type_label,
                title=title,
                body=body,
                timestamp=_now(),
            )
            await storage.write_concept(concept)
        return OKFBundle(storage)