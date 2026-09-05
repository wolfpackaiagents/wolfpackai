"""MCP client adapter that exposes remote tools as Wolfpack Functions."""

from __future__ import annotations

from typing import Any, List

from ..tools.function import Function


class MCPClient:
    """Wraps an initialized MCP ClientSession.

    The caller owns the MCP transport/session lifecycle. This keeps stdio, SSE and
    streamable HTTP transport choices outside the framework's tool abstraction.
    """

    def __init__(self, session: Any):
        self.session = session

    async def get_tools(self) -> List[Function]:
        response = await self.session.list_tools()
        return [self._to_function(tool) for tool in response.tools]

    def _to_function(self, tool: Any) -> Function:
        name = tool.name
        description = tool.description or f"MCP tool: {name}"
        parameters = getattr(tool, "inputSchema", None) or getattr(tool, "input_schema", None) or {"type": "object"}

        async def invoke(**arguments: Any) -> str:
            result = await self.session.call_tool(name, arguments)
            if getattr(result, "isError", False):
                raise RuntimeError(self._result_text(result))
            return self._result_text(result)

        return Function(name=name, description=description, entrypoint=invoke, parameters=parameters)

    @staticmethod
    def _result_text(result: Any) -> str:
        content = getattr(result, "content", result)
        if isinstance(content, str):
            return content
        return "\n".join(
            item.get("text", str(item)) if isinstance(item, dict) else getattr(item, "text", str(item))
            for item in content
        )
