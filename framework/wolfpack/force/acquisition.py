"""Data acquisition and normalization from various sources into TaskItems."""

from __future__ import annotations

import inspect
import json
from typing import Any, Dict, List, Optional, Protocol, runtime_checkable
from .spec import TaskItem


@runtime_checkable
class DataSource(Protocol):
    """Protocol for searchable data sources (Knowledge, OKFBundle, custom stores)."""

    def search(self, query: str, limit: Optional[int] = None) -> List[Any]:
        ...


def normalize_to_tasks(
    data: Optional[List[Any]] = None,
    data_source: Optional[Any] = None,
    toolkit: Optional[Any] = None,
    policy: Optional[Any] = None,
    mission: str = "",
    default_pool: str = "default",
) -> List[TaskItem]:
    """Extracts, queries, or transforms diverse data sources into a unified list of TaskItems.

    Supported sources:
    1. Direct list of dicts/items (`data`)
    2. SQLToolkit query execution (`toolkit`)
    3. Vector Knowledge or OKFBundle (`data_source`)
    4. DataAccessPolicy scoping and limits
    """
    tasks: List[TaskItem] = []

    # 1. Direct data list
    if data:
        for idx, item in enumerate(data):
            if isinstance(item, TaskItem):
                tasks.append(item)
            elif isinstance(item, dict):
                # Detect pool assignment if present in the data dict
                pool = item.get("pool") or item.get("target_pool") or "default"
                desc = item.get("description") or item.get("title") or item.get("prompt") or f"Task #{idx + 1}"
                task_id = item.get("id") or item.get("task_id")
                tasks.append(
                    TaskItem(
                        id=str(task_id) if task_id else f"task_{idx + 1}",
                        input=item,
                        description=str(desc),
                        pool=str(pool),
                        metadata={"source": "direct_data", "index": idx},
                    )
                )
            else:
                tasks.append(
                    TaskItem(
                        id=f"task_{idx + 1}",
                        input=item,
                        description=str(item)[:80],
                        pool=default_pool,
                        metadata={"source": "direct_data", "index": idx},
                    )
                )

    # 2. SQL / Analytics Toolkit
    if toolkit:
        sql_rows = _acquire_from_toolkit(toolkit, policy, mission)
        for idx, row in enumerate(sql_rows):
            pool = row.get("pool") or default_pool
            desc = row.get("description") or row.get("prompt") or f"SQL Item #{idx + 1}"
            tasks.append(
                TaskItem(
                    id=str(row.get("id") or f"sql_{idx + 1}"),
                    input=row,
                    description=str(desc),
                    pool=str(pool),
                    metadata={"source": "sql_toolkit", "row_index": idx},
                )
            )

    # 3. Knowledge / OKF DataSource
    if data_source and hasattr(data_source, "search"):
        grounding_items = _acquire_from_datasource(data_source, mission)
        for idx, item in enumerate(grounding_items):
            tasks.append(
                TaskItem(
                    id=item.get("id") or f"kb_{idx + 1}",
                    input=item,
                    description=item.get("description") or f"Knowledge Item #{idx + 1}",
                    pool=item.get("pool") or default_pool,
                    metadata={"source": "data_source", "score": item.get("score")},
                )
            )

    return tasks


def _acquire_from_toolkit(toolkit: Any, policy: Optional[Any], mission: str) -> List[Dict[str, Any]]:
    """Runs a governed SQL query using the toolkit if available."""
    query_fn = getattr(toolkit, "query", None)
    if not callable(query_fn):
        return []

    # If policy defines allowed tables, pick the first allowed table
    target_table = None
    if policy and getattr(policy, "allowed_tables", None):
        tables = list(policy.allowed_tables)
        if tables:
            target_table = tables[0]

    limit = 100
    if policy and getattr(policy, "max_rows", None):
        limit = min(policy.max_rows, 500)

    try:
        if target_table:
            sql = f"SELECT * FROM {target_table} LIMIT {limit}"
            result = query_fn(sql)
            if isinstance(result, dict) and "rows" in result:
                return result["rows"]
    except Exception:
        pass
    return []


def _acquire_from_datasource(data_source: Any, mission: str) -> List[Dict[str, Any]]:
    """Retrieves chunks or concepts from a Knowledge base or OKFBundle."""
    results: List[Dict[str, Any]] = []
    try:
        search_fn = getattr(data_source, "search")
        # Handle async vs sync search
        if inspect.iscoroutinefunction(search_fn):
            import asyncio
            try:
                loop = asyncio.get_running_loop()
            except RuntimeError:
                raw_results = asyncio.run(search_fn(mission))
            else:
                import concurrent.futures
                with concurrent.futures.ThreadPoolExecutor(max_workers=1) as pool:
                    raw_results = pool.submit(asyncio.run, search_fn(mission)).result()
        else:
            raw_results = search_fn(mission, limit=20)

        for item in raw_results or []:
            # SearchResult from Knowledge
            if hasattr(item, "text"):
                results.append({
                    "id": getattr(item, "id", None) or f"chunk_{len(results) + 1}",
                    "content": item.text,
                    "score": getattr(item, "score", 1.0),
                    "description": item.text[:100],
                    "metadata": getattr(item, "metadata", {}) or {},
                })
            # Concept from OKFBundle
            elif hasattr(item, "title") and hasattr(item, "content"):
                results.append({
                    "id": getattr(item, "id", None) or item.title,
                    "content": item.content,
                    "description": item.title,
                    "tags": getattr(item, "tags", []),
                    "metadata": {"okf_concept": True},
                })
            elif isinstance(item, dict):
                results.append(item)
    except Exception:
        pass
    return results
