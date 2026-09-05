"""Default tool factory: search_knowledge_base (RAG tool, agno pattern).

Exposes the Knowledge available in an Agent as a callable tool so the model can
decide when to search for context.
"""

from __future__ import annotations

from typing import Any, Optional

from .decorator import tool
from .function import Function


def create_knowledge_search_tool(knowledge: Any, name: str = "search_knowledge") -> Function:
    @tool(name=name)
    def _search(query: str, limit: int = 5) -> str:
        """Searches the knowledge base.

        Args:
            query: the search query for the knowledge base.
            limit: maximum number of results.
        """
        results = knowledge.search(query, limit=limit)
        if not results:
            return "No se encontraron documentos relevantes."
        lines = []
        for r in results:
            doc = r.document if hasattr(r, "document") else r
            content = doc.content if hasattr(doc, "content") else str(doc)
            score = getattr(r, "score", 0)
            lines.append(f"[score={score:.3f}] {content[:500]}")
        return "\n\n".join(lines)

    return getattr(_search, "function")