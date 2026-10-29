# Email Validator MCP

An MCP server for checking email syntax and DNS mail routes without sending a message. Optional SMTP probing provides a recipient acceptance signal; it does not prove ownership or guarantee delivery.

## Run without cloning

Requires [uv](https://docs.astral.sh/uv/getting-started/installation/) and Git. uv downloads the selected package and manages Python 3.13 and its dependencies:

```bash
uvx --python 3.13 --from "git+https://github.com/jayanth-mkv/agent-mcp-registry.git@main#subdirectory=mcp-email-validator" mcp-email-validator
```

Only this MCP and its runtime dependencies are installed. uv fetches the repository internally; you do not need a local checkout. To pin the source, replace `main` with a release tag or full commit SHA.

PyPI publishing is configured through GitHub Actions. After the first PyPI release is confirmed, the equivalent versioned command is `uvx --python 3.13 mcp-email-validator@0.2.0`. Until then, use the GitHub command above. See the [release guide](https://github.com/jayanth-mkv/agent-mcp-registry/blob/main/docs/publishing.md).

## Install from source

From this directory, with Python 3.13+ and [uv](https://docs.astral.sh/uv/getting-started/installation/):

```bash
uv sync --locked --no-dev
uv run --locked --no-dev mcp-email-validator
```

The default transport is stdio. Configure your MCP client using the [repository example](https://github.com/jayanth-mkv/agent-mcp-registry#connect-an-mcp-client). No API key is required; DNS checks need network access.

For Streamable HTTP:

```bash
uv run --locked --no-dev mcp-email-validator --transport http --host 127.0.0.1 --port 8003
```

Endpoint: `http://127.0.0.1:8003/mcp`. Legacy SSE is available with `--transport sse` at `/sse`. HTTP and SSE have no authentication; keep them on loopback unless protected separately.

## Tools

| Tool | Required argument | Optional arguments |
| --- | --- | --- |
| `validate_email` | `address: string` | `check_smtp=false`, `timeout_seconds=10` |
| `validate_email_batch` | `addresses: string[]` (up to 50) | `check_smtp=false`, `timeout_seconds=10` |

Both tools check conventional unquoted mailbox syntax and normalize the domain, then look up MX records. Domains without MX records may use A/AAAA fallback; a null MX means the domain does not accept mail. Invalid syntax skips DNS and SMTP.

Example tool arguments:

```json
{ "address": "user@example.com", "check_smtp": false }
```

Results contain `normalized_address`, `syntax_valid`, `mail_route_status`, `mail_hosts`, `smtp_status`, and explanatory `notes`.

| Field | Possible values |
| --- | --- |
| `mail_route_status` | `not_checked`, `found`, `fallback`, `not_found`, `lookup_error` |
| `smtp_status` | `not_requested`, `accepted`, `rejected`, `unavailable`, `error` |

## SMTP boundaries

SMTP probing is disabled unless `check_smtp=true`. It tries at most three mail hosts, connects to one public IP per host on port 25, and uses SMTP greeting, sender, and recipient commands. It never sends `DATA` or authenticates. DNS lookups and socket operations use a timeout clamped to 1–15 seconds; this is not a total request deadline, and batches run sequentially.

Use probing only for infrastructure and addresses you are authorized to assess. Catch-all domains, greylisting, sender policy, and anti-abuse controls can produce misleading results. Private and loopback IP addresses are not contacted. Address data is not written to an application database; DNS queries and optional SMTP probes are visible to the contacted infrastructure.

## Development

```bash
uv sync --locked
uv run --locked pytest -q
uv build
```

Tests mock DNS/SMTP network operations and exercise the installed stdio server. Live recipient acceptance and delivery are separate checks.

Version 0.2.0. Licensed under the [MIT License](https://github.com/jayanth-mkv/agent-mcp-registry/blob/main/mcp-email-validator/LICENSE).
