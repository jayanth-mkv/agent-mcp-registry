"""Email Validator MCP server package."""

from __future__ import annotations

from .mcp import mcp
from .tools import validate_email, validate_email_batch

__all__ = ["mcp", "run", "validate_email", "validate_email_batch"]


def run(
    host: str = "127.0.0.1", port: int = 8003, transport: str = "stdio"
) -> None:
    """Run the server with the requested local transport."""
    if transport in {"sse", "http"}:
        mcp.run(transport=transport, host=host, port=port)
    else:
        mcp.run(transport=transport)
