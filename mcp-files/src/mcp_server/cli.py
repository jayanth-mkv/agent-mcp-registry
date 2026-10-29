"""Command line interface for the mcp-server package.

Usage examples:
  uv run mcp-files --transport http --port 9000
  python -m mcp_server.cli --transport sse
"""

from __future__ import annotations

import argparse
from typing import Optional

from . import run as run_programmatic
from .config import DEFAULT_HOST, DEFAULT_PORT


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="Run the MCP file server.")
    parser.add_argument(
        "--host",
        default=None,
        help=f"Host interface to bind (default: env MCP_SERVER_HOST or {DEFAULT_HOST})",
    )
    parser.add_argument(
        "--port",
        type=int,
        default=None,
        help=f"Port to listen on (default: env MCP_SERVER_PORT or {DEFAULT_PORT})",
    )
    parser.add_argument(
        "--transport",
        default="stdio",
        choices=["sse", "http", "stdio"],
        help="MCP transport (default: stdio; sse is a legacy option).",
    )
    parser.add_argument(
        "--workspace",
        default=None,
        help="Workspace directory (default: MCP_WORKSPACE_DIR or ./workspace).",
    )
    return parser


def main(argv: Optional[list[str]] = None) -> None:
    parser = build_parser()
    args = parser.parse_args(argv)

    run_programmatic(host=args.host, port=args.port, transport=args.transport, workspace=args.workspace)


if __name__ == "__main__":  # pragma: no cover
    main()
