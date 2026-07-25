"""MCP tool definitions for bounded email validation."""

from __future__ import annotations

from typing import Any

from .mcp import mcp
from .validation import MAX_BATCH_SIZE, validate_address, validate_batch


@mcp.tool
def validate_email(
    address: str, check_smtp: bool = False, timeout_seconds: float = 10.0
) -> dict[str, Any]:
    """Check one email's syntax and mail route; SMTP probing is opt-in and sends no mail."""
    return validate_address(
        address, check_smtp=check_smtp, timeout_seconds=timeout_seconds
    )


@mcp.tool
def validate_email_batch(
    addresses: list[str], check_smtp: bool = False, timeout_seconds: float = 10.0
) -> list[dict[str, Any]]:
    """Validate up to 50 addresses with optional, bounded SMTP recipient probes."""
    if len(addresses) > MAX_BATCH_SIZE:
        return [
            {
                "error": f"Batch limit exceeded: submit at most {MAX_BATCH_SIZE} addresses.",
                "smtp_status": "not_requested",
            }
        ]
    return validate_batch(
        addresses, check_smtp=check_smtp, timeout_seconds=timeout_seconds
    )
