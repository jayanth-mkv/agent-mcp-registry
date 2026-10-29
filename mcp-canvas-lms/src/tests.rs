use crate::{
    client::{Canvas, next_link},
    config::Config,
    tools,
};
use serde_json::{Value, json};
use std::{
    io::{Read, Write},
    net::TcpListener,
    sync::{Arc, Mutex},
    thread,
    time::{Duration, Instant},
};

struct Fixture {
    client: Canvas,
    requests: Arc<Mutex<Vec<String>>>,
    worker: Option<thread::JoinHandle<()>>,
}

impl Fixture {
    fn new(replies: Vec<String>, writes: bool) -> Self {
        let listener = TcpListener::bind("127.0.0.1:0").unwrap();
        listener.set_nonblocking(true).unwrap();
        let base = format!("http://{}", listener.local_addr().unwrap());
        let requests = Arc::new(Mutex::new(Vec::new()));
        let captured = requests.clone();
        let worker = thread::spawn(move || {
            for reply in replies {
                let deadline = Instant::now() + Duration::from_secs(5);
                let mut stream = loop {
                    match listener.accept() {
                        Ok((stream, _)) => break stream,
                        Err(error) if error.kind() == std::io::ErrorKind::WouldBlock => {
                            assert!(Instant::now() < deadline, "expected an HTTP request");
                            thread::sleep(Duration::from_millis(5));
                        }
                        Err(error) => panic!("mock server: {error}"),
                    }
                };
                stream.set_nonblocking(false).unwrap();
                stream
                    .set_read_timeout(Some(Duration::from_secs(3)))
                    .unwrap();
                let mut bytes = Vec::new();
                let mut buffer = [0; 4096];
                loop {
                    let count = stream.read(&mut buffer).unwrap();
                    assert!(count > 0, "request closed before headers/body");
                    bytes.extend_from_slice(&buffer[..count]);
                    if let Some(end) = bytes.windows(4).position(|window| window == b"\r\n\r\n") {
                        let headers = String::from_utf8_lossy(&bytes[..end]);
                        let length = headers
                            .lines()
                            .filter_map(|line| line.split_once(':'))
                            .find(|(key, _)| key.eq_ignore_ascii_case("content-length"))
                            .map(|(_, value)| value.trim().parse::<usize>().unwrap())
                            .unwrap_or(0);
                        if bytes.len() >= end + 4 + length {
                            break;
                        }
                    }
                }
                captured
                    .lock()
                    .unwrap()
                    .push(String::from_utf8(bytes).unwrap());
                let _ = stream.write_all(reply.as_bytes());
            }
        });
        let config = Config::new(&base, "test-token".into(), writes, true, 2).unwrap();
        Self {
            client: Canvas::new(config).unwrap(),
            requests,
            worker: Some(worker),
        }
    }
}

impl Drop for Fixture {
    fn drop(&mut self) {
        if let Some(worker) = self.worker.take() {
            let result = worker.join();
            if !thread::panicking() {
                result.unwrap();
            }
        }
    }
}

fn response(status: u16, headers: &str, body: &str) -> String {
    format!(
        "HTTP/1.1 {status} Result\r\nContent-Type: application/json\r\nContent-Length: {}\r\nConnection: close\r\n{headers}\r\n{body}",
        body.len()
    )
}

#[test]
fn default_mode_hides_and_denies_every_write() {
    assert_eq!(tools::catalog(false).count(), 17);
    assert_eq!(tools::catalog(true).count(), 22);
    for spec in tools::catalog(true).filter(|spec| spec.write) {
        assert!(tools::plan(&spec.tool.name, json!({}), false).is_err());
        assert_eq!(
            spec.tool.annotations.as_ref().unwrap().read_only_hint,
            Some(false)
        );
    }
}

