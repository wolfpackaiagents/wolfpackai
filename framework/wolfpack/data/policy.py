"""Policies shared by live data-source tools."""

from __future__ import annotations

from dataclasses import dataclass, field


class DataPolicyError(ValueError):
    """Raised when an operation exceeds its configured data-access scope."""


@dataclass(frozen=True)
class DataAccessPolicy:
    """Server-side scope and result limits for one data source."""

    source_id: str
    allowed_tables: set[str] = field(default_factory=set)
    allowed_columns: dict[str, set[str]] = field(default_factory=dict)
    allowed_collections: set[str] = field(default_factory=set)
    allowed_graph_labels: set[str] = field(default_factory=set)
    allowed_key_prefixes: set[str] = field(default_factory=set)
    sensitive_columns: set[str] = field(default_factory=set)
    max_rows: int = 100
    timeout_seconds: float = 5.0
    max_bytes_scanned: int | None = None
    cost_budget_per_query: float | None = None
    require_explain: bool = False

    def __post_init__(self) -> None:
        if not self.source_id:
            raise DataPolicyError("source_id is required")
        if self.max_rows < 1:
            raise DataPolicyError("max_rows must be positive")
        if self.timeout_seconds <= 0:
            raise DataPolicyError("timeout_seconds must be positive")

    def require_table(self, table: str) -> None:
        if self.allowed_tables and table.lower() not in {item.lower() for item in self.allowed_tables}:
            raise DataPolicyError(f"Table '{table}' is not allowed for source '{self.source_id}'.")

    def require_collection(self, collection: str) -> None:
        if self.allowed_collections and collection not in self.allowed_collections:
            raise DataPolicyError(f"Collection '{collection}' is not allowed for source '{self.source_id}'.")

    def require_key(self, key: str) -> None:
        if self.allowed_key_prefixes and not any(key.startswith(prefix) for prefix in self.allowed_key_prefixes):
            raise DataPolicyError(f"Key '{key}' is not allowed for source '{self.source_id}'.")
