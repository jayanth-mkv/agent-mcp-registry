use crate::{
    config::{Config, MAX_BODY, MAX_OUTPUT},
    tools::Plan,
};
use serde_json::{Value, json};
use std::{
    io::{Read, Write},
    sync::Arc,
    thread,
    time::Duration,
};
use ureq::{
    Agent,
    tls::{RootCerts, TlsConfig, TlsProvider},
};
use url::Url;

#[derive(Clone)]
pub struct Canvas {
    pub config: Arc<Config>,
    agent: Agent,
}

impl Canvas {
    pub fn new(config: Config) -> Result<Self, String> {
        let agent = Agent::config_builder()
            .tls_config(
                TlsConfig::builder()
                    .provider(TlsProvider::NativeTls)
                    .root_certs(RootCerts::PlatformVerifier)
                    .build(),
            )
            .timeout_global(Some(config.timeout))
            .timeout_connect(Some(Duration::from_secs(5)))
            .max_redirects(0)
            .http_status_as_error(false)
            .max_idle_connections(1)
            .max_idle_connections_per_host(1)
            .user_agent(concat!("mcp-canvas-lms/", env!("CARGO_PKG_VERSION")))
            .build()
            .new_agent();
        Ok(Self {
            config: Arc::new(config),
            agent,
        })
    }

    pub fn endpoint(&self, plan: &Plan) -> Result<Url, String> {
        let mut url = self.config.base.clone();
        {
            let mut segments = url
                .path_segments_mut()
                .map_err(|_| "Invalid Canvas base URL")?;
            segments.pop_if_empty();
            for part in &plan.path {
                segments.push(part);
            }
        }
        if let Some(cursor) = &plan.cursor {
            return self.validate_cursor(cursor, &url, plan);
        }
        if !plan.query.is_empty() {
            url.query_pairs_mut().extend_pairs(
                plan.query
                    .iter()
                    .map(|(key, value)| (key.as_str(), value.as_str())),
            );
        }
        Ok(url)
    }

    fn validate_cursor(&self, cursor: &str, expected: &Url, plan: &Plan) -> Result<Url, String> {
        let url = Url::parse(cursor).map_err(|_| "Invalid pagination cursor")?;
        if url.origin() != expected.origin()
            || url.path().strip_suffix(".json").unwrap_or(url.path())
                != expected
                    .path()
                    .strip_suffix(".json")
                    .unwrap_or(expected.path())
            || !url.username().is_empty()
            || url.password().is_some()
            || url.fragment().is_some()
        {
            return Err(
                "Pagination cursor must stay on the same Canvas origin and API endpoint".into(),
            );
        }
        let pairs: Vec<_> = url.query_pairs().collect();
        if pairs.iter().any(|(key, value)| {
            key.eq_ignore_ascii_case("access_token")
                || (key == "per_page"
                    && value
                        .parse::<u64>()
                        .ok()
                        .filter(|n| (1..=100).contains(n))
                        .is_none())
        }) {
            return Err(
                "Pagination cursor contains forbidden credentials or an invalid page size".into(),
            );
        }
        if let Some(context) = &plan.context {
            let contexts: Vec<_> = pairs
                .iter()
                .filter(|(key, _)| key == "context_codes[]")
                .map(|(_, value)| value.as_ref())
                .collect();
            if contexts != [context.as_str()] {
                return Err("Pagination cursor changed the requested course context".into());
            }
        }
        Ok(url)
    }

