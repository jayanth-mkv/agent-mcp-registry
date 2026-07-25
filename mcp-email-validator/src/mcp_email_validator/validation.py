"""Pure validation and deliberately bounded network-check helpers."""

from __future__ import annotations

import ipaddress
import re
import smtplib
from collections.abc import Iterable
from typing import Any

import dns.exception
import dns.resolver

MAX_ADDRESS_LENGTH = 254
MAX_LOCAL_PART_LENGTH = 64
MAX_BATCH_SIZE = 50
MAX_SMTP_HOSTS = 3
MIN_TIMEOUT_SECONDS = 1.0
MAX_TIMEOUT_SECONDS = 15.0
LOCAL_PART_PATTERN = re.compile(r"^[A-Za-z0-9.!#$%&'*+/=?^_`{|}~-]+$")


def _bounded_timeout(value: float) -> float:
    """Return a usable timeout without allowing callers to make probes linger."""
    return max(MIN_TIMEOUT_SECONDS, min(float(value), MAX_TIMEOUT_SECONDS))


def _normalise_address(address: str) -> tuple[str | None, str | None, str | None]:
    """Validate a conventional address and return normalized address and domain."""
    candidate = address.strip()
    if not candidate or len(candidate) > MAX_ADDRESS_LENGTH:
        return None, None, "Address must be between 1 and 254 characters."
    if candidate.count("@") != 1:
        return None, None, "Address must contain one @ separator."

    local_part, domain = candidate.rsplit("@", 1)
    if not local_part or len(local_part) > MAX_LOCAL_PART_LENGTH:
        return None, None, "Local part must be between 1 and 64 characters."
    if not LOCAL_PART_PATTERN.fullmatch(local_part):
        return None, None, "Local part contains unsupported characters."
    if local_part.startswith(".") or local_part.endswith(".") or ".." in local_part:
        return None, None, "Local part cannot begin, end, or repeat a dot."

    try:
        ascii_domain = domain.encode("idna").decode("ascii").lower()
    except UnicodeError:
        return None, None, "Domain cannot be converted to IDNA."
    if len(ascii_domain) > 253 or "." not in ascii_domain:
        return None, None, "Domain must be a fully qualified hostname."

    labels = ascii_domain.split(".")
    if any(
        not label
        or len(label) > 63
        or label.startswith("-")
        or label.endswith("-")
        or not all(character.isalnum() or character == "-" for character in label)
        for label in labels
    ):
        return None, None, "Domain contains an invalid hostname label."

    return f"{local_part}@{ascii_domain}", ascii_domain, None


def _resolver(timeout_seconds: float) -> dns.resolver.Resolver:
    resolver = dns.resolver.Resolver(configure=True)
    resolver.timeout = timeout_seconds
    resolver.lifetime = timeout_seconds
    return resolver


def _resolve_mail_hosts(domain: str, timeout_seconds: float) -> tuple[str, list[str], list[str]]:
    """Find MX hosts, falling back to the domain only when RFC fallback is possible."""
    resolver = _resolver(timeout_seconds)
    try:
        answers = resolver.resolve(domain, "MX")
        records = sorted(
            (int(record.preference), str(record.exchange).rstrip(".")) for record in answers
        )
        if any(host == "" for _, host in records):
            return "not_found", [], ["The domain publishes a null MX record and does not accept email."]
        hosts = [host for _, host in records]
        return "found", hosts, ["MX records were found for the domain."]
    except dns.resolver.NoAnswer:
        pass
    except dns.resolver.NXDOMAIN:
        return "not_found", [], ["The domain does not exist in DNS."]
    except dns.exception.Timeout:
        return "lookup_error", [], ["DNS lookup timed out before mail routes could be confirmed."]
    except dns.exception.DNSException:
        return "lookup_error", [], ["DNS lookup failed before mail routes could be confirmed."]

    try:
        resolver.resolve(domain, "A")
        return "fallback", [domain], ["No MX record; the domain has an A record and may use implicit MX fallback."]
    except dns.resolver.NoAnswer:
        pass
    except dns.resolver.NXDOMAIN:
        return "not_found", [], ["The domain does not exist in DNS."]
    except dns.exception.Timeout:
        return "lookup_error", [], ["DNS lookup timed out before mail routes could be confirmed."]
    except dns.exception.DNSException:
        return "lookup_error", [], ["DNS lookup failed before mail routes could be confirmed."]

    try:
        resolver.resolve(domain, "AAAA")
        return "fallback", [domain], ["No MX record; the domain has an AAAA record and may use implicit MX fallback."]
    except dns.resolver.NoAnswer:
        return "not_found", [], ["No MX, A, or AAAA mail route was found for the domain."]
    except dns.resolver.NXDOMAIN:
        return "not_found", [], ["The domain does not exist in DNS."]
    except dns.exception.Timeout:
        return "lookup_error", [], ["DNS lookup timed out before mail routes could be confirmed."]
    except dns.exception.DNSException:
        return "lookup_error", [], ["DNS lookup failed before mail routes could be confirmed."]


