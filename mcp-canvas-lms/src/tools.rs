use rmcp::model::{Tool, ToolAnnotations};
use serde_json::{Map, Value, json};
use std::sync::LazyLock;

static SPECS: LazyLock<Vec<Spec>> = LazyLock::new(build_catalog);

pub struct Spec {
    pub tool: Tool,
    pub write: bool,
}

#[derive(Debug)]
pub struct Plan {
    pub method: &'static str,
    pub path: Vec<String>,
    pub query: Vec<(String, String)>,
    pub body: Option<Value>,
    pub cursor: Option<String>,
    pub fields: &'static [&'static str],
    pub list: bool,
    pub full: bool,
    pub context: Option<String>,
    pub text_limit: usize,
    pub text_offset: usize,
}

pub fn catalog(writes: bool) -> impl Iterator<Item = &'static Spec> {
    SPECS.iter().filter(move |spec| writes || !spec.write)
}

fn build_catalog() -> Vec<Spec> {
    let id = || json!({"type":"integer","minimum":1});
    let text = |max| json!({"type":"string","minLength":1,"maxLength":max});
    let nullable_date = || json!({"type":["string","null"],"maxLength":64,"description":"RFC3339 timestamp; null removes the due date."});
    let assignment_types = || json!({"type":"array","minItems":1,"maxItems":5,"items":{"type":"string","enum":["online_text_entry","online_upload","online_url","on_paper","none"]}});
    let mut specs = Vec::new();
    let mut add = |name: &'static str,
                   description: &'static str,
                   mut props: Value,
                   required: &[&str],
                   list: bool,
                   write: bool| {
        let object = props.as_object_mut().expect("static tool properties");
        if list {
            object.insert(
                "per_page".into(),
                json!({"type":"integer","minimum":1,"maximum":100,"default":20}),
            );
            object.insert("cursor".into(), json!({"type":"string","maxLength":8192,"description":"Use next_cursor from the previous page unchanged; page/filter parameters are carried in this cursor."}));
        }
        if !write {
            object.insert("full".into(), json!({"type":"boolean","default":false,"description":"Include all API fields instead of compact fields; response limits still apply."}));
        }
        if !list && !write && name != "canvas_get_profile" {
            object.insert("text_limit".into(),json!({"type":"integer","minimum":1,"maximum":64000,"default":12000,"description":"Maximum characters per content field. Truncation returns _mcp_text_windows metadata."}));
            object.insert("text_offset".into(),json!({"type":"integer","minimum":0,"maximum":2097152,"default":0,"description":"Continue a content field using its next_offset from _mcp_text_windows."}));
        }
        let schema = json!({"type":"object","properties":props,"required":required,"additionalProperties":false});
        let mut tool = Tool::new(
            name,
            description,
            schema.as_object().expect("static schema").clone(),
        );
        tool.annotations = Some(
            ToolAnnotations::new()
                .read_only(!write)
                .destructive(
                    write
                        && !matches!(
                            name,
                            "canvas_create_assignment" | "canvas_post_announcement"
                        ),
                )
                .idempotent(!write)
                .open_world(true),
        );
        specs.push(Spec { tool, write });
    };
    add(
        "canvas_get_profile",
        "Read the authenticated user's Canvas profile. Start here to verify access.",
        json!({}),
        &[],
        false,
        false,
    );
    add(
        "canvas_list_courses",
        "List my courses. Follow next_cursor to retrieve subsequent pages.",
        json!({"enrollment_state":{"type":"string","enum":["active","invited_or_pending","completed"]}}),
        &[],
        true,
        false,
    );
    add(
        "canvas_get_course",
        "Read a course, including its syllabus and available permissions.",
        json!({"course_id":id()}),
        &["course_id"],
        false,
        false,
    );
    add(
        "canvas_list_assignments",
        "List a course's assignments, deadlines and submission types. Compact results omit long descriptions.",
        json!({"course_id":id(),"search_term":text(255),"bucket":{"type":"string","enum":["past","overdue","undated","ungraded","unsubmitted","upcoming","future"]}}),
        &["course_id"],
        true,
        false,
    );
    add(
        "canvas_get_assignment",
        "Read assignment instructions and my submission when available.",
        json!({"course_id":id(),"assignment_id":id()}),
        &["course_id", "assignment_id"],
        false,
        false,
    );
    add(
        "canvas_list_modules",
        "List course modules and completion state; retrieve their items separately.",
        json!({"course_id":id()}),
        &["course_id"],
        true,
        false,
    );
    add(
        "canvas_list_module_items",
        "List the learning materials and completion requirements inside one module.",
        json!({"course_id":id(),"module_id":id()}),
        &["course_id", "module_id"],
        true,
        false,
    );
    add(
        "canvas_list_pages",
        "List course wiki pages; get an individual page to read its content.",
        json!({"course_id":id(),"search_term":text(255)}),
        &["course_id"],
        true,
        false,
    );
    add(
        "canvas_get_page",
        "Read a course page's HTML. Supply its url slug or page_id:<id>, not a full URL.",
        json!({"course_id":id(),"page":text(255)}),
        &["course_id", "page"],
        false,
        false,
    );
    add(
        "canvas_list_announcements",
        "List a course's announcements. Canvas defaults to the last 14 days. Read the message with canvas_get_discussion.",
        json!({"course_id":id(),"start_date":text(64),"end_date":text(64)}),
        &["course_id"],
        true,
        false,
    );
    add(
        "canvas_list_discussions",
        "List course discussion topics; use canvas_get_discussion for the opening message.",
        json!({"course_id":id(),"search_term":text(255)}),
        &["course_id"],
        true,
        false,
    );
    add(
        "canvas_get_discussion",
        "Read the opening message of a discussion or announcement. This does not fetch all replies.",
        json!({"course_id":id(),"topic_id":id()}),
        &["course_id", "topic_id"],
        false,
        false,
    );
    add(
        "canvas_list_files",
        "List course file metadata and authorized download URLs. Does not download or parse files.",
        json!({"course_id":id(),"search_term":text(255)}),
        &["course_id"],
        true,
        false,
    );
    add(
        "canvas_list_enrollments",
        "List my enrollments/grades, or a course roster when course_id is supplied. Canvas permissions control access.",
        json!({"course_id":id()}),
        &[],
        true,
        false,
    );
    add(
        "canvas_list_submissions",
        "List submissions for an assignment, typically for teachers. Canvas permissions apply.",
        json!({"course_id":id(),"assignment_id":id()}),
        &["course_id", "assignment_id"],
        true,
        false,
    );
    add(
        "canvas_get_submission",
        "Read my assignment submission and feedback, or a specified user's submission when permitted.",
        json!({"course_id":id(),"assignment_id":id(),"user_id":id()}),
        &["course_id", "assignment_id"],
        false,
        false,
    );
    add(
        "canvas_list_calendar_events",
        "List personal or course calendar events. Supply start_date/end_date for an explicit date window.",
        json!({"course_id":id(),"start_date":text(64),"end_date":text(64),"type":{"type":"string","enum":["event","assignment"]}}),
        &[],
        true,
        false,
    );
    let assignment = json!({"course_id":id(),"name":text(255),"description":{"type":"string","maxLength":65536},"due_at":nullable_date(),"points_possible":{"type":"number","minimum":0},"submission_types":assignment_types(),"published":{"type":"boolean","default":false}});
    add(
        "canvas_create_assignment",
        "Create a course assignment. Defaults to an unpublished draft. Requires write mode and Canvas course permissions.",
        assignment.clone(),
        &["course_id", "name"],
        false,
        true,
    );
    let mut update = assignment;
    update["assignment_id"] = id();
    add(
        "canvas_update_assignment",
        "Update only supplied assignment fields. Changing published or due_at affects students. Requires write mode.",
        update,
        &["course_id", "assignment_id"],
        false,
        true,
    );
    add(
        "canvas_submit_assignment",
        "Submit my text or URL to an assignment. Creates a submission attempt; requires write mode. No file uploads or quiz answers.",
        json!({"course_id":id(),"assignment_id":id(),"submission_type":{"type":"string","enum":["online_text_entry","online_url"]},"body":text(65536),"url":text(8192)}),
        &["course_id", "assignment_id", "submission_type"],
        false,
        true,
    );
    add(
        "canvas_grade_submission",
        "Set a student's assignment grade and optionally add feedback. Requires write mode and grading permission.",
        json!({"course_id":id(),"assignment_id":id(),"user_id":id(),"posted_grade":text(64),"comment":text(65536)}),
        &["course_id", "assignment_id", "user_id", "posted_grade"],
        false,
        true,
    );
    add(
        "canvas_post_announcement",
        "Publish an announcement to a course, notifying users according to Canvas settings. Requires write mode and announcement permission.",
        json!({"course_id":id(),"title":text(255),"message":text(65536)}),
        &["course_id", "title", "message"],
        false,
        true,
    );
    specs
}