    pub fn execute(&self, plan: Plan) -> Result<String, String> {
        if plan.method != "GET" && !self.config.writes {
            return Err("Write mode is disabled".into());
        }
        let url = self.endpoint(&plan)?;
        let authorization = format!("Bearer {}", self.config.token);
        for attempt in 0..2 {
            let response = match plan.method {
                "GET" => self
                    .agent
                    .get(url.as_str())
                    .header("Authorization", &authorization)
                    .header("Accept", "application/json")
                    .call(),
                "POST" => self
                    .agent
                    .post(url.as_str())
                    .header("Authorization", &authorization)
                    .header("Accept", "application/json")
                    .send_json(plan.body.as_ref().ok_or("Missing write body")?),
                "PUT" => self
                    .agent
                    .put(url.as_str())
                    .header("Authorization", &authorization)
                    .header("Accept", "application/json")
                    .send_json(plan.body.as_ref().ok_or("Missing write body")?),
                _ => return Err("Unsupported request method".into()),
            };
            let mut response = response.map_err(|_| "Canvas connection failed; check the URL, TLS certificates, network and timeout")?;
            let status = response.status().as_u16();
            if plan.method == "GET" && attempt == 0 && matches!(status, 429 | 502 | 503 | 504) {
                let delay = response
                    .headers()
                    .get("retry-after")
                    .and_then(|value| value.to_str().ok())
                    .map(|value| value.parse::<u64>().ok());
                let seconds = match delay {
                    None => Some(1),
                    Some(Some(seconds)) if seconds <= 2 => Some(seconds),
                    _ => None,
                };
                if let Some(seconds) = seconds {
                    drop(response);
                    thread::sleep(Duration::from_secs(seconds));
                    continue;
                }
            }
            if !(200..300).contains(&status) {
                return Err(match status {
                    301..=399 => "Canvas returned a redirect; configure the final Canvas instance URL. Redirects are not followed".into(),
                    401 => "Canvas API 401: token is missing, invalid, revoked or expired".into(),
                    403 => "Canvas API 403: the authenticated user or token lacks permission".into(),
                    404 => "Canvas API 404: resource is missing or unavailable to this user".into(),
                    429 => "Canvas API 429: rate limited; wait before retrying".into(),
                    500..=599 => format!("Canvas API HTTP {status}: service temporarily unavailable; try again later"),
                    _ => format!("Canvas API returned HTTP {status}; check the requested fields and account permissions"),
                });
            }
            let mut next = None;
            for value in response.headers().get_all("link") {
                let header = value
                    .to_str()
                    .map_err(|_| "Invalid Canvas pagination header")?;
                if let Some(link) = next_link(header)? {
                    let candidate = self.validate_cursor(&link, &url, &plan)?;
                    if next
                        .as_ref()
                        .is_some_and(|current| current != candidate.as_str())
                    {
                        return Err("Ambiguous Canvas pagination links".into());
                    }
                    next = Some(candidate.to_string());
                }
            }
            if response
                .headers()
                .get("content-length")
                .and_then(|value| value.to_str().ok())
                .and_then(|value| value.parse::<usize>().ok())
                .is_some_and(|length| length > MAX_BODY)
            {
                return Err("Canvas response exceeds the 2 MiB body limit; reduce per_page".into());
            }
            let mut bytes = Vec::new();
            response
                .body_mut()
                .as_reader()
                .take((MAX_BODY + 1) as u64)
                .read_to_end(&mut bytes)
                .map_err(
                    |_| "Cannot read the Canvas response within the configured timeout and limits",
                )?;
            if bytes.len() > MAX_BODY {
                return Err("Canvas response exceeds the 2 MiB body limit; reduce per_page".into());
            }
            let data:Value = serde_json::from_slice(&bytes).map_err(|_| "Canvas returned invalid JSON; check that the URL points to a Canvas API instance")?;
            drop(bytes);
            if plan.list && !data.is_array() {
                return Err("Canvas list endpoint returned an unexpected response shape".into());
            }
            let mut data = if plan.full || plan.fields.is_empty() {
                data
            } else {
                compact(data, plan.fields)
            };
            window_text(&mut data, plan.text_offset, plan.text_limit);
            let result = json!({"data":data,"next_cursor":next});
            let mut output = OutputBuffer(Vec::with_capacity(4096));
            serde_json::to_writer(&mut output, &result).map_err(
                |_| "Result exceeds the 256 KiB output limit; reduce per_page or omit full",
            )?;
            return String::from_utf8(output.0).map_err(|_| "Cannot encode Canvas response".into());
        }
        Err("Canvas request failed".into())
    }
}

