"""Command-line entry point for Email Validator MCP."""

from __future__ import annotations

import argparse

from . import run


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="Run the Email Validator MCP server.")
    parser.add_argument(
        "--transport",
        choices=["stdio", "sse", "http"],
        default="stdio",
        help="MCP transport (default: stdio).",
    )
    parser.add_argument(
        "--host",
        default="127.0.0.1",
        help="Host for HTTP or SSE transport (default: 127.0.0.1).",
    )
    parser.add_argument(
        "--port",
        type=int,
        default=8003,
        help="Port for HTTP or SSE transport (default: 8003).",
    )
    return parser


def main(argv: list[str] | None = None) -> None:
    args = build_parser().parse_args(argv)
    run(host=args.host, port=args.port, transport=args.transport)


if __name__ == "__main__":  # pragma: no cover
    main()
