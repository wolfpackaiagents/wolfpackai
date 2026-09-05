import asyncio

from wolfpack.mcp import MCPClient


class FakeSession:
    async def list_tools(self):
        tool = type("Tool", (), {"name": "lookup", "description": "Looks up data", "inputSchema": {"type": "object", "properties": {"query": {"type": "string"}}}})()
        return type("Tools", (), {"tools": [tool]})()

    async def call_tool(self, name, arguments):
        assert (name, arguments) == ("lookup", {"query": "wolfpack"})
        return type("Result", (), {"content": [type("Text", (), {"text": "found"})()], "isError": False})()


def test_mcp_tools_are_exposed_as_wolfpack_functions():
    client = MCPClient(FakeSession())
    function = asyncio.run(client.get_tools())[0]

    assert function.name == "lookup"
    assert function.get_tool_schema()["parameters"]["properties"]["query"]["type"] == "string"
    assert asyncio.run(function.entrypoint(query="wolfpack")) == "found"