pub fn plan(name: &str, args: Value, writes: bool) -> Result<Plan, String> {
    let spec = catalog(writes)
        .find(|spec| spec.tool.name == name)
        .ok_or("Unknown or disabled tool; write tools require CANVAS_ENABLE_WRITES=true")?;
    let args = args.as_object().ok_or("Tool arguments must be an object")?;
    validate(args, spec.tool.input_schema.as_ref())?;
    let number = |key: &str| {
        args.get(key)
            .and_then(Value::as_u64)
            .map(|value| value.to_string())
            .unwrap_or_default()
    };
    let course = number("course_id");
    let assignment = number("assignment_id");
    let mut result = Plan {
        method: "GET",
        path: Vec::new(),
        query: Vec::new(),
        body: None,
        cursor: args
            .get("cursor")
            .and_then(Value::as_str)
            .map(str::to_owned),
        fields: &[],
        list: name.starts_with("canvas_list_"),
        full: args.get("full").and_then(Value::as_bool).unwrap_or(false),
        context: None,
        text_limit: args
            .get("text_limit")
            .and_then(Value::as_u64)
            .unwrap_or(12000) as usize,
        text_offset: args.get("text_offset").and_then(Value::as_u64).unwrap_or(0) as usize,
    };
    let path = match name {
        "canvas_get_profile" => "users/self/profile".into(),
        "canvas_list_courses" => "courses".into(),
        "canvas_get_course" => {
            result.query.extend([
                ("include[]".into(), "syllabus_body".into()),
                ("include[]".into(), "permissions".into()),
            ]);
            format!("courses/{course}")
        }
        "canvas_list_assignments" => format!("courses/{course}/assignments"),
        "canvas_get_assignment" => {
            result.query.push(("include[]".into(), "submission".into()));
            format!("courses/{course}/assignments/{assignment}")
        }
        "canvas_list_modules" => format!("courses/{course}/modules"),
        "canvas_list_module_items" => {
            format!("courses/{course}/modules/{}/items", number("module_id"))
        }
        "canvas_list_pages" => format!("courses/{course}/pages"),
        "canvas_get_page" => format!("courses/{course}/pages"),
        "canvas_list_announcements" => {
            result.context = Some(format!("course_{course}"));
            result
                .query
                .push(("context_codes[]".into(), format!("course_{course}")));
            "announcements".into()
        }
        "canvas_list_discussions" => format!("courses/{course}/discussion_topics"),
        "canvas_get_discussion" => {
            format!("courses/{course}/discussion_topics/{}", number("topic_id"))
        }
        "canvas_list_files" => format!("courses/{course}/files"),
        "canvas_list_enrollments" => {
            if course.is_empty() {
                "users/self/enrollments".into()
            } else {
                format!("courses/{course}/enrollments")
            }
        }
        "canvas_list_submissions" => {
            format!("courses/{course}/assignments/{assignment}/submissions")
        }
        "canvas_get_submission" => {
            result
                .query
                .push(("include[]".into(), "submission_comments".into()));
            let user = if args.contains_key("user_id") {
                number("user_id")
            } else {
                "self".into()
            };
            format!("courses/{course}/assignments/{assignment}/submissions/{user}")
        }
        "canvas_list_calendar_events" => {
            if !course.is_empty() {
                result.context = Some(format!("course_{course}"));
                result
                    .query
                    .push(("context_codes[]".into(), format!("course_{course}")));
            }
            "calendar_events".into()
        }
        "canvas_create_assignment" | "canvas_update_assignment" => {
            result.method = if name == "canvas_create_assignment" {
                "POST"
            } else {
                "PUT"
            };
            let mut body = Map::new();
            for key in [
                "name",
                "description",
                "due_at",
                "points_possible",
                "submission_types",
                "published",
            ] {
                if let Some(value) = args.get(key) {
                    body.insert(key.into(), value.clone());
                }
            }
            if result.method == "POST" {
                body.entry("published").or_insert(json!(false));
                body.entry("submission_types")
                    .or_insert(json!(["online_text_entry"]));
            } else if body.is_empty() {
                return Err("Provide at least one assignment field to update".into());
            }
            result.body = Some(json!({"assignment":body}));
            if result.method == "POST" {
                format!("courses/{course}/assignments")
            } else {
                format!("courses/{course}/assignments/{assignment}")
            }
        }
        "canvas_submit_assignment" => {
            result.method = "POST";
            let kind = args["submission_type"].as_str().expect("validated string");
            let mut submission = json!({"submission_type":kind});
            if kind == "online_text_entry" {
                submission["body"] = args
                    .get("body")
                    .cloned()
                    .ok_or("Text submissions require body")?;
                if args.contains_key("url") {
                    return Err("Text submissions do not accept url".into());
                }
            } else {
                let address = args
                    .get("url")
                    .and_then(Value::as_str)
                    .ok_or("URL submissions require url")?;
                let url =
                    url::Url::parse(address).map_err(|_| "Submission URL must be HTTP or HTTPS")?;
                if !matches!(url.scheme(), "https" | "http")
                    || url.host_str().is_none()
                    || !url.username().is_empty()
                    || url.password().is_some()
                {
                    return Err("Submission URL must be HTTP or HTTPS without credentials".into());
                }
                if args.contains_key("body") {
                    return Err("URL submissions do not accept body".into());
                }
                submission["url"] = json!(address);
            }
            result.body = Some(json!({"submission":submission}));
            format!("courses/{course}/assignments/{assignment}/submissions")
        }
        "canvas_grade_submission" => {
            result.method = "PUT";
            let mut body = json!({"submission":{"posted_grade":args["posted_grade"]}});
            if let Some(comment) = args.get("comment") {
                body["comment"] = json!({"text_comment":comment});
            }
            result.body = Some(body);
            format!(
                "courses/{course}/assignments/{assignment}/submissions/{}",
                number("user_id")
            )
        }
        "canvas_post_announcement" => {
            result.method = "POST";
            result.body = Some(
                json!({"title":args["title"],"message":args["message"],"is_announcement":true,"published":true}),
            );
            format!("courses/{course}/discussion_topics")
        }
        _ => return Err("Unknown tool".into()),
    };
    result.path = path.split('/').map(str::to_owned).collect();
    if name == "canvas_get_page" {
        let page = args["page"].as_str().expect("validated string");
        if matches!(page, "." | "..")
            || page.chars().any(|c| c.is_control() || "/\\?#%".contains(c))
        {
            return Err("Use a page slug or page_id:<id>, without URL/path separators".into());
        }
        result.path.push(page.into());
    }
    for key in [
        "search_term",
        "bucket",
        "enrollment_state",
        "start_date",
        "end_date",
        "type",
    ] {
        if let Some(value) = args.get(key).and_then(Value::as_str) {
            result.query.push((key.into(), value.into()));
        }
    }
    if result.list {
        result.query.push((
            "per_page".into(),
            args.get("per_page")
                .and_then(Value::as_u64)
                .unwrap_or(20)
                .to_string(),
        ));
    }
    result.fields = fields(name);
    Ok(result)
}

