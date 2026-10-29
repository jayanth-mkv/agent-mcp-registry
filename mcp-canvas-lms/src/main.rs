mod client;
mod config;
mod server;
#[cfg(test)]
mod tests;
mod tools;

use config::Config;
use rmcp::{RoleServer, ServiceExt, transport::async_rw::AsyncRwTransport};

fn main() {
    if let Err(error) = run() {
        eprintln!("mcp-canvas-lms: {error}");
        std::process::exit(1);
    }
}

fn run() -> Result<(), String> {
    let args: Vec<String> = std::env::args().skip(1).collect();
    match args.as_slice() {
        [] => {}
        [arg] if arg == "--version" || arg == "-V" => {
            println!("mcp-canvas-lms {}", env!("CARGO_PKG_VERSION"));
            return Ok(());
        }
        [arg] if arg == "--help" || arg == "-h" => {
            println!(
                "mcp-canvas-lms {}\n\nNative stdio MCP for Canvas LMS.\n\nUsage: mcp-canvas-lms [--help | --version | --check]\n\nRequired: CANVAS_BASE_URL and CANVAS_API_TOKEN (or CANVAS_API_TOKEN_FILE).\nOptional: CANVAS_ENABLE_WRITES=true, CANVAS_TIMEOUT_SECONDS=15.\n--check verifies credentials using a read-only profile request.\nDiagnostics use stderr; stdout is reserved for MCP messages.",
                env!("CARGO_PKG_VERSION")
            );
            return Ok(());
        }
        [arg] if arg == "--check" => {
            let client = client::Canvas::new(Config::from_env()?)?;
            client.execute(tools::plan(
                "canvas_get_profile",
                serde_json::json!({}),
                false,
            )?)?;
            println!("Canvas credentials and profile access verified.");
            return Ok(());
        }
        _ => return Err("Unknown arguments; use --help".into()),
    }
    let canvas = client::Canvas::new(Config::from_env()?)?;
    let runtime = tokio::runtime::Builder::new_current_thread()
        .enable_all()
        .max_blocking_threads(4)
        .build()
        .map_err(|_| "Cannot initialize runtime")?;
    runtime.block_on(async {
        let transport =
            AsyncRwTransport::<RoleServer, _, _>::new(tokio::io::stdin(), tokio::io::stdout())
                .with_max_line_length(1024 * 1024);
        let service = server::CanvasServer::new(canvas)
            .serve(transport)
            .await
            .map_err(|_| "MCP initialization failed")?;
        service
            .waiting()
            .await
            .map_err(|_| "MCP connection ended unexpectedly")?;
        Ok(())
    })
}
