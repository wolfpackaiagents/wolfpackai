"""Local MCP server used by 01_stdio_client.py."""

from mcp.server.fastmcp import FastMCP

mcp = FastMCP("wolfpack-example")


@mcp.tool()
def multiply(left: int, right: int) -> str:
    """Multiplies two integers."""
    return str(left * right)


if __name__ == "__main__":
    mcp.run(transport="stdio")
