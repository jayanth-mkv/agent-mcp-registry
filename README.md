# Agent MCP Registry

Standalone Model Context Protocol servers for local file operations and email validation.

| Server | Tools | Documentation |
| --- | --- | --- |
| **File Server** | 14 tools to create, read, search, copy, move, and manage text files within a configured directory. | [mcp-files](mcp-files/README.md) |
| **Email Validator** | Single and batch syntax checks, DNS mail-route lookup, and optional SMTP recipient probing. | [mcp-email-validator](mcp-email-validator/README.md) |

Demo servers, AI clients, and the Postgres agent live in [experimental/](experimental/README.md).

## Install and run

Requires **Python 3.13+** and [uv](https://docs.astral.sh/uv/getting-started/installation/). These servers are installed from this repository; no PyPI publication is assumed.

```bash
git clone https://github.com/jayanth-mkv/agent-mcp-registry.git
cd agent-mcp-registry
```

File Server:

```bash
uv sync --project mcp-files --locked --no-dev
uv run --project mcp-files --locked --no-dev mcp-files --workspace ./workspace
```

Email Validator:

```bash
uv sync --project mcp-email-validator --locked --no-dev
uv run --project mcp-email-validator --locked --no-dev mcp-email-validator
```

Both default to **stdio** and wait for an MCP client. For a local Streamable HTTP endpoint:

```bash
uv run --project mcp-files --locked --no-dev mcp-files --transport http --workspace ./workspace
uv run --project mcp-email-validator --locked --no-dev mcp-email-validator --transport http
```

Run HTTP servers in separate terminals. Endpoints are `http://127.0.0.1:8000/mcp` and `http://127.0.0.1:8003/mcp`.

## Connect an MCP client

For clients supporting `mcpServers` configuration, replace the example paths with absolute paths on your machine. On Windows, use forward slashes or escaped backslashes in JSON. The client must be able to find `uv` on its PATH.

```json
{
  "mcpServers": {
    "files": {
      "command": "uv",
      "args": [
        "--directory", "/absolute/path/agent-mcp-registry/mcp-files",
        "run", "--locked", "--no-dev", "mcp-files",
        "--workspace", "/absolute/path/allowed-files"
      ]
    },
    "email-validator": {
      "command": "uv",
      "args": [
        "--directory", "/absolute/path/agent-mcp-registry/mcp-email-validator",
        "run", "--locked", "--no-dev", "mcp-email-validator"
      ]
    }
  }
}
```

## Usage boundaries

- File tools can modify and recursively delete data in the configured workspace. Use a dedicated directory. Links and junctions are rejected; this is a local tool, not an OS sandbox against other processes modifying the filesystem.
- Email checks do not prove mailbox ownership or guarantee delivery. SMTP probing is opt-in and never sends message data.
- HTTP and legacy SSE modes have no authentication. Keep them on loopback unless you provide a protected deployment.

## Development

Each Python project has its own manifest and lockfile. Install development dependencies and run its tests:

```bash
uv sync --project mcp-files --locked
uv run --project mcp-files --locked pytest mcp-files/tests -q
uv sync --project mcp-email-validator --locked
uv run --project mcp-email-validator --locked pytest mcp-email-validator/tests -q
```

The standalone packages are version **0.2.0**. Dependency updates are resolved in their lockfiles; see [verification notes](docs/verification.md) for the tested scope and remaining external checks. Each standalone server includes its own MIT license.
