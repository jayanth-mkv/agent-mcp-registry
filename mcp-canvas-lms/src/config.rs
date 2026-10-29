use std::{env, fs::File, io::Read, path::Path, time::Duration};
use url::Url;

pub const MAX_BODY: usize = 2 * 1024 * 1024;
pub const MAX_OUTPUT: usize = 256 * 1024;

#[derive(Clone)]
pub struct Config {
    pub base: Url,
    pub token: String,
    pub writes: bool,
    pub timeout: Duration,
}

impl Config {
    pub fn from_env() -> Result<Self, String> {
        let base = env::var("CANVAS_BASE_URL")
            .map_err(|_| "Set CANVAS_BASE_URL to your Canvas instance URL")?;
        let token = match (
            env::var("CANVAS_API_TOKEN").ok(),
            env::var("CANVAS_API_TOKEN_FILE").ok(),
        ) {
            (Some(_), Some(_)) => {
                return Err("Set CANVAS_API_TOKEN or CANVAS_API_TOKEN_FILE, not both".into());
            }
            (Some(value), None) => value,
            (None, Some(path)) => read_token(Path::new(&path))?,
            (None, None) => return Err("Set CANVAS_API_TOKEN or CANVAS_API_TOKEN_FILE".into()),
        };
        let timeout = env::var("CANVAS_TIMEOUT_SECONDS")
            .ok()
            .map(|value| {
                value
                    .parse::<u64>()
                    .ok()
                    .filter(|n| (1..=30).contains(n))
                    .ok_or("CANVAS_TIMEOUT_SECONDS must be 1..30")
            })
            .transpose()?
            .unwrap_or(15);
        Self::new(
            &base,
            token,
            flag("CANVAS_ENABLE_WRITES")?,
            flag("CANVAS_ALLOW_HTTP")?,
            timeout,
        )
    }

    pub fn new(
        base: &str,
        token: String,
        writes: bool,
        allow_http: bool,
        timeout: u64,
    ) -> Result<Self, String> {
        let mut base =
            Url::parse(base).map_err(|_| "CANVAS_BASE_URL must be an absolute HTTPS URL")?;
        if base.host_str().is_none()
            || !base.username().is_empty()
            || base.password().is_some()
            || base.query().is_some()
            || base.fragment().is_some()
        {
            return Err(
                "Canvas URL must have a host and no credentials, query, or fragment".into(),
            );
        }
        let loopback = match base.host() {
            Some(url::Host::Domain(host)) => host.eq_ignore_ascii_case("localhost"),
            Some(url::Host::Ipv4(ip)) => ip.is_loopback(),
            Some(url::Host::Ipv6(ip)) => ip.is_loopback(),
            None => false,
        };
        if base.scheme() != "https" && !(base.scheme() == "http" && allow_http && loopback) {
            return Err(
                "HTTPS is required; CANVAS_ALLOW_HTTP=true permits loopback test servers only"
                    .into(),
            );
        }
        let path = base
            .path()
            .trim_end_matches('/')
            .trim_end_matches("/api/v1")
            .to_owned();
        base.set_path(&format!("{path}/api/v1/"));
        let token = token.trim().to_owned();
        if token.is_empty() || token.len() > 16_384 || !token.bytes().all(|b| b.is_ascii_graphic())
        {
            return Err("Canvas token must contain 1..16384 visible ASCII characters".into());
        }
        Ok(Self {
            base,
            token,
            writes,
            timeout: Duration::from_secs(timeout.clamp(1, 30)),
        })
    }
}

fn flag(name: &str) -> Result<bool, String> {
    match env::var(name).ok().as_deref() {
        None | Some("false" | "0") => Ok(false),
        Some("true" | "1") => Ok(true),
        _ => Err(format!("{name} must be true or false")),
    }
}

fn read_token(path: &Path) -> Result<String, String> {
    let mut data = String::new();
    File::open(path)
        .map_err(|_| "Cannot open CANVAS_API_TOKEN_FILE")?
        .take(16_385)
        .read_to_string(&mut data)
        .map_err(|_| "Cannot read Canvas token file as UTF-8")?;
    if data.len() > 16_384 {
        return Err("Canvas token file is too large".into());
    }
    Ok(data)
}
