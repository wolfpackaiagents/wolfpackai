"""22_okf/01_okf_bundle.py - Open Knowledge Format (OKF) bundle example.

This example demonstrates creating, storing, and querying knowledge bundles
using the Open Knowledge Format (OKF). It covers all three storage backends:

- Local directory (filesystem)
- Archive (.tar.gz portable bundle)
- S3/MinIO (cloud storage)

Each concept is a markdown file with YAML frontmatter. File paths = identities.
Markdown links between files = a navigable knowledge graph.

Usage:
    uv run python examples/22_okf/01_okf_bundle.py
"""

import asyncio
import sys
import tempfile
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from wolfpack.knowledge.okf import (
    ArchiveOKFStorage,
    Concept,
    LocalOKFStorage,
    OKFBundle,
)


async def main() -> None:
    with tempfile.TemporaryDirectory() as tmp:
        storage = LocalOKFStorage(Path(tmp) / "ecommerce_knowledge")
        bundle = OKFBundle(storage)

        print("=" * 60)
        print("OKF BUNDLE EXAMPLE - E-Commerce Data Warehouse")
        print("=" * 60)

        # -- Bundle index --
        await bundle.add(Concept(
            path="index.md", type="bundle", title="E-Commerce Warehouse",
            description="ACME e-commerce data warehouse concepts.",
            tags=["ecommerce", "bigquery", "analytics"],
        ))

        # -- Table: orders --
        await bundle.add(Concept(
            path="tables/orders.md", type="BigQuery Table", title="Orders",
            description="One row per completed customer order.",
            tags=["sales", "revenue"],
            body=(
                "# Schema\n\n"
                "| Column | Type | Description |\n"
                "|--------|------|-------------|\n"
                "| order_id | STRING | Unique ID |\n"
                "| customer_id | STRING | FK to [customers](tables/customers.md) |\n"
                "| total | FLOAT | Order total in USD |\n\n"
                "See [customers](tables/customers.md).\n"
            ),
        ))

        # -- Table: customers --
        await bundle.add(Concept(
            path="tables/customers.md", type="BigQuery Table", title="Customers",
            description="One row per registered customer.",
            tags=["sales", "crm"],
            body="# Schema\n\n| customer_id | STRING | Unique ID |\n| name | STRING | Full name |\n| email | STRING | Email |\n\nReferenced by [orders](tables/orders.md).\n",
        ))

        # -- Metric: weekly_active_users --
        await bundle.add(Concept(
            path="metrics/weekly_active_users.md", type="Metric",
            title="Weekly Active Users",
            description="Distinct users who ordered in the last 7 days.",
            tags=["engagement", "growth"],
            body="# SQL\nSELECT COUNT(DISTINCT customer_id) FROM sales.orders\nWHERE created_at >= TIMESTAMP_SUB(CURRENT_TIMESTAMP(), INTERVAL 7 DAY)\n",
        ))

        concepts = await bundle.list()
        print(f"\nBundle created. Concepts: {len(concepts)}")

        # -- Search --
        print("\n--- Search ---")
        for q in ["orders", "revenue", "customer"]:
            results = await bundle.search(q)
            print(f"  '{q}': {len(results)} result(s)")
            for c in results:
                print(f"    - {c.path}: {c.title} ({c.type})")

        # -- Graph neighbours --
        print("\n--- Graph ---")
        n = await bundle.neighbours("tables/orders.md")
        print(f"  Outbound: {n['outbound']}")
        print(f"  Inbound:  {n['inbound']}")

        # -- Context for LLM --
        print("\n--- Prompt context (head) ---")
        ctx = await bundle.to_context(query="weekly active users")
        print(ctx[:500])

        # -- Archive --
        ap = Path(tmp) / "bundle.tar.gz"
        await ArchiveOKFStorage.pack(storage, ap)
        archive = ArchiveOKFStorage(ap)
        archived = OKFBundle(archive)
        print(f"\nArchive: {len(await archived.list())} concepts, {ap.stat().st_size} bytes")

        # -- Generate from docs --
        docs = [("API v2", "# API\nGET /users"), ("Deploy Guide", "# Deploy\nHelm chart steps")]
        gen = await OKFBundle.generate(docs, LocalOKFStorage(Path(tmp) / "gen"))
        print(f"Generated: {len(await gen.list())} concepts")

        # -- S3 check --
        from wolfpack.knowledge.okf import S3OKFStorage
        print("S3OKFStorage available:", hasattr(S3OKFStorage, "list_concepts"))

        print("\nDone.")


if __name__ == "__main__":
    asyncio.run(main())