#[test]
fn schemas_reject_unknown_and_invalid_inputs() {
    for args in [
        json!({"course_id":0}),
        json!({"course_id":-1}),
        json!({"course_id":1.5}),
        json!({"course_id":"1"}),
        json!({"course_id":1,"per_page":101}),
        json!({"course_id":1,"extra":true}),
        json!({"course_id":1,"full":"true"}),
    ] {
        assert!(tools::plan("canvas_list_assignments", args, false).is_err());
    }
    assert!(tools::plan("canvas_get_assignment", json!({"course_id":1}), false).is_err());
}

#[test]
fn config_requires_https_without_url_credentials_or_query() {
    for url in [
        "http://canvas.example.com",
        "https://user:password@canvas.example.com",
        "https://canvas.example.com?access_token=secret",
        "https://canvas.example.com#fragment",
        "file:///tmp/canvas",
    ] {
        assert!(Config::new(url, "test".into(), false, true, 15).is_err());
    }
    for url in [
        "http://localhost:1234",
        "http://127.0.0.1:1234",
        "http://[::1]:1234",
    ] {
        assert!(Config::new(url, "test".into(), false, true, 15).is_ok());
        assert!(Config::new(url, "test".into(), false, false, 15).is_err());
    }
    assert!(
        Config::new(
            "https://canvas.example.com",
            "bad\r\nheader".into(),
            false,
            false,
            15
        )
        .is_err()
    );
    assert!(Config::new("https://canvas.example.com", "".into(), false, false, 15).is_err());
}

#[test]
fn configured_api_prefix_is_not_duplicated() {
    for base in [
        "https://canvas.example.com",
        "https://canvas.example.com/",
        "https://canvas.example.com/api/v1/",
    ] {
        let client =
            Canvas::new(Config::new(base, "test".into(), false, false, 15).unwrap()).unwrap();
        let plan = tools::plan("canvas_get_profile", json!({}), false).unwrap();
        assert_eq!(
            client.endpoint(&plan).unwrap().as_str(),
            "https://canvas.example.com/api/v1/users/self/profile"
        );
    }
}

#[test]
fn authorization_is_a_header_and_results_are_compact() {
    let fixture = Fixture::new(
        vec![response(
            200,
            "",
            r#"[{"id":7,"name":"Course","unneeded":"large"}]"#,
        )],
        false,
    );
    let result = fixture
        .client
        .execute(tools::plan("canvas_list_courses", json!({}), false).unwrap())
        .unwrap();
    assert_eq!(
        result,
        json!({"data":[{"id":7,"name":"Course"}],"next_cursor":null})
    );
    let requests = fixture.requests.lock().unwrap();
    assert!(requests[0].starts_with("GET /api/v1/courses?per_page=20 HTTP/1.1"));
    assert!(
        requests[0]
            .to_ascii_lowercase()
            .contains("authorization: bearer test-token")
    );
    assert!(!requests[0].lines().next().unwrap().contains("test-token"));
}

