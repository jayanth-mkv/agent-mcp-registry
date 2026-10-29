# Canvas MCP verification

## Local verification — 2026-10-30

Built on Windows x64 using Rust/Cargo **1.95.0**, official **rmcp 3.8.0**, **ureq 3.5.0**, **Tokio 1.54.1**, **serde_json 1.0.154**, and **url 2.5.8**. Dependency features and versions are recorded in `Cargo.toml` and `Cargo.lock`.

- 17 Rust unit tests passed, covering authentication placement, compact/full results, Unicode content windows, opaque pagination, origin/context restrictions, redirect rejection, response/output bounds, throttling, write envelopes/defaults, input validation, and credential-safe error messages.
- Clippy passed with warnings denied.
- Four release-guard tests and GitHub Actions workflow linting passed. The crate packaged and verified successfully.
- A dependency-free, independent JSON-RPC client initialized the optimized executable and exercised all 22 tools against an authenticated local HTTP mock in both read-only and write-enabled modes. Discovery, pagination continuation, input errors, disabled writes, content windows, and clean stdin-EOF shutdown passed.
- The downloaded Windows release executable passed the same independent protocol checks. Its local initialization was **7.77–9.20 ms**, with idle working set **6,414,336–6,430,720 bytes** after discovery and before HTTP calls.

Mock fixtures establish protocol and request behavior. They do not prove successful operation against an institution's production Canvas or that a particular user has student/teacher permissions.

## Verified release 0.1.0

[Release Actions run 40944253931](https://github.com/jayanth-mkv/agent-mcp-registry/actions/runs/40944253931) passed on all five platforms and published [crates.io 0.1.0](https://crates.io/crates/mcp-canvas-lms/0.1.0) and [native downloads](https://github.com/jayanth-mkv/agent-mcp-registry/releases/tag/mcp-canvas-lms-v0.1.0). The immutable tag `mcp-canvas-lms-v0.1.0` points to source commit `bc7043e6327369f8036008f203834e4844702003`.

Each platform passed formatting, Clippy with warnings denied, 17 Rust tests, an optimized release build, and the independent 22-tool protocol checks. A separate Rust 1.89 compatibility check passed. Publication compared the source crate with the build job's verified crate before using the repository token.

All five downloaded archive checksums matched their SHA-256 files. The crates.io version checksum matched the Actions-verified `.crate` archive: `0dced6ce7bc4d075b89b309c67b05883587e8123c8be57e25c57bb426bda659f`. The source archive is **30,746 bytes**.

| Platform | Executable bytes | Download bytes | CI idle memory, bytes |
| --- | ---: | ---: | ---: |
| Linux x64 | 1,605,512 | 732,885 | 4,993,024–4,997,120 |
| Linux ARM64 | 1,430,528 | 716,135 | 4,329,472–4,333,568 |
| macOS Apple Silicon | 1,207,920 | 646,850 | Not measured |
| macOS Intel | 1,392,332 | 679,845 | Not measured |
| Windows x64, static C runtime | 1,355,264 | 649,286 | 6,066,176–6,094,848 |

Memory samples were taken after tool discovery and before HTTP requests, across read-only and write-enabled sessions. These are individual observations on CI runners, not peak memory figures or performance guarantees. The release's `*-metrics.json` files include initialization timings and tool-schema sizes.

## Live checks remaining

With an authorized Canvas instance and token, run `mcp-canvas-lms --check`, then verify course visibility, real pagination, syllabus/page content, and student feedback. Teacher roster/submission reads depend on institutional scopes and permissions. Test mutations only in a suitable test course with explicit authorization. Real submissions, grades, assignment changes, and announcements have not been executed against a live Canvas account.

HTTPS certificate validation uses the native TLS backend and OS trust store. Mock HTTP tests do not establish institutional TLS, proxy compatibility, token issuance/renewal, or support for every self-hosted Canvas version.

A separate public-Canvas HTTPS probe using an intentionally invalid token reached HTTP 503. It did not verify authentication or institution-specific availability; no real credentials were used.
