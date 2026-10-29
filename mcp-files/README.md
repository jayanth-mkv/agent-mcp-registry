# File Server MCP

An MCP server with 14 tools for managing UTF-8 text files within a configured workspace. No API key or external service is required.

## Run without cloning

Requires [uv](https://docs.astral.sh/uv/getting-started/installation/) and Git. uv downloads the selected package and manages Python 3.13 and its dependencies:

```bash
uvx --python 3.13 --from "git+https://github.com/jayanth-mkv/agent-mcp-registry.git@main#subdirectory=mcp-files" mcp-files --workspace ./workspace
```

Only this MCP and its runtime dependencies are installed. uv fetches the repository internally; you do not need a local checkout. To pin the source, replace `main` with a release tag or full commit SHA.

PyPI publishing is configured through GitHub Actions under the distribution name `agent-mcp-registry-files`; its command remains `mcp-files`. After the first PyPI release is confirmed, run `uvx --python 3.13 --from agent-mcp-registry-files==0.2.0 mcp-files --workspace ./workspace`. Until then, use the GitHub command above. See the [release guide](https://github.com/jayanth-mkv/agent-mcp-registry/blob/main/docs/publishing.md).

## Install from source

From this directory, with Python 3.13+ and [uv](https://docs.astral.sh/uv/getting-started/installation/):

```bash
uv sync --locked --no-dev
uv run --locked --no-dev mcp-files --workspace ./workspace
```

The default transport is stdio. Configure your MCP client using the [repository example](https://github.com/jayanth-mkv/agent-mcp-registry#connect-an-mcp-client).

For Streamable HTTP:

```bash
uv run --locked --no-dev mcp-files --transport http --host 127.0.0.1 --port 8000 --workspace ./workspace
```

Endpoint: `http://127.0.0.1:8000/mcp`. Legacy SSE is available with `--transport sse` at `/sse`.

## Tools

| Tool | Arguments | Behavior |
| --- | --- | --- |
| `create_file` | `path`, `content=""` | Create a new file; fail if it exists. |
| `read_file` | `path` | Read UTF-8 text. |
| `write_file` | `path`, `content` | Create or overwrite a text file. |
| `append_file` | `path`, `content` | Append text; create the file if missing. |
| `delete_path` | `path` | Delete a file or recursively delete a directory. |
| `rename_path` | `src`, `dst` | Rename a file or directory. |
| `copy_path` | `src`, `dst` | Copy a file or directory; merge existing directories. |
| `move_path` | `src`, `dst` | Move a file or directory. |
| `list_files` | None | List workspace files recursively. |
| `list_dirs` | None | List workspace directories recursively. |
| `search_file` | `path`, `term` | Return matching lines with line numbers. |
| `file_info` | `path` | Return JSON metadata. |
| `workspace_stats` | None | Return JSON counts, sizes, and extensions. |
| `path_exists` | `path` | Return `file`, `dir`, or `none`. |

Paths resolve inside the configured workspace. Parent directories are created when writing files. Relative workspace paths resolve from the process working directory; prefer an absolute workspace path in client configuration.

## Configuration

| Setting | Environment variable | Default |
| --- | --- | --- |
| Workspace | `MCP_WORKSPACE_DIR` | `./workspace` |
| HTTP/SSE host | `MCP_SERVER_HOST` | `127.0.0.1` |
| HTTP/SSE port | `MCP_SERVER_PORT` | `8000` |

CLI flags override environment settings. `--workspace` is applied before the server starts. Startup diagnostics use stderr so stdout remains available for MCP messages.

## Boundaries

Use a dedicated workspace: callers have read and write access, including recursive deletion. The workspace root itself cannot be deleted, renamed, or moved. Symbolic links and Windows junctions are unsupported and rejected, including links inside copied directory trees. These checks do not provide isolation against concurrent filesystem changes by other processes.

The server has no authentication or size quotas. Keep HTTP/SSE on loopback. Text tools read complete files into memory and are intended for small local text files.

## Development

```bash
uv sync --locked
uv run --locked pytest -q
uv build
```

The CLI is now `mcp-files`; the former nested `mcp-server` workspace has been consolidated into this package. AI clients are in [experimental/](https://github.com/jayanth-mkv/agent-mcp-registry/tree/main/experimental).

Version 0.2.0. Licensed under the [MIT License](https://github.com/jayanth-mkv/agent-mcp-registry/blob/main/mcp-files/LICENSE).
