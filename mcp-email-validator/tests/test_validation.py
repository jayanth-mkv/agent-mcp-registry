"""Deterministic DNS/SMTP coverage plus an installed stdio MCP session."""

import asyncio
import sys
from types import SimpleNamespace
from unittest.mock import MagicMock

import dns.exception
import dns.resolver
from fastmcp import Client
from fastmcp.client.transports import StdioTransport
import pytest

from mcp_email_validator import validation as v


@pytest.mark.parametrize("address", ["", "bad", "a..b@example.com", ".a@example.com", "a@localhost", "a@-bad.com"])
def test_invalid_address_never_uses_network(monkeypatch, address):
    lookup = MagicMock(side_effect=AssertionError("Network must not be used"))
    monkeypatch.setattr(v, "_resolve_mail_hosts", lookup)
    result = v.validate_address(address, check_smtp=True)
    assert not result["syntax_valid"]
    assert result["mail_route_status"] == "not_checked"
    lookup.assert_not_called()


def test_normalization_and_default_no_smtp(monkeypatch):
    monkeypatch.setattr(v, "_resolve_mail_hosts", lambda *args: ("found", ["mx.example.org"], []))
    smtp = MagicMock(side_effect=AssertionError("SMTP is opt-in"))
    monkeypatch.setattr(v, "_probe_smtp", smtp)
    result = v.validate_address(" User@EXAMPLE.ORG ")
    assert result["normalized_address"] == "User@example.org"
    assert result["smtp_status"] == "not_requested"
    smtp.assert_not_called()


def test_null_mx_does_not_fall_back(monkeypatch):
    resolver = MagicMock()
    resolver.resolve.return_value = [SimpleNamespace(preference=0, exchange=".")]
    monkeypatch.setattr(v, "_resolver", lambda timeout: resolver)
    status, hosts, _ = v._resolve_mail_hosts("example.com", 2)
    assert status == "not_found" and not hosts
    assert resolver.resolve.call_count == 1


def test_no_mx_falls_back_to_address_record(monkeypatch):
    resolver = MagicMock()
    resolver.resolve.side_effect = [dns.resolver.NoAnswer(), ["93.184.215.14"]]
    monkeypatch.setattr(v, "_resolver", lambda timeout: resolver)
    assert v._resolve_mail_hosts("example.com", 2)[:2] == ("fallback", ["example.com"])


def test_dns_timeout_is_reported(monkeypatch):
    resolver = MagicMock()
    resolver.resolve.side_effect = dns.exception.Timeout()
    monkeypatch.setattr(v, "_resolver", lambda timeout: resolver)
    assert v._resolve_mail_hosts("example.com", 2)[0] == "lookup_error"


def test_private_addresses_are_not_probed(monkeypatch):
    resolver = MagicMock()
    resolver.resolve.return_value = ["127.0.0.1", "10.0.0.1", "::1"]
    monkeypatch.setattr(v, "_resolver", lambda timeout: resolver)
    smtp = MagicMock(side_effect=AssertionError("Private SMTP must not be contacted"))
    monkeypatch.setattr(v.smtplib, "SMTP", smtp)
    assert v._probe_smtp("a@example.com", ["mx.example.com"], 2)[0] == "unavailable"
    smtp.assert_not_called()


def test_smtp_probe_never_sends_message(monkeypatch):
    monkeypatch.setattr(v, "_public_ip_for_host", lambda *args: "8.8.8.8")
    smtp = MagicMock()
    connection = smtp.return_value.__enter__.return_value
    connection.mail.return_value = (250, b"ok")
    connection.rcpt.return_value = (250, b"ok")
    monkeypatch.setattr(v.smtplib, "SMTP", smtp)
    assert v._probe_smtp("a@example.com", ["mx.example.com"], 2)[0] == "accepted"
    connection.rcpt.assert_called_once_with("a@example.com")
    connection.data.assert_not_called()
    connection.sendmail.assert_not_called()


def test_smtp_host_limit(monkeypatch):
    resolve = MagicMock(return_value=None)
    monkeypatch.setattr(v, "_public_ip_for_host", resolve)
    v._probe_smtp("a@example.com", [f"mx{i}.example.com" for i in range(10)], 2)
    assert resolve.call_count == 3


def test_timeout_and_batch_bounds():
    assert v._bounded_timeout(-1) == 1
    assert v._bounded_timeout(999) == 15
    with pytest.raises(ValueError, match="50"):
        v.validate_batch(["bad"] * 51)


def test_stdio_tools():
    async def check():
        transport = StdioTransport(command=sys.executable, args=["-m", "mcp_email_validator.cli"])
        async with Client(transport) as client:
            assert {t.name for t in await client.list_tools()} == {"validate_email", "validate_email_batch"}
            result = await client.call_tool("validate_email", {"address": "invalid"})
            assert result.data["syntax_valid"] is False
            batch = await client.call_tool("validate_email_batch", {"addresses": ["invalid"]})
            assert len(batch.data) == 1

    asyncio.run(check())
