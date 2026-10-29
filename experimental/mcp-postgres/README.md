# Postgres MCP Agent Example

An Azure OpenAI agent that connects to a separately hosted Postgres MCP server. This directory contains an agent example, not a Postgres MCP server or database deployment. Available database tools and access controls depend on the external server.

## Setup

Requires Python 3.13+, uv, an Azure OpenAI deployment, and a reachable Postgres MCP endpoint. From `experimental/`:

```bash
uv sync --locked
```

Create a local `.env` using [the example](../.env.example) and set:

- `AZURE_OPENAI_API_KEY`
- `AZURE_OPENAI_ENDPOINT`
- `AZURE_OPENAI_API_VERSION` supported by your deployment
- `AZURE_OPENAI_DEPLOYMENT_NAME`
- `MCP_RENDER_URL`, including the endpoint path
- `MCP_POSTGRES_TRANSPORT`: `http` (default) or `sse` for legacy endpoints

Use a read-only database role and an MCP endpoint you trust. The agent receives the endpoint's tools; this example does not enforce SQL access controls.

## Run

From `experimental/`:

```bash
uv run --locked mcp-postgres/main.py
```

The example asks for customer and order counts, retaining in-memory context between the two questions. Change the questions for your schema. There is no bundled Northwind database or expected row count.

The optional [notebook](ai_agent.ipynb) runs the same implementation. To use it with the project environment:

```bash
uv run --locked --with jupyterlab jupyter lab mcp-postgres/ai_agent.ipynb
```

Provider calls, database permissions, and the external MCP connection require separate live verification.
