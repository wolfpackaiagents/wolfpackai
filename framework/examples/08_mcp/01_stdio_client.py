"""Discover and call an actual MCP stdio tool through Wolfpack's adapter.

    uv run python examples/08_mcp/01_stdio_client.py
"""

import asyncio
from pathlib import Path

from mcp import ClientSession
from mcp.client.stdio import StdioServerParameters, stdio_client

from wolfpack import MCPClient


async def main() -> None:
    server = Path(__file__).with_name("local_server.py")
    params = StdioServerParameters(command="uv", args=["run", "python", str(server)])
    async with stdio_client(params) as (read, write):
        async with ClientSession(read, write) as session:
            await session.initialize()
            function = (await MCPClient(session).get_tools())[0]
            print(f"{function.name}(6, 7) = {await function.entrypoint(left=6, right=7)}")


if __name__ == "__main__":
    asyncio.run(main())