struct OutputBuffer(Vec<u8>);

impl Write for OutputBuffer {
    fn write(&mut self, bytes: &[u8]) -> std::io::Result<usize> {
        let needed = self.0.len().saturating_add(bytes.len());
        if needed > MAX_OUTPUT {
            return Err(std::io::Error::new(
                std::io::ErrorKind::InvalidData,
                "output limit",
            ));
        }
        if needed > self.0.capacity() {
            let capacity = needed
                .max(self.0.capacity().saturating_mul(2))
                .min(MAX_OUTPUT);
            self.0.reserve_exact(capacity - self.0.len());
        }
        self.0.extend_from_slice(bytes);
        Ok(bytes.len())
    }

    fn flush(&mut self) -> std::io::Result<()> {
        Ok(())
    }
}

fn compact(value: Value, fields: &[&str]) -> Value {
    match value {
        Value::Array(items) => Value::Array(
            items
                .into_iter()
                .map(|item| compact(item, fields))
                .collect(),
        ),
        Value::Object(mut object) => {
            object.retain(|key, _| fields.contains(&key.as_str()));
            Value::Object(object)
        }
        other => other,
    }
}

fn window_text(value: &mut Value, offset: usize, limit: usize) {
    match value {
        Value::Array(items) => {
            for item in items {
                window_text(item, offset, limit);
            }
        }
        Value::Object(object) => {
            let mut windows = serde_json::Map::new();
            for (key, value) in object.iter_mut() {
                if matches!(
                    key.as_str(),
                    "body" | "description" | "message" | "syllabus_body"
                ) {
                    if let Some(text) = value.as_str() {
                        let total = text.chars().count();
                        if total > limit || offset > 0 {
                            let start = offset.min(total);
                            let end = start.saturating_add(limit).min(total);
                            let slice: String = text.chars().skip(start).take(limit).collect();
                            windows.insert(key.clone(),json!({"offset":start,"total_chars":total,"next_offset":if end<total {Some(end)} else {None}}));
                            *value = Value::String(slice);
                        }
                    }
                } else {
                    window_text(value, offset, limit);
                }
            }
            if !windows.is_empty() {
                object.insert("_mcp_text_windows".into(), Value::Object(windows));
            }
        }
        _ => {}
    }
}

pub fn next_link(header: &str) -> Result<Option<String>, String> {
    let mut parts = Vec::new();
    let (mut start, mut angle, mut quoted) = (0, false, false);
    for (index, character) in header.char_indices() {
        match character {
            '<' if !quoted => angle = true,
            '>' if !quoted => angle = false,
            '"' if !angle => quoted = !quoted,
            ',' if !angle && !quoted => {
                parts.push(&header[start..index]);
                start = index + 1;
            }
            _ => {}
        }
    }
    parts.push(&header[start..]);
    let mut next = None;
    for part in parts {
        let part = part.trim();
        let Some((target, parameters)) =
            part.strip_prefix('<').and_then(|part| part.split_once('>'))
        else {
            continue;
        };
        let is_next = parameters
            .split(';')
            .filter_map(|part| part.trim().split_once('='))
            .any(|(key, value)| {
                key.eq_ignore_ascii_case("rel")
                    && value
                        .trim()
                        .trim_matches('"')
                        .split_ascii_whitespace()
                        .any(|rel| rel.eq_ignore_ascii_case("next"))
            });
        if is_next {
            if target.len() > 8192 {
                return Err("Canvas pagination cursor is too long".into());
            }
            if next.as_ref().is_some_and(|old| old != target) {
                return Err("Ambiguous Canvas pagination links".into());
            }
            next = Some(target.to_owned());
        }
    }
    Ok(next)
}
