"""Tests for OKF (Open Knowledge Format) bundle.

Covers:
- LocalOKFStorage (filesystem directory)
- ArchiveOKFStorage (.tar.gz portable archive)
- OKFBundle (search, neighbours, context generation, generate)
- Frontmatter parsing and rendering roundtrip
"""

from __future__ import annotations

import os
import tempfile
from pathlib import Path

import pytest

from wolfpack.knowledge.okf import (
    ArchiveOKFStorage,
    BundleMeta,
    Concept,
    LocalOKFStorage,
    OKFBundle,
    _render_concept,
    _parse_concept,
    _parse_frontmatter,
)


# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------


@pytest.fixture
def tmp_dir():
    with tempfile.TemporaryDirectory() as d:
        yield Path(d)


@pytest.fixture
def sample_concept() -> Concept:
    return Concept(
        path="tables/orders.md",
        type="BigQuery Table",
        title="Orders",
        description="One row per completed customer order.",
        resource="https://console.cloud.google.com/bigquery?p=acme&d=sales&t=orders",
        tags=["sales", "revenue"],
        timestamp="2026-05-28T14:30:00Z",
        body="# Schema\n\n| Column | Type |\n|--------|------|\n| order_id | STRING |\n\nSee [customers](/tables/customers.md).",
        links=["/tables/customers.md"],
    )


@pytest.fixture
def sample_bundle() -> Concept:
    return Concept(
        path="tables/orders.md",
        type="BigQuery Table",
        title="Orders",
        description="One row per completed customer order.",
        body="# Schema\n\nSee [customers](/tables/customers.md).",
        links=["/tables/customers.md"],
    )


@pytest.fixture
async def populated_local(tmp_dir, sample_concept) -> LocalOKFStorage:
    storage = LocalOKFStorage(tmp_dir / "bundle")
    await storage.write_concept(sample_concept)
    await storage.write_meta(BundleMeta(title="Sales Bundle", description="Sales data concepts", tags=["sales"]))
    customers = Concept(
        path="tables/customers.md",
        type="BigQuery Table",
        title="Customers",
        description="One row per customer.",
        tags=["sales"],
    )
    await storage.write_concept(customers)
    return storage


# ---------------------------------------------------------------------------
# Frontmatter
# ---------------------------------------------------------------------------


class TestFrontmatter:
    def test_parse_roundtrip(self, sample_concept):
        rendered = _render_concept(sample_concept)
        assert "---" in rendered
        assert "type: BigQuery Table" in rendered
        assert "title: Orders" in rendered
        assert sample_concept.body in rendered

    def test_parse_back(self, sample_concept):
        rendered = _render_concept(sample_concept)
        parsed = _parse_concept(sample_concept.path, rendered)
        assert parsed.type == sample_concept.type
        assert parsed.title == sample_concept.title
        assert parsed.description == sample_concept.description
        assert parsed.tags == sample_concept.tags
        assert parsed.resource == sample_concept.resource

    def test_parse_no_frontmatter(self):
        text = "# Just a heading\n\nSome content."
        meta, body = _parse_frontmatter(text)
        assert meta == {}
        assert "Just a heading" in body

    def test_parse_empty_frontmatter(self):
        text = "---\n---\n\nBody here"
        meta, body = _parse_frontmatter(text)
        assert meta == {}
        assert body.strip() == "Body here"

    def test_parse_tag_list(self):
        text = "---\ntype: Document\ntags: [alpha, beta]\n---\n\nBody"
        meta, _ = _parse_frontmatter(text)
        assert meta["tags"] == ["alpha", "beta"]

    def test_markdown_links(self):
        body = "See [here](/tables/a.md) and [there](../docs/b.md) and [web](https://example.com)"
        from wolfpack.knowledge.okf import _extract_markdown_links
        links = _extract_markdown_links(body)
        assert "/tables/a.md" in links
        assert "../docs/b.md" in links
        assert "https://example.com" not in links  # external


