"""VectorDb abstraction: the interface connecting Knowledge to vector databases.

Pattern taken from agno (`VectorDb` with insert/upsert/search). `Knowledge` does not
know which VDB it uses; it only knows this interface. MVP: Qdrant and PGVector plus an
in-memory implementation for development/tests.
"""

from __future__ import annotations

import math
import uuid
from abc import ABC, abstractmethod
from typing import Any, Dict, List, Optional


class Document:
    def __init__(self, content: str, metadata: Optional[Dict[str, Any]] = None, id: Optional[str] = None):
        self.id = id or uuid.uuid4().hex
        self.content = content
        self.metadata = metadata or {}

    def to_dict(self) -> Dict[str, Any]:
        return {"id": self.id, "content": self.content, "metadata": self.metadata}


class SearchResult:
    def __init__(self, document: Document, score: float):
        self.document = document
        self.score = score

    def to_dict(self) -> Dict[str, Any]:
        return {"document": self.document.to_dict(), "score": self.score}


class VectorDb(ABC):
    @abstractmethod
    def upsert(self, docs: List[Document], embeddings: List[List[float]]) -> None:
        ...

    def insert(self, docs: List[Document], embeddings: List[List[float]]) -> None:
        self.upsert(docs, embeddings)

    @abstractmethod
    def search(self, query_embedding: List[float], limit: int = 5, filters: Optional[Dict[str, Any]] = None) -> List[SearchResult]:
        ...

    @abstractmethod
    def delete(self, ids: List[str]) -> None:
        ...

    def count(self) -> int:
        return 0


class MemoryVectorDb(VectorDb):
    """In-memory implementation for development and tests (no external deps)."""

    def __init__(self):
        self._docs: List[Document] = []
        self._embeddings: List[List[float]] = []

    def upsert(self, docs, embeddings):
        for doc, emb in zip(docs, embeddings):
            for i, existing in enumerate(self._docs):
                if existing.id == doc.id:
                    self._docs[i] = doc
                    self._embeddings[i] = emb
                    break
            else:
                self._docs.append(doc)
                self._embeddings.append(emb)

    def search(self, query_embedding, limit=5, filters=None):
        def cos(a, b):
            if not a or not b or len(a) != len(b):
                return 0.0
            denom = (math.sqrt(sum(x * x for x in a)) or 1.0) * (math.sqrt(sum(x * x for x in b)) or 1.0)
            return sum(x * y for x, y in zip(a, b)) / denom

        scored = []
        for i, doc in enumerate(self._docs):
            if filters and not all(doc.metadata.get(k) == v for k, v in filters.items()):
                continue
            emb = self._embeddings[i] if i < len(self._embeddings) else []
            scored.append((doc, cos(query_embedding, emb)))
        scored.sort(key=lambda t: t[1], reverse=True)
        return [SearchResult(doc, score) for doc, score in scored[:limit]]

    def delete(self, ids):
        idset = set(ids)
        kept = [(d, e) for d, e in zip(self._docs, self._embeddings) if d.id not in idset]
        self._docs = [d for d, _ in kept]
        self._embeddings = [e for _, e in kept]

    def count(self):
        return len(self._docs)