fn validate(args: &Map<String, Value>, schema: &Map<String, Value>) -> Result<(), String> {
    let props = schema["properties"].as_object().expect("static properties");
    for key in schema["required"].as_array().expect("static required") {
        if !args.contains_key(key.as_str().expect("static required name")) {
            return Err(format!("Missing required argument: {key}"));
        }
    }
    for (key, value) in args {
        let rules = props
            .get(key)
            .ok_or_else(|| format!("Unknown argument: {key}"))?;
        validate_value(value, rules)
            .map_err(|_| format!("Invalid argument: {key}; follow its input schema"))?;
    }
    Ok(())
}

fn validate_value(value: &Value, rules: &Value) -> Result<(), ()> {
    let matches_type = |kind: &str| match kind {
        "string" => value.is_string(),
        "boolean" => value.is_boolean(),
        "integer" => value.as_u64().is_some(),
        "number" => value.is_number(),
        "array" => value.is_array(),
        "null" => value.is_null(),
        _ => false,
    };
    let valid = match &rules["type"] {
        Value::String(kind) => matches_type(kind),
        Value::Array(types) => types
            .iter()
            .any(|kind| matches_type(kind.as_str().unwrap_or_default())),
        _ => false,
    };
    if !valid {
        return Err(());
    }
    if let Some(choices) = rules.get("enum").and_then(Value::as_array)
        && !choices.contains(value)
    {
        return Err(());
    }
    if let Some(text) = value.as_str() {
        let length = text.chars().count() as u64;
        if rules
            .get("minLength")
            .and_then(Value::as_u64)
            .is_some_and(|n| length < n)
            || rules
                .get("maxLength")
                .and_then(Value::as_u64)
                .is_some_and(|n| length > n)
        {
            return Err(());
        }
    }
    if let Some(number) = value.as_f64()
        && (rules
            .get("minimum")
            .and_then(Value::as_f64)
            .is_some_and(|n| number < n)
            || rules
                .get("maximum")
                .and_then(Value::as_f64)
                .is_some_and(|n| number > n))
    {
        return Err(());
    }
    if let Some(items) = value.as_array() {
        let length = items.len() as u64;
        if rules
            .get("minItems")
            .and_then(Value::as_u64)
            .is_some_and(|n| length < n)
            || rules
                .get("maxItems")
                .and_then(Value::as_u64)
                .is_some_and(|n| length > n)
        {
            return Err(());
        }
        for item in items {
            validate_value(item, &rules["items"])?;
        }
    }
    Ok(())
}