#[test]
fn opaque_link_header_supports_commas_and_multiple_relations() {
    let header = r#"<https://canvas.example.com/api/v1/courses?cursor=a,b>; rel="next last", <https://canvas.example.com/api/v1/courses>; rel="prev""#;
    assert_eq!(
        next_link(header).unwrap(),
        Some("https://canvas.example.com/api/v1/courses?cursor=a,b".into())
    );
    assert!(
        next_link(r#"<https://a.example/a>; rel=next, <https://a.example/b>; rel=next"#).is_err()
    );
}

#[test]
fn malicious_pagination_cursors_are_rejected_before_network() {
    let client = Canvas::new(
        Config::new(
            "https://canvas.example.com",
            "test".into(),
            false,
            false,
            15,
        )
        .unwrap(),
    )
    .unwrap();
    for cursor in [
        "https://evil.example/api/v1/courses?page=2",
        "http://canvas.example.com/api/v1/courses?page=2",
        "https://canvas.example.com/api/v1/users/self/profile",
        "https://test@canvas.example.com/api/v1/courses?page=2",
        "https://canvas.example.com/api/v1/courses?access_token=secret",
        "https://canvas.example.com/api/v1/courses?per_page=1000",
        "https://canvas.example.com/api/v1/courses#fragment",
    ] {
        let plan = tools::plan("canvas_list_courses", json!({"cursor":cursor}), false).unwrap();
        assert!(client.endpoint(&plan).is_err(), "{cursor}");
    }
}

#[test]
fn course_context_cannot_be_changed_by_a_cursor() {
    let client = Canvas::new(
        Config::new(
            "https://canvas.example.com",
            "test".into(),
            false,
            false,
            15,
        )
        .unwrap(),
    )
    .unwrap();
    let plan=tools::plan("canvas_list_announcements",json!({"course_id":1,"cursor":"https://canvas.example.com/api/v1/announcements?context_codes[]=course_2"}),false).unwrap();
    assert!(client.endpoint(&plan).is_err());
}

#[test]
fn valid_pagination_is_returned_without_fetching_every_page() {
    let fixture = Fixture::new(vec![response(200, "", r#"[{"id":1}]"#)], false);
    let base = fixture.client.config.base.to_string();
    let cursor = format!("{base}courses?opaque=next%2Btoken&per_page=7");
    let plan = tools::plan("canvas_list_courses", json!({"cursor":cursor}), false).unwrap();
    fixture.client.execute(plan).unwrap();
    let request = fixture.requests.lock().unwrap()[0].clone();
    assert!(request.starts_with("GET /api/v1/courses?opaque=next%2Btoken&per_page=7 "));
}

#[test]
fn redirects_are_not_followed() {
    let fixture = Fixture::new(
        vec![response(
            302,
            "Location: http://127.0.0.1:1/stolen\r\n",
            "{}",
        )],
        false,
    );
    let error = fixture
        .client
        .execute(tools::plan("canvas_get_profile", json!({}), false).unwrap())
        .unwrap_err();
    assert!(error.contains("redirect"), "{error}");
    assert_eq!(fixture.requests.lock().unwrap().len(), 1);
}

#[test]
fn read_throttling_retries_once_but_writes_never_retry() {
    let fixture = Fixture::new(
        vec![
            response(429, "Retry-After: 0\r\n", "{}"),
            response(200, "", r#"{"id":1}"#),
        ],
        false,
    );
    fixture
        .client
        .execute(tools::plan("canvas_get_profile", json!({}), false).unwrap())
        .unwrap();
    assert_eq!(fixture.requests.lock().unwrap().len(), 2);
    let fixture = Fixture::new(vec![response(503, "Retry-After: 0\r\n", "{}")], true);
    let plan = tools::plan(
        "canvas_create_assignment",
        json!({"course_id":1,"name":"Draft"}),
        true,
    )
    .unwrap();
    assert!(fixture.client.execute(plan).unwrap_err().contains("503"));
    assert_eq!(fixture.requests.lock().unwrap().len(), 1);
}

#[test]
fn a_long_retry_after_is_returned_without_early_retry() {
    let fixture = Fixture::new(vec![response(429, "Retry-After: 60\r\n", "{}")], false);
    assert!(
        fixture
            .client
            .execute(tools::plan("canvas_get_profile", json!({}), false).unwrap())
            .unwrap_err()
            .contains("429")
    );
    assert_eq!(fixture.requests.lock().unwrap().len(), 1);
}

#[test]
fn canvas_error_bodies_never_expose_credentials() {
    let fixture = Fixture::new(vec![response(401, "", r#"{"error":"test-token"}"#)], false);
    let error = fixture
        .client
        .execute(tools::plan("canvas_get_profile", json!({}), false).unwrap())
        .unwrap_err();
    assert!(error.contains("401"));
    assert!(!error.contains("test-token"));
}

#[test]
fn large_responses_are_bounded_and_full_output_is_optional() {
    let body = json!([{"id":1,"extra":"x".repeat(300000)}]).to_string();
    let fixture = Fixture::new(
        vec![response(200, "", &body), response(200, "", &body)],
        false,
    );
    let compact = fixture
        .client
        .execute(tools::plan("canvas_list_courses", json!({}), false).unwrap())
        .unwrap();
    assert_eq!(compact["data"], json!([{"id":1}]));
    assert!(
        fixture
            .client
            .execute(tools::plan("canvas_list_courses", json!({"full":true}), false).unwrap())
            .unwrap_err()
            .contains("256 KiB")
    );
    let fixture = Fixture::new(
        vec!["HTTP/1.1 200 OK\r\nContent-Length: 2097153\r\nConnection: close\r\n\r\n".into()],
        false,
    );
    assert!(
        fixture
            .client
            .execute(tools::plan("canvas_get_profile", json!({}), false).unwrap())
            .unwrap_err()
            .contains("2 MiB")
    );
}

#[test]
fn unicode_content_windows_can_be_continued_without_corruption() {
    let body = json!({"page_id":1,"body":"🙂漢abc"}).to_string();
    let fixture = Fixture::new(
        vec![response(200, "", &body), response(200, "", &body)],
        false,
    );
    let first = fixture
        .client
        .execute(
            tools::plan(
                "canvas_get_page",
                json!({"course_id":1,"page":"intro","text_limit":2}),
                false,
            )
            .unwrap(),
        )
        .unwrap();
    assert_eq!(first["data"]["body"], "🙂漢");
    assert_eq!(first["data"]["_mcp_text_windows"]["body"]["next_offset"], 2);
    let second = fixture
        .client
        .execute(
            tools::plan(
                "canvas_get_page",
                json!({"course_id":1,"page":"intro","text_limit":3,"text_offset":2}),
                false,
            )
            .unwrap(),
        )
        .unwrap();
    assert_eq!(second["data"]["body"], "abc");
    assert!(second["data"]["_mcp_text_windows"]["body"]["next_offset"].is_null());
}

#[test]
fn writes_use_the_documented_canvas_envelopes_and_draft_defaults() {
    let fixture = Fixture::new(vec![response(200, "", r#"{"id":99}"#)], true);
    let plan = tools::plan(
        "canvas_create_assignment",
        json!({"course_id":1,"name":"Draft"}),
        true,
    )
    .unwrap();
    fixture.client.execute(plan).unwrap();
    let requests = fixture.requests.lock().unwrap();
    assert!(requests[0].starts_with("POST /api/v1/courses/1/assignments "));
    let body: Value = serde_json::from_str(requests[0].split_once("\r\n\r\n").unwrap().1).unwrap();
    assert_eq!(
        body,
        json!({"assignment":{"name":"Draft","published":false,"submission_types":["online_text_entry"]}})
    );
    let grade=tools::plan("canvas_grade_submission",json!({"course_id":1,"assignment_id":2,"user_id":3,"posted_grade":"90%","comment":"Good work"}),true).unwrap();
    assert_eq!(
        grade.body.unwrap(),
        json!({"submission":{"posted_grade":"90%"},"comment":{"text_comment":"Good work"}})
    );
}

#[test]
fn submissions_and_updates_reject_incomplete_or_ambiguous_intent() {
    for args in [
        json!({"course_id":1,"assignment_id":2,"submission_type":"online_text_entry"}),
        json!({"course_id":1,"assignment_id":2,"submission_type":"online_url","url":"file:///etc/passwd"}),
        json!({"course_id":1,"assignment_id":2,"submission_type":"online_text_entry","body":"text","url":"https://example.com"}),
    ] {
        assert!(tools::plan("canvas_submit_assignment", args, true).is_err());
    }
    assert!(
        tools::plan(
            "canvas_update_assignment",
            json!({"course_id":1,"assignment_id":2}),
            true
        )
        .is_err()
    );
    for page in ["..", "../secret", "%2e%2e", "https://evil.example/a"] {
        assert!(tools::plan("canvas_get_page", json!({"course_id":1,"page":page}), false).is_err());
    }
}
