# Agent MCP Registry

Independent Model Context Protocol servers for Canvas LMS, local files, and email validation.

| Server | Tools | Documentation |
| --- | --- | --- |
| **Canvas LMS** (Rust) | 17 read tools and 5 optional write tools for student and teacher workflows. | [mcp-canvas-lms](mcp-canvas-lms/README.md) |
| **File Server** ([mcp-files-context](https://pypi.org/project/mcp-files-context/)) | 14 tools to create, read, search, copy, move, and manage text files within a configured directory. | [mcp-files](mcp-files/README.md) |
| **Email Validator** ([mcp-email-validator](https://pypi.org/project/mcp-email-validator/)) | Single and batch syntax checks, DNS mail-route lookup, and optional SMTP recipient probing. | [mcp-email-validator](mcp-email-validator/README.md) |

Demo servers, AI clients, and the Postgres agent live in [experimental/](experimental/README.md).

## Install and run

Choose the server you need; each installs independently. The Canvas server is a native executable with [Cargo and prebuilt-download instructions](mcp-canvas-lms/README.md). The Python servers below require [uv](https://docs.astral.sh/uv/getting-started/installation/), which manages Python 3.13 and an isolated runtime environment.

File Server:

```bash
uvx --python 3.13 --from mcp-files-context==0.2.0 mcp-files --workspace ./workspace
```

Email Validator:

```bash
uvx --python 3.13 mcp-email-validator@0.2.0
```

Only the selected package and its runtime dependencies are installed from PyPI. The file distribution is named `mcp-files-context` and provides the `mcp-files` command. For unreleased changes, use the GitHub source commands in each server's README. Use a source checkout with `uv sync --locked` when you need the checked-in dependency lockfile.

The Python servers default to **stdio** and wait for an MCP client. Add `--transport http` to start a local Streamable HTTP endpoint instead: File Server uses `http://127.0.0.1:8000/mcp`, and Email Validator uses `http://127.0.0.1:8003/mcp`. Canvas uses stdio only.

Both Python packages have a verified **0.2.0** release on PyPI; see [publishing and release setup](docs/publishing.md). Canvas has its own Rust build/release workflow and [verification record](mcp-canvas-lms/VERIFICATION.md).

## Connect an MCP client

For clients supporting `mcpServers` configuration, copy only the entry you need. Replace the file workspace with an absolute path on your machine. On Windows, use forward slashes or escaped backslashes in JSON. The client must be able to find `uvx` on its PATH.

For Canvas, use the native executable and token-file configuration in its [README](mcp-canvas-lms/README.md#configure).

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

Each project has its own manifest and lockfile. Canvas's Rust build/test commands are in its README. For the Python servers:

```bash
git clone https://github.com/jayanth-mkv/agent-mcp-registry.git
cd agent-mcp-registry
uv sync --project mcp-files --locked
uv run --project mcp-files --locked pytest mcp-files/tests -q
uv sync --project mcp-email-validator --locked
uv run --project mcp-email-validator --locked pytest mcp-email-validator/tests -q
```

The Python packages are version **0.2.0** and Canvas is **0.1.0**. Dependency versions are resolved in their respective lockfiles. See the Python [verification notes](docs/verification.md) and Canvas's own verification record for tested scope and remaining live checks. Each server includes its own MIT license.
