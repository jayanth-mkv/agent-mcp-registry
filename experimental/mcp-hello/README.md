# Hello MCP Worker

An experimental Cloudflare Worker exposing `sayHello(name)` and `getCurrentTime(message?)` through a stateless Streamable HTTP MCP endpoint at `/mcp`. Uses the official TypeScript MCP SDK.

## Run locally

Requires Node.js 22.12+ and npm. From this directory:

```bash
npm ci
npm run dev
```

Connect an HTTP-capable MCP client to `http://127.0.0.1:8787/mcp`.

## Verify

```bash
npm run typecheck
npm test
npm run build
npm audit
```

Tests use the MCP client SDK to initialize, discover tools, and call the Worker handler. The build command bundles with Wrangler using `--dry-run`; it does not deploy. Local workerd execution is checked separately in the [verification notes](../../docs/verification.md).

## Deploy

After configuring your own Cloudflare account:

```bash
npm run deploy
```

Deployment publishes a public endpoint without authentication. No cloud deployment is included in local verification. This demo has no database, API keys, or bindings.
