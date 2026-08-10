import base64

from fastmcp import FastMCP
from fastmcp.utilities.types import Image


mcp = FastMCP("Sample MCP")


@mcp.tool
def echo(text: str) -> dict[str, str]:
    """Echo a string for gateway integration tests."""
    return {"echo": text}


@mcp.tool
def add(left: int, right: int) -> int:
    """Add two integers."""
    return left + right


@mcp.tool
def screenshot() -> Image:
    """Return a tiny PNG to test native image forwarding."""
    png = base64.b64decode(
        "iVBORw0KGgoAAAANSUhEUgAAAAEAAAABCAQAAAC1HAwCAAAAC0lEQVR42mNk+A8AAQUBAScY42YAAAAASUVORK5CYII="
    )
    return Image(data=png, format="png")


if __name__ == "__main__":
    mcp.run(transport="stdio", show_banner=False)
