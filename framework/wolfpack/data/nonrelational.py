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
        return {"source_id": self.policy.source_id, "documents": documents[: self.policy.max_rows]}


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
