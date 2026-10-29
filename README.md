# Agent MCP Registry

Standalone Model Context Protocol servers for local file operations and email validation.

| Server | Tools | Documentation |
| --- | --- | --- |
| **File Server** ([mcp-files-context](https://pypi.org/project/mcp-files-context/)) | 14 tools to create, read, search, copy, move, and manage text files within a configured directory. | [mcp-files](mcp-files/README.md) |
| **Email Validator** ([mcp-email-validator](https://pypi.org/project/mcp-email-validator/)) | Single and batch syntax checks, DNS mail-route lookup, and optional SMTP recipient probing. | [mcp-email-validator](mcp-email-validator/README.md) |

Demo servers, AI clients, and the Postgres agent live in [experimental/](experimental/README.md).

## Install and run

Requires [uv](https://docs.astral.sh/uv/getting-started/installation/). Choose the server you need; no Git, clone, or installation of the other MCP is required. uv manages Python 3.13 and an isolated runtime environment.

File Server:

```bash
uvx --python 3.13 --from mcp-files-context==0.2.0 mcp-files --workspace ./workspace
```

Email Validator:

```bash
uvx --python 3.13 mcp-email-validator@0.2.0
```

Only the selected package and its runtime dependencies are installed from PyPI. The file distribution is named `mcp-files-context` and provides the `mcp-files` command. For unreleased changes, use the GitHub source commands in each server's README. Use a source checkout with `uv sync --locked` when you need the checked-in dependency lockfile.

Both default to **stdio** and wait for an MCP client. Add `--transport http` to start a local Streamable HTTP endpoint instead: File Server uses `http://127.0.0.1:8000/mcp`, and Email Validator uses `http://127.0.0.1:8003/mcp`.

Both packages have a verified **0.2.0** release on PyPI. Independent releases run through GitHub Actions; see [publishing and release setup](docs/publishing.md).

## Connect an MCP client

For clients supporting `mcpServers` configuration, copy only the entry you need. Replace the file workspace with an absolute path on your machine. On Windows, use forward slashes or escaped backslashes in JSON. The client must be able to find `uvx` on its PATH.

```json
{
  "mcpServers": {
    "files": {
      "command": "uvx",
      "args": [
        "--python", "3.13",
        "--from", "mcp-files-context==0.2.0",
        "mcp-files",
        "--workspace", "/absolute/path/allowed-files"
      ]
    },
    "email-validator": {
      "command": "uvx",
      "args": [
        "--python", "3.13",
        "mcp-email-validator@0.2.0"
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
git clone https://github.com/jayanth-mkv/agent-mcp-registry.git
cd agent-mcp-registry
uv sync --project mcp-files --locked
uv run --project mcp-files --locked pytest mcp-files/tests -q
uv sync --project mcp-email-validator --locked
uv run --project mcp-email-validator --locked pytest mcp-email-validator/tests -q
```

The standalone packages are version **0.2.0**. Dependency updates are resolved in their lockfiles; see [verification notes](docs/verification.md) for the tested scope and remaining external checks. Each standalone server includes its own MIT license.