fn fields(name: &str) -> &'static [&'static str] {
    match name {
        "canvas_get_profile" => &["id", "name", "short_name", "time_zone", "locale"],
        "canvas_list_courses" => &[
            "id",
            "name",
            "course_code",
            "workflow_state",
            "start_at",
            "end_at",
            "time_zone",
            "enrollments",
        ],
        "canvas_get_course" => &[
            "id",
            "name",
            "course_code",
            "workflow_state",
            "time_zone",
            "syllabus_body",
            "permissions",
        ],
        "canvas_list_assignments" => &[
            "id",
            "name",
            "due_at",
            "points_possible",
            "submission_types",
            "html_url",
            "published",
            "locked_for_user",
            "has_submitted_submissions",
        ],
        "canvas_get_assignment" => &[
            "id",
            "name",
            "description",
            "due_at",
            "lock_at",
            "unlock_at",
            "points_possible",
            "submission_types",
            "html_url",
            "published",
            "locked_for_user",
            "submission",
        ],
        "canvas_list_modules" => &[
            "id",
            "name",
            "position",
            "items_count",
            "state",
            "unlock_at",
            "published",
        ],
        "canvas_list_module_items" => &[
            "id",
            "title",
            "type",
            "content_id",
            "page_url",
            "external_url",
            "html_url",
            "completion_requirement",
        ],
        "canvas_list_pages" => &[
            "page_id",
            "url",
            "title",
            "published",
            "html_url",
            "updated_at",
            "locked_for_user",
        ],
        "canvas_get_page" => &[
            "page_id",
            "url",
            "title",
            "body",
            "published",
            "html_url",
            "updated_at",
            "locked_for_user",
            "lock_explanation",
        ],
        "canvas_list_announcements" | "canvas_list_discussions" => &[
            "id",
            "title",
            "posted_at",
            "html_url",
            "published",
            "discussion_subentry_count",
            "unread_count",
            "context_code",
        ],
        "canvas_get_discussion" => &[
            "id",
            "title",
            "message",
            "posted_at",
            "html_url",
            "published",
            "discussion_subentry_count",
            "locked_for_user",
        ],
        "canvas_list_files" => &[
            "id",
            "display_name",
            "filename",
            "content-type",
            "size",
            "url",
            "locked_for_user",
        ],
        "canvas_list_enrollments" => &[
            "id",
            "course_id",
            "user_id",
            "type",
            "enrollment_state",
            "grades",
        ],
        "canvas_list_submissions" => &[
            "assignment_id",
            "user_id",
            "submitted_at",
            "workflow_state",
            "late",
            "missing",
            "grade",
            "score",
            "attempt",
            "preview_url",
        ],
        "canvas_get_submission" => &[
            "assignment_id",
            "user_id",
            "body",
            "url",
            "submitted_at",
            "workflow_state",
            "late",
            "missing",
            "grade",
            "score",
            "attempt",
            "submission_comments",
            "preview_url",
        ],
        "canvas_list_calendar_events" => &[
            "id",
            "title",
            "start_at",
            "end_at",
            "context_code",
            "html_url",
            "type",
            "description",
        ],
        _ => &[],
    }
}
