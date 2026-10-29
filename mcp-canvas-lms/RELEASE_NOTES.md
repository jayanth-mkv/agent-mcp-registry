# Canvas LMS MCP 0.1.0

Native Rust stdio server for students and teachers, with 17 read tools and five optional write tools. Read-only by default; write mode requires `CANVAS_ENABLE_WRITES=true` and the user's Canvas permissions.

Install with `cargo install mcp-canvas-lms --version 0.1.0 --locked`, or download the archive matching your OS and architecture. Each archive has a SHA-256 file. Linux binaries use system OpenSSL 3 and CA certificates; Windows downloads link the C runtime statically.

The server uses pooled connections, one active Canvas request, compact paginated results, Unicode-safe content windows, bounded input/output, and retries only for eligible reads. Credentials stay in runtime environment variables or a token file. There is no Python/Node runtime or application database.

Platform artifacts include measured binary size and initialization/idle-memory reports. Mock API and independent MCP tests run in CI; a real institution's Canvas permissions and mutations require separate live verification. See the packaged README and repository verification notes for setup and limits.
