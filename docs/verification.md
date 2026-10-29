# Verification

Checked locally on **2026-10-29**, using Windows, Python **3.13.7**, Node.js **22.23.4**, and uv **0.8.15**. These results describe local execution, not a production deployment or certification.

## Standalone servers

Both packages are version **0.2.0**, with **FastMCP 4.1.4** and **MCP Python SDK 2.3.0**. Email validation uses **dnspython 2.9.0**. Direct dependency requirements were checked against PyPI, updated to current stable releases, and resolved into separate lockfiles.

| Check | Result |
| --- | --- |
| Locked dependency installation | Passed for both servers. |
| Source distribution and wheel build | Passed for both servers. |
| Isolated wheel installation and CLI help | Passed for both servers outside their editable project environments. |
| File tests | 6 passed across the suite and added junction regression; 1 symlink test skipped because Windows did not allow symlink creation. |
| Email tests | 15 passed, including mocked DNS/SMTP behavior and stdio tool calls. |
| File stdio protocol session | All 14 tools exercised, including write/read/search/copy/move/delete; CLI workspace override and rejected escapes checked. |
| Email stdio protocol session | Both tools discovered and called with invalid addresses without network access. |
| Streamable HTTP and legacy SSE | Both servers started locally; tool discovery and representative calls passed on both transports. |
| Live email DNS lookup | MX records resolved successfully; SMTP was not requested. |
| LangChain adapter compatibility | MCP SDK 1 client discovered all 14 tools and called the FastMCP 4 HTTP server successfully. |

File checks cover relative and absolute path escapes, workspace-root protection, copying a directory into itself, and Windows junctions. The symlink regression remains in the suite and runs where the OS permits creating symlinks. Filesystem race conditions against other local processes are outside the server's isolation guarantee.

To run the retained Python tests, from the repository root:

```bash
uv sync --project mcp-files --locked
uv run --project mcp-files --locked pytest mcp-files/tests -q
uv sync --project mcp-email-validator --locked
uv run --project mcp-email-validator --locked pytest mcp-email-validator/tests -q
```

## Experiments

The LangChain environment locks **LangChain 1.4.7**, **LangGraph 1.2.18**, **langchain-mcp-adapters 0.3.2**, **langchain-google-genai 4.4.2**, and **langchain-openai 1.7.3**. The separate FastMCP client environment locks **google-genai 2.34.0** with FastMCP 4.1.4. Both environments install successfully, and the client and agent modules import successfully.

The LangChain adapter currently requires MCP SDK 1, so it is intentionally isolated from the FastMCP 4 client environment. This preserves compatible stable dependencies without forcing either environment onto an incompatible SDK.

The Worker uses **@modelcontextprotocol/sdk 1.32.2**, **Wrangler 4.155.0**, **TypeScript 7.0.2**, **Vitest 5.0.5**, and **Zod 4.6.7**.

| Worker check | Result |
| --- | --- |
| Clean `npm ci` | Passed. |
| `npm run typecheck` | Passed. |
| `npm test` | 2 passed; protocol initialization, discovery, tool calls, invalid input, and routing checked. |
| `npm run build` | Passed Wrangler dry-run bundle. |
| Local Wrangler/workerd | MCP client discovered and called the locally served Worker successfully. |
| `npm outdated` | No outdated direct dependencies reported. |
| `npm audit` | No known vulnerabilities reported at verification time. |

## External checks remaining

- Live Gemini model calls and tool execution through the Google SDK and LangChain agent require an API key and an available model.
- Azure OpenAI calls and the Postgres agent require the user's deployment, external MCP endpoint, schema, and database permissions.
- Real SMTP recipient probes were not performed. Acceptance does not establish ownership or guarantee delivery.
- No Cloudflare deployment or public authenticated deployment was performed.

Future upgrades should regenerate the appropriate lockfile and rerun the relevant checks. Test results and package versions above are a dated record.

## PyPI release verification — 2026-10-30

Both **0.2.0** releases were published by GitHub Actions from commit `c5b54f98f743ff7c88f171542c8b70985b6de88c`, using separate Trusted Publisher environments:

| Distribution | Release tag | Environment | Publishing result |
| --- | --- | --- | --- |
| [mcp-files-context](https://pypi.org/project/mcp-files-context/0.2.0/) | `mcp-files-v0.2.0` | `pypi-files` | [Actions succeeded](https://github.com/jayanth-mkv/agent-mcp-registry/actions/runs/40934572264) |
| [mcp-email-validator](https://pypi.org/project/mcp-email-validator/0.2.0/) | `mcp-email-validator-v0.2.0` | `pypi` | [Actions succeeded](https://github.com/jayanth-mkv/agent-mcp-registry/actions/runs/40934571806) |

The [package-check run](https://github.com/jayanth-mkv/agent-mcp-registry/actions/runs/40934277454) passed all five jobs: 14 release-guard tests and each package's tests, builds, metadata checks, and isolated wheel installation on Linux and Windows. Each release workflow repeated the selected package's Linux and Windows verification before uploading its verified Linux distributions through OIDC. Publishing used package attestations and no stored PyPI API token.

After publication, isolated installs from `https://pypi.org/simple` initialized both stdio servers and discovered the expected 14 file tools and 2 email tools. File creation/readback and workspace-root deletion rejection passed. Single and batch invalid-email calls passed without DNS or SMTP traffic. These checks used installed PyPI packages outside the repository, with no editable project environment.