# ---------------------------------------------------------------------------
# LocalOKFStorage
# ---------------------------------------------------------------------------


class TestLocalOKFStorage:
    @pytest.mark.asyncio
    async def test_write_and_read_concept(self, tmp_dir, sample_concept):
        storage = LocalOKFStorage(tmp_dir / "bundle")
        await storage.write_concept(sample_concept)
        read_back = await storage.read_concept("tables/orders.md")
        assert read_back is not None
        assert read_back.title == "Orders"
        assert read_back.type == "BigQuery Table"

    @pytest.mark.asyncio
    async def test_list_concepts(self, populated_local):
        concepts = await populated_local.list_concepts()
        assert len(concepts) >= 1
        paths = [c.path for c in concepts]
        assert "tables/orders.md" in paths
        assert "index.md" in paths

    @pytest.mark.asyncio
    async def test_read_nonexistent(self, tmp_dir):
        storage = LocalOKFStorage(tmp_dir / "empty")
        assert await storage.read_concept("ghost.md") is None

    @pytest.mark.asyncio
    async def test_delete_concept(self, tmp_dir, sample_concept):
        storage = LocalOKFStorage(tmp_dir / "bundle")
        await storage.write_concept(sample_concept)
        await storage.delete_concept("tables/orders.md")
        assert await storage.read_concept("tables/orders.md") is None

    @pytest.mark.asyncio
    async def test_read_meta(self, populated_local):
        meta = await populated_local.read_meta()
        assert meta.title == "Sales Bundle"
        assert "sales" in meta.tags

    @pytest.mark.asyncio
    async def test_path_traversal_protection(self, tmp_dir):
        storage = LocalOKFStorage(tmp_dir / "bundle")
        concept = await storage.read_concept("../../../etc/passwd")
        assert concept is None


# ---------------------------------------------------------------------------
# ArchiveOKFStorage
# ---------------------------------------------------------------------------


class TestArchiveOKFStorage:
    @pytest.mark.asyncio
    async def test_pack_and_list(self, tmp_dir, populated_local):
        archive_path = tmp_dir / "bundle.tar.gz"
        await ArchiveOKFStorage.pack(populated_local, archive_path)
        assert archive_path.exists()

        archive = ArchiveOKFStorage(archive_path)
        concepts = await archive.list_concepts()
        assert len(concepts) >= 2
        paths = [c.path for c in concepts]
        assert "tables/orders.md" in paths

    @pytest.mark.asyncio
    async def test_pack_and_read(self, tmp_dir, populated_local):
        archive_path = tmp_dir / "bundle.tar.gz"
        await ArchiveOKFStorage.pack(populated_local, archive_path)

        archive = ArchiveOKFStorage(archive_path)
        concept = await archive.read_concept("tables/orders.md")
        assert concept is not None
        assert concept.title == "Orders"

    @pytest.mark.asyncio
    async def test_read_nonexistent(self, tmp_dir):
        archive = ArchiveOKFStorage(tmp_dir / "nonexistent.tar.gz")
        assert await archive.read_concept("x.md") is None

    @pytest.mark.asyncio
    async def test_write_raises(self, tmp_dir):
        archive = ArchiveOKFStorage(tmp_dir / "test.tar.gz")
        with pytest.raises(NotImplementedError):
            await archive.write_concept(Concept(path="x.md", type="X"))


# ---------------------------------------------------------------------------
# OKFBundle (high-level API)
# ---------------------------------------------------------------------------


