from fastmcp import FastMCP


mcp = FastMCP("Sample MCP")


@mcp.tool
def echo(text: str) -> dict[str, str]:
    """Echo a string for gateway integration tests."""
    return {"echo": text}


@mcp.tool
def add(left: int, right: int) -> int:
    """Add two integers."""
    return left + right


if __name__ == "__main__":
    mcp.run(transport="stdio", show_banner=False)
