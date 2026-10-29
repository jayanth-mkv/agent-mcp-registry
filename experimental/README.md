# Experiments

Optional demonstrations kept separate from the standalone MCP servers.

| Entry | Purpose | Requirements |
| --- | --- | --- |
| [clients/base.py](clients/base.py) | Discover file tools and write `example.txt`. | Running File Server HTTP endpoint. |
| [clients/gemini.py](clients/gemini.py) | Let the Google Gen AI SDK call file tools. | File Server, Google API key, model access. |
| [agents/react_agent.py](agents/react_agent.py) | Interactive LangChain agent with file tools. | File Server, Google API key, model access. |
| [mcp-postgres](mcp-postgres/README.md) | Azure OpenAI agent using an external Postgres MCP. | Azure deployment and a Postgres MCP endpoint. |
| [mcp-hello](mcp-hello/README.md) | Cloudflare Worker exposing greeting and time tools. | Node.js 22.12+; Cloudflare account only for deployment. |

## File client examples

Start the standalone File Server in another terminal, from the repository root:

```bash
uv run --project mcp-files --locked --no-dev mcp-files --transport http --workspace ./workspace
```

Then, from `experimental/`:

```bash
uv sync --project clients --locked
uv run --project clients --locked clients/base.py
```

The base example writes or overwrites `example.txt` inside the file workspace. Set `MCP_FILES_URL` to override `http://127.0.0.1:8000/mcp`.

For either Google-backed example, set `GOOGLE_API_KEY` and `GEMINI_MODEL` to values available in your account. You can use a local `.env` file (see [.env.example](.env.example)). Model calls may incur provider charges and can modify workspace files.

```bash
uv run --project clients --locked clients/gemini.py
```

## LangChain agents

From `experimental/`:

```bash
uv sync --locked
uv run --locked agents/react_agent.py
```

The parent environment supplies LangChain and the Postgres agent. `clients/` has a separate manifest and lockfile because current LangChain MCP adapters require MCP SDK 1, while FastMCP 4 uses SDK 2. The environments communicate with the standalone server over HTTP.

AI provider calls and the external Postgres service require credentials and have not been verified by local offline tests. The Worker has its own npm setup and verification commands.
