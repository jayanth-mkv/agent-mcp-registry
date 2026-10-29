# Canvas MCP verification

## Local verification — 2026-10-30

Built on Windows x64 using Rust/Cargo **1.95.0**, official **rmcp 3.8.0**, **ureq 3.5.0**, **Tokio 1.54.1**, **serde_json 1.0.154**, and **url 2.5.8**. Dependency features and versions are recorded in `Cargo.toml` and `Cargo.lock`.

- 17 Rust unit tests passed, covering authentication placement, compact/full results, Unicode content windows, opaque pagination, origin/context restrictions, redirect rejection, response/output bounds, throttling, write envelopes/defaults, input validation, and credential-safe error messages.
- Clippy passed with warnings denied.
- Four release-guard tests and GitHub Actions workflow linting passed. The crate packaged and verified successfully, at approximately 30 KiB compressed; the initial Windows download archive was approximately 578 KiB compressed.
- A dependency-free, independent JSON-RPC client initialized the optimized executable and exercised all 22 tools against an authenticated local HTTP mock in both read-only and write-enabled modes. Discovery, pagination continuation, input errors, disabled writes, content windows, and clean stdin-EOF shutdown passed.
- The initial optimized local Windows binary was **1,247,744 bytes**, with observed initialization **7.8–8.6 ms** and idle working set **6,389,760–6,402,048 bytes** after discovery and before HTTP calls. These measurements include the default local build, not the later Windows release's static C-runtime linkage.

Mock fixtures establish protocol and request behavior. They do not prove successful operation against an institution's production Canvas or that a particular user has student/teacher permissions.

## Publication status

The crate and native release workflows are configured. crates.io publication and platform downloads are pending their first successful Actions run; until then, build from source. The release workflow's five platform measurement reports are the source for release artifact sizes.

## Live checks remaining

With an authorized Canvas instance and token, run `mcp-canvas-lms --check`, then verify course visibility, real pagination, syllabus/page content, and student feedback. Teacher roster/submission reads depend on institutional scopes and permissions. Test mutations only in a suitable test course with explicit authorization. Real submissions, grades, assignment changes, and announcements have not been executed against a live Canvas account.

HTTPS certificate validation uses the native TLS backend and OS trust store. Mock HTTP tests do not establish institutional TLS, proxy compatibility, token issuance/renewal, or support for every self-hosted Canvas version.

A separate public-Canvas HTTPS probe using an intentionally invalid token reached HTTP 503. It did not verify authentication or institution-specific availability; no real credentials were used.