class QdrantVectorDb(VectorDb):
    def __init__(self, collection: str, url: str | None = None, host: str = "localhost", port: int = 6333, api_key: str | None = None, distance: str = "Cosine", vector_size: int = 1536):
        try:
            from qdrant_client import QdrantClient, models
        except ImportError as e:
            raise ImportError('Instalá "qdrant-client>=1.9" para usar Qdrant.') from e
        self.models = models
        self.vector_size = vector_size
        if url:
            self.client = QdrantClient(url=url, api_key=api_key or None)
        else:
            self.client = QdrantClient(host=host, port=port, api_key=api_key or None)
        self.collection = collection
        self._ensure_collection(distance)

    def _ensure_collection(self, distance: str):
        try:
            self.client.get_collection(self.collection)
        except Exception:
            self.client.recreate_collection(
                collection_name=self.collection,
                vectors_config=self.models.VectorParams(size=self.vector_size, distance=self.models.Distance[distance.upper()]),
            )

    def upsert(self, docs, embeddings):
        points = [
            self.models.PointStruct(
                id=doc.id,
                vector=list(emb),
                payload={"content": doc.content, "metadata": doc.metadata},
            )
            for doc, emb in zip(docs, embeddings)
        ]
        self.client.upsert(self.collection, points)

    def search(self, query_embedding, limit=5, filters=None):
        qfilter = None
        if filters and hasattr(self.models, "FieldCondition"):
            conditions = [
                self.models.FieldCondition(key=f"metadata.{k}", match=self.models.MatchValue(value=v))
                for k, v in filters.items()
            ]
            qfilter = self.models.Filter(should=conditions)
        hits = self.client.query_points(
            collection_name=self.collection,
            query=list(query_embedding),
            query_filter=qfilter,
            limit=limit,
            with_payload=True,
        )
        results = []
        for h in hits:
            if hasattr(h, "payload") and h.payload:
                doc = Document(content=h.payload.get("content", ""), metadata=h.payload.get("metadata", {}), id=str(h.id))
                results.append(SearchResult(doc, h.score))
        return results

    def delete(self, ids):
        self.client.delete(self.collection, points_selector=self.models.PointIdsList(points=ids))

    def count(self):
        return self.client.count(self.collection).count


class PGVectorVectorDb(VectorDb):
    """PGVector skeleton (psycopg3 + pgvector). MVP users complete it with Qdrant."""

    def __init__(self, connection_string: str, table: str = "documents", vector_size: int = 1536):
        self.connection_string = connection_string
        self.table = table
        self.vector_size = vector_size

    def _connect(self):
        try:
            import psycopg
            from pgvector.psycopg import register_vector
        except ImportError as e:
            raise ImportError('Installá "psycopg[binary]>=3.1" y "pgvector>=0.2" para PGVector.') from e
        conn = psycopg.connect(self.connection_string)
        register_vector(conn)
        return conn

    def upsert(self, docs, embeddings):
        conn = self._connect()
        try:
            with conn.cursor() as cur:
                for doc, emb in zip(docs, embeddings):
                    cur.execute(
                        f"INSERT INTO {self.table} (id, content, metadata, embedding) VALUES (%s,%s,%s,%s) "
                        f"ON CONFLICT (id) DO UPDATE SET content=EXCLUDED.content, metadata=EXCLUDED.metadata, embedding=EXCLUDED.embedding",
                        (doc.id, doc.content, doc.metadata, emb),
                    )
                conn.commit()
        finally:
            conn.close()

    def search(self, query_embedding, limit=5, filters=None):
        conn = self._connect()
        try:
            import psycopg
            with conn.cursor() as cur:
                cur.execute(
                    f"SELECT id, content, metadata, embedding <=> %s AS score FROM {self.table} "
                    f"ORDER BY embedding <=> %s LIMIT %s",
                    (query_embedding, query_embedding, limit),
                )
                rows = cur.fetchall()
            results = []
            for rid, content, meta, score in rows:
                doc = Document(content=content, metadata=meta or {}, id=str(rid))
                results.append(SearchResult(doc, float(score)))
            return results
        finally:
            conn.close()

    def delete(self, ids):
        conn = self._connect()
        try:
            with conn.cursor() as cur:
                cur.execute(f"DELETE FROM {self.table} WHERE id = ANY(%s)", (ids,))
                conn.commit()
        finally:
            conn.close()

    def count(self):
        conn = self._connect()
        try:
            with conn.cursor() as cur:
                cur.execute(f"SELECT count(*) FROM {self.table}")
                return int(cur.fetchone()[0])
        finally:
            conn.close()