def _public_ip_for_host(host: str, timeout_seconds: float) -> str | None:
    """Resolve one publicly routable address, avoiding private-network SMTP probes."""
    resolver = _resolver(timeout_seconds)
    for record_type in ("A", "AAAA"):
        try:
            answers = resolver.resolve(host, record_type)
        except dns.resolver.NoAnswer:
            continue
        except dns.exception.DNSException:
            return None
        for answer in answers:
            try:
                candidate = ipaddress.ip_address(str(answer))
            except ValueError:
                continue
            if candidate.is_global:
                return str(candidate)
    return None


def _probe_smtp(address: str, hosts: Iterable[str], timeout_seconds: float) -> tuple[str, list[str]]:
    """Attempt the smallest SMTP conversation needed for a recipient signal."""
    attempted_hosts = 0
    errors: list[str] = []
    for host in list(hosts)[:MAX_SMTP_HOSTS]:
        public_ip = _public_ip_for_host(host, timeout_seconds)
        if not public_ip:
            errors.append(f"{host}: no publicly routable address was available")
            continue

        attempted_hosts += 1
        try:
            with smtplib.SMTP(host=public_ip, port=25, timeout=timeout_seconds) as client:
                client.ehlo_or_helo_if_needed()
                mail_code, _ = client.mail("mcp-email-validator@invalid.example")
                if mail_code >= 400:
                    errors.append(f"{host}: server did not accept the probe sender")
                    continue
                recipient_code, _ = client.rcpt(address)
        except (OSError, smtplib.SMTPException):
            errors.append(f"{host}: SMTP connection or protocol check failed")
            continue

        if 200 <= recipient_code < 300:
            return "accepted", [f"A recipient command was accepted by {host}."]
        if 500 <= recipient_code < 600:
            return "rejected", [f"A recipient command was rejected by {host}."]
        errors.append(f"{host}: SMTP server returned a temporary or indeterminate recipient response")

    if not attempted_hosts:
        return "unavailable", errors or ["No eligible public mail host was available for SMTP probing."]
    return "error", errors or ["SMTP probing did not produce a recipient response."]


def validate_address(
    address: str, *, check_smtp: bool = False, timeout_seconds: float = 10.0
) -> dict[str, Any]:
    """Return bounded syntax, DNS, and optional SMTP facts for one address."""
    timeout = _bounded_timeout(timeout_seconds)
    normalized, domain, syntax_error = _normalise_address(address)
    result: dict[str, Any] = {
        "address": address,
        "normalized_address": normalized,
        "syntax_valid": syntax_error is None,
        "domain": domain,
        "mail_route_status": "not_checked",
        "mail_hosts": [],
        "smtp_status": "not_requested",
        "notes": [],
    }
    if syntax_error:
        result["notes"] = [syntax_error, "DNS and SMTP checks were skipped."]
        return result

    route_status, hosts, route_notes = _resolve_mail_hosts(domain, timeout)
    result["mail_route_status"] = route_status
    result["mail_hosts"] = hosts
    result["notes"] = route_notes
    if not check_smtp:
        result["notes"].append("SMTP probing was not requested.")
        return result
    if not hosts:
        result["smtp_status"] = "unavailable"
        result["notes"].append("SMTP probing was skipped because no mail host was available.")
        return result

    smtp_status, smtp_notes = _probe_smtp(normalized, hosts, timeout)
    result["smtp_status"] = smtp_status
    result["notes"].extend(smtp_notes)
    return result


def validate_batch(
    addresses: list[str], *, check_smtp: bool = False, timeout_seconds: float = 10.0
) -> list[dict[str, Any]]:
    """Validate a deliberately small batch while preserving the caller's order."""
    if len(addresses) > MAX_BATCH_SIZE:
        raise ValueError(f"A batch can contain at most {MAX_BATCH_SIZE} addresses.")
    return [
        validate_address(address, check_smtp=check_smtp, timeout_seconds=timeout_seconds)
        for address in addresses
    ]
