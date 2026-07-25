# Email Validator MCP

A standalone [FastMCP](https://gofastmcp.com/) server for checking an email address without sending a message. It performs a pragmatic syntax check and DNS mail-routing lookup by default. SMTP recipient probing is deliberately opt-in because it opens a network connection to the recipient infrastructure and is only a delivery signal, not proof that a mailbox belongs to someone.

## Tools

| Tool | Default behavior | Optional behavior |
| --- | --- | --- |
| `validate_email` | Syntax and MX/A/AAAA mail-route lookup for one address. | With `check_smtp=true`, tries `EHLO`, `MAIL FROM`, and `RCPT TO` against up to three public mail hosts. It never sends `DATA`. |
| `validate_email_batch` | Runs the same local and DNS checks for up to 50 addresses. | SMTP probing remains opt-in and is rate-bounded by the same host and timeout limits for each address. |

The returned `smtp_status` is `not_requested`, `accepted`, `rejected`, `unavailable`, or `error`. An `accepted` response means only that the remote server accepted the SMTP command; catch-all domains, greylisting, and provider anti-abuse rules can make it inaccurate.

## Run locally

Requirements: Python 3.13+ and [uv](https://docs.astral.sh/uv/).

```bash
git clone https://github.com/jayanth-mkv/mcp-dump.git
cd mcp-dump/mcp-email-validator
uv sync
uv run mcp-email-validator --transport stdio
```

For a local HTTP or SSE endpoint, bind to loopback unless a protected deployment is intentional:

```bash
uv run mcp-email-validator --transport http --host 127.0.0.1 --port 8003
```

## Example result

```json
{
  "address": "hello@example.com",
  "normalized_address": "hello@example.com",
  "syntax_valid": true,
  "domain": "example.com",
  "mail_route_status": "found",
  "mail_hosts": ["mail.example.com"],
  "smtp_status": "not_requested",
  "notes": ["SMTP probing was not requested."]
}
```

## Safety boundaries

- SMTP is disabled unless the caller explicitly passes `check_smtp=true`.
- Syntax-invalid addresses do not trigger DNS or SMTP traffic.
- SMTP checks are limited to three mail hosts, one publicly routable IP per host, and a timeout clamped to 1–15 seconds.
- The server does not authenticate, send a message, retain addresses, or verify ownership of a mailbox.
- Use recipient probing only for addresses and infrastructure you are authorized to assess. Do not expose the HTTP or SSE transport directly to untrusted callers.

## Scope

The syntax check intentionally supports conventional unquoted mailbox addresses. It is not a full implementation of every RFC mailbox form. DNS and SMTP results can change between calls, and a successful result should not be treated as consent or a guarantee of deliverability.

This subproject is licensed under the [MIT License](LICENSE).