class TestOKFBundle:
    @pytest.mark.asyncio
    async def test_list(self, populated_local):
        bundle = OKFBundle(populated_local)
        concepts = await bundle.list()
        assert len(concepts) >= 2

    @pytest.mark.asyncio
    async def test_get(self, populated_local):
        bundle = OKFBundle(populated_local)
        concept = await bundle.get("tables/orders.md")
        assert concept is not None
        assert concept.title == "Orders"

    @pytest.mark.asyncio
    async def test_search_by_title(self, populated_local):
        bundle = OKFBundle(populated_local)
        results = await bundle.search("orders")
        assert len(results) >= 1
        assert results[0].title == "Orders"

    @pytest.mark.asyncio
    async def test_search_by_tag(self, populated_local):
        bundle = OKFBundle(populated_local)
        results = await bundle.search("revenue")
        assert len(results) >= 1

    @pytest.mark.asyncio
    async def test_search_by_body(self, populated_local):
        bundle = OKFBundle(populated_local)
        results = await bundle.search("order_id")
        assert len(results) >= 1

    @pytest.mark.asyncio
    async def test_search_no_match(self, populated_local):
        bundle = OKFBundle(populated_local)
        results = await bundle.search("zzz_nonexistent_zzz")
        assert len(results) == 0

    @pytest.mark.asyncio
    async def test_neighbours(self, populated_local):
        bundle = OKFBundle(populated_local)
        neighbours = await bundle.neighbours("tables/orders.md")
        assert "outbound" in neighbours
        assert len(neighbours["outbound"]) >= 1

    @pytest.mark.asyncio
    async def test_to_context(self, populated_local):
        bundle = OKFBundle(populated_local)
        context = await bundle.to_context()
        assert "Knowledge Bundle: Sales Bundle" in context
        assert "Orders" in context
        assert "BigQuery Table" in context

    @pytest.mark.asyncio
    async def test_to_context_with_query(self, populated_local):
        bundle = OKFBundle(populated_local)
        context = await bundle.to_context(query="orders")
        assert "Orders" in context

    @pytest.mark.asyncio
    async def test_add_and_remove(self, tmp_dir):
        storage = LocalOKFStorage(tmp_dir / "bundle")
        bundle = OKFBundle(storage)
        c = Concept(path="test.md", type="Test", title="Test Concept", body="Hello")
        await bundle.add(c)
        assert await bundle.get("test.md") is not None
        await bundle.remove("test.md")
        assert await bundle.get("test.md") is None

    @pytest.mark.asyncio
    async def test_generate(self, tmp_dir):
        storage = LocalOKFStorage(tmp_dir / "gen_bundle")
        docs = [
            ("Customer Orders", "# Orders\n\nCustomer order data."),
            ("Products", "# Products\n\nProduct catalog."),
        ]
        bundle = await OKFBundle.generate(docs, storage)
        concepts = await bundle.list()
        assert len(concepts) >= 3
        meta = await storage.read_meta()
        assert meta.title == "Generated Knowledge Bundle"


# ---------------------------------------------------------------------------
# Roundtrip: Local -> Archive -> read
# ---------------------------------------------------------------------------


class TestRoundtrip:
    @pytest.mark.asyncio
    async def test_local_to_archive_and_back(self, tmp_dir, sample_concept):
        local = LocalOKFStorage(tmp_dir / "bundle")
        await local.write_concept(sample_concept)
        await local.write_meta(BundleMeta(title="Test"))

        archive_path = tmp_dir / "bundle.tar.gz"
        await ArchiveOKFStorage.pack(local, archive_path)

        archive = ArchiveOKFStorage(archive_path)
        concept = await archive.read_concept("tables/orders.md")
        assert concept is not None
        assert concept.title == "Orders"
        assert concept.type == "BigQuery Table"
        assert "order_id" in concept.body


# ---------------------------------------------------------------------------
# S3OKFStorage (requires moto / real S3) — integration marker
# ---------------------------------------------------------------------------


class TestS3OKFStorage:
    def test_interface(self):
        from wolfpack.knowledge.okf import S3OKFStorage
        assert hasattr(S3OKFStorage, "list_concepts")
        assert hasattr(S3OKFStorage, "read_concept")
        assert hasattr(S3OKFStorage, "write_concept")
        assert hasattr(S3OKFStorage, "delete_concept")