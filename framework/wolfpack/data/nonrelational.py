"""Bounded tools for document, graph, and key-value data sources."""

from __future__ import annotations

import re
from collections.abc import Callable
from typing import Any

from ..tools.toolkit import Toolkit
from .policy import DataAccessPolicy, DataPolicyError


class DocumentToolkit(Toolkit):
    def __init__(self, *, collection: str, policy: DataAccessPolicy, find: Callable[[str, dict[str, Any], int], list[dict[str, Any]]]) -> None:
        super().__init__("document")
        policy.require_collection(collection)
        self.collection = collection
        self.policy = policy
        self._find = find
        self.register(self.find_documents, description="Find bounded documents in the configured collection.")

    def find_documents(self, filter: dict[str, Any]) -> dict[str, Any]:
        documents = self._find(self.collection, filter, self.policy.max_rows)
        return {
            "source_id": self.policy.source_id,
            "documents": [self._redact(document) for document in documents[: self.policy.max_rows]],
        }

    def _redact(self, document: dict[str, Any]) -> dict[str, Any]:
        sensitive = {column.lower() for column in self.policy.sensitive_columns}
        return {key: "[REDACTED]" if key.lower() in sensitive else value for key, value in document.items()}


class GraphToolkit(Toolkit):
    def __init__(self, *, policy: DataAccessPolicy, labels: Callable[[], list[str]], read: Callable[[str, dict[str, Any] | None, int], list[dict[str, Any]]]) -> None:
        super().__init__("graph")
        self.policy = policy
        self._labels = labels
        self._read = read
        self.register(self.list_labels, description="List permitted graph labels.")
        self.register(self.read_cypher, description="Run a bounded read-only Cypher query.")

    def list_labels(self) -> dict[str, Any]:
        labels = self._labels()
        if self.policy.allowed_graph_labels:
            labels = [label for label in labels if label in self.policy.allowed_graph_labels]
        return {"source_id": self.policy.source_id, "labels": labels}

    def read_cypher(self, query: str, parameters: dict[str, Any] | None = None) -> dict[str, Any]:
        if not re.match(r"^\s*(MATCH|OPTIONAL\s+MATCH|CALL)\b", query, re.IGNORECASE):
            raise DataPolicyError("Only read-only Cypher queries are allowed.")
        if re.search(r"\b(CREATE|DELETE|DETACH|MERGE|REMOVE|SET|DROP)\b", query, re.IGNORECASE):
            raise DataPolicyError("Only read-only Cypher queries are allowed.")
        for label in re.findall(r":([A-Za-z_][A-Za-z0-9_]*)", query):
            if self.policy.allowed_graph_labels and label not in self.policy.allowed_graph_labels:
                raise DataPolicyError(f"Graph label '{label}' is not allowed.")
        rows = self._read(query, parameters, self.policy.max_rows)
        return {"source_id": self.policy.source_id, "rows": rows[: self.policy.max_rows]}


class KeyValueToolkit(Toolkit):
    def __init__(self, *, policy: DataAccessPolicy, get_value: Callable[[str], Any]) -> None:
        super().__init__("key_value")
        self.policy = policy
        self._get_value = get_value
        self.register(self.get, description="Read one value from an allowed key prefix.")

    def get(self, key: str) -> dict[str, Any]:
        self.policy.require_key(key)
        return {"source_id": self.policy.source_id, "key": key, "value": self._get_value(key)}


class RedisToolkit(KeyValueToolkit):
    """Read one governed key from a redis-py client."""

    def __init__(self, client: Any, *, policy: DataAccessPolicy) -> None:
        def get_value(key: str) -> Any:
            value = client.get(key)
            return value.decode() if isinstance(value, bytes) else value

        super().__init__(policy=policy, get_value=get_value)
        self.name = "redis"


class Neo4jToolkit(GraphToolkit):
    """Read bounded Cypher through an official Neo4j driver instance."""

    def __init__(self, driver: Any, *, policy: DataAccessPolicy) -> None:
        def labels() -> list[str]:
            with driver.session() as session:
                return [record["label"] for record in session.run("CALL db.labels() YIELD label RETURN label")]

        def read(query: str, parameters: dict[str, Any] | None, limit: int) -> list[dict[str, Any]]:
            with driver.session() as session:
                return [dict(record) for record in session.run(query, parameters or {})][:limit]

        super().__init__(policy=policy, labels=labels, read=read)
        self.name = "neo4j"


class ElasticsearchToolkit(DocumentToolkit):
    """Search one governed Elasticsearch index using exact-match filters."""

    def __init__(self, client: Any, *, index: str, policy: DataAccessPolicy) -> None:
        def find(collection: str, filter: dict[str, Any], limit: int) -> list[dict[str, Any]]:
            clauses = [{"term": {field: value}} for field, value in filter.items()]
            query = {"bool": {"filter": clauses}} if clauses else {"match_all": {}}
            response = client.search(index=collection, query=query, size=limit)
            return [hit.get("_source", {}) for hit in response["hits"]["hits"]]

        super().__init__(collection=index, policy=policy, find=find)
        self.name = "elasticsearch"
