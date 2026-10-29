"""Dependency-free MCP integration test against an authenticated mock Canvas API."""

from __future__ import annotations

import argparse
import ctypes
import http.server
import json
import os
from pathlib import Path
import queue
import subprocess
import tempfile
import threading
import time
import urllib.parse


class CanvasHandler(http.server.BaseHTTPRequestHandler):
    requests: list = []

    def log_message(self, *_):
        pass

    def handle_api(self):
        assert self.headers.get("Authorization") == "Bearer fixture-token"
        address = urllib.parse.urlsplit(self.path)
        query = urllib.parse.parse_qs(address.query)
        body = json.loads(self.rfile.read(int(self.headers.get("Content-Length", 0))) or b"null")
        self.requests.append((self.command, address.path, query, body))
        headers = {}
        path = address.path
        if self.command != "GET":
            data = {"id": 9, "saved": True}
        elif path == "/api/v1/courses":
            data = [{"id": 2 if query.get("page") == ["2"] else 1, "name": "Fixture course", "omit_me": "x" * 1000}]
            if "page" not in query:
                headers["Link"] = f'<http://127.0.0.1:{self.server.server_port}/api/v1/courses?page=2&per_page=20>; rel="next"'
        elif path.endswith("/profile"):
            data = {"id": 7, "name": "Fixture User", "omit_me": "private"}
        elif "/pages/" in path:
            data = {"page_id": 3, "title": "Introduction", "body": "🙂漢abc"}
        elif path.endswith("/submissions/self"):
            data = {"assignment_id": 2, "user_id": 7, "body": "Answer", "score": 10}
        elif path in ("/api/v1/courses/1", "/api/v1/courses/1/assignments/2", "/api/v1/courses/1/discussion_topics/3"):
            data = {"id": 1, "name": "Fixture", "title": "Fixture", "description": "<p>Instructions</p>", "message": "<p>Hello</p>"}
        else:
            data = [{"id": 1, "title": "Fixture", "name": "Fixture", "course_id": 1, "assignment_id": 2, "user_id": 7}]
        content = json.dumps(data).encode()
        self.send_response(200)
        self.send_header("Content-Type", "application/json")
        self.send_header("Content-Length", str(len(content)))
        for key, value in headers.items():
            self.send_header(key, value)
        self.end_headers()
        self.wfile.write(content)

    do_GET = handle_api
    do_POST = handle_api
    do_PUT = handle_api


def resident_bytes(pid):
    if os.name == "nt":
        from ctypes import wintypes

        class Counters(ctypes.Structure):
            _fields_ = [("cb", wintypes.DWORD), ("faults", wintypes.DWORD)] + [
                (name, ctypes.c_size_t) for name in (
                    "peak_working_set", "working_set", "peak_paged", "paged",
                    "peak_nonpaged", "nonpaged", "pagefile", "peak_pagefile",
                )
            ]

        kernel = ctypes.WinDLL("kernel32", use_last_error=True)
        kernel.OpenProcess.restype = wintypes.HANDLE
        kernel.OpenProcess.argtypes = [wintypes.DWORD, wintypes.BOOL, wintypes.DWORD]
        kernel.CloseHandle.argtypes = [wintypes.HANDLE]
        memory = ctypes.WinDLL("psapi").GetProcessMemoryInfo
        memory.argtypes = [wintypes.HANDLE, ctypes.POINTER(Counters), wintypes.DWORD]
        handle = kernel.OpenProcess(0x410, False, pid)
        try:
            counters = Counters()
            counters.cb = ctypes.sizeof(counters)
            return counters.working_set if memory(handle, ctypes.byref(counters), counters.cb) else None
        finally:
            if handle:
                kernel.CloseHandle(handle)
    status = Path(f"/proc/{pid}/status")
    if status.exists():
        for line in status.read_text().splitlines():
            if line.startswith("VmRSS:"):
                return int(line.split()[1]) * 1024
    return None


class Session:
    def __init__(self, binary, base, writes):
        self.messages = queue.Queue()
        self.next_id = 0
        self.stderr = tempfile.TemporaryFile(mode="w+b")
        environment = {key: value for key, value in os.environ.items() if not key.startswith("CANVAS_")}
        environment.update(CANVAS_BASE_URL=base, CANVAS_API_TOKEN="fixture-token",
                           CANVAS_ALLOW_HTTP="true", CANVAS_ENABLE_WRITES=str(writes).lower())
        started = time.perf_counter()
        self.process = subprocess.Popen([str(binary)], stdin=subprocess.PIPE, stdout=subprocess.PIPE,
                                        stderr=self.stderr, text=True, encoding="utf-8", env=environment)

        def read():
            try:
                for line in self.process.stdout:
                    self.messages.put(json.loads(line))
            except Exception as error:
                self.messages.put(error)

        self.reader = threading.Thread(target=read, daemon=True)
        self.reader.start()
        result = self.rpc("initialize", {"protocolVersion": "2025-11-25", "capabilities": {},
                                        "clientInfo": {"name": "independent-test", "version": "1.0.0"}})
        assert result["result"]["serverInfo"]["name"] == "mcp-canvas-lms", result
        self.startup_ms = (time.perf_counter() - started) * 1000
        self.send({"jsonrpc": "2.0", "method": "notifications/initialized"})

    def send(self, value):
        self.process.stdin.write(json.dumps(value, ensure_ascii=False) + "\n")
        self.process.stdin.flush()

    def rpc(self, method, parameters=None):
        self.next_id += 1
        request = {"jsonrpc": "2.0", "id": self.next_id, "method": method}
        if parameters is not None:
            request["params"] = parameters
        self.send(request)
        while True:
            response = self.messages.get(timeout=15)
            if isinstance(response, Exception):
                raise response
            if response.get("id") == self.next_id:
                return response

    def tool(self, name, arguments):
        response = self.rpc("tools/call", {"name": name, "arguments": arguments})
        assert "error" not in response, response
        result = response["result"]
        assert not result.get("isError"), result
        return json.loads(result["content"][0]["text"])

    def close(self):
        self.process.stdin.close()
        try:
            self.process.wait(timeout=5)
        except subprocess.TimeoutExpired:
            self.process.kill()
            self.process.wait()
            raise AssertionError("MCP did not shut down after stdin closed")
        self.reader.join(timeout=2)
        self.process.stdout.close()
        self.stderr.seek(0)
        logs = self.stderr.read().decode("utf-8", errors="replace")
        self.stderr.close()
        assert "fixture-token" not in logs, "Credentials appeared in stderr"
        assert self.process.returncode == 0, logs


def verify(binary):
    environment = {key: value for key, value in os.environ.items() if not key.startswith("CANVAS_")}
    for argument in ("--help", "--version"):
        assert subprocess.run([str(binary), argument], env=environment, capture_output=True, timeout=5).returncode == 0
    invalid = subprocess.run([str(binary)], env=environment, capture_output=True, timeout=5)
    assert invalid.returncode != 0 and invalid.stdout == b""
    api = http.server.ThreadingHTTPServer(("127.0.0.1", 0), CanvasHandler)
    thread = threading.Thread(target=api.serve_forever, daemon=True)
    thread.start()
    metrics = []
    try:
        for writes in (False, True):
            session = Session(binary, f"http://127.0.0.1:{api.server_port}", writes)
            try:
                tools = session.rpc("tools/list")["result"]["tools"]
                assert len(tools) == (22 if writes else 17)
                assert all(tool["inputSchema"]["additionalProperties"] is False for tool in tools)
                metrics.append({"writes": writes, "initialize_ms": round(session.startup_ms, 2),
                                "idle_rss_bytes": resident_bytes(session.process.pid),
                                "tool_schema_bytes": len(json.dumps(tools, separators=(",", ":")).encode())})
                profile = session.tool("canvas_get_profile", {})
                assert profile["data"] == {"id": 7, "name": "Fixture User"}
                first = session.tool("canvas_list_courses", {})
                assert first["data"][0]["id"] == 1 and "omit_me" not in first["data"][0]
                assert session.tool("canvas_list_courses", {"cursor": first["next_cursor"]})["data"][0]["id"] == 2
                cases = {
                    "canvas_get_course": {"course_id": 1},
                    "canvas_list_assignments": {"course_id": 1},
                    "canvas_get_assignment": {"course_id": 1, "assignment_id": 2},
                    "canvas_list_modules": {"course_id": 1},
                    "canvas_list_module_items": {"course_id": 1, "module_id": 2},
                    "canvas_list_pages": {"course_id": 1},
                    "canvas_get_page": {"course_id": 1, "page": "intro"},
                    "canvas_list_announcements": {"course_id": 1},
                    "canvas_list_discussions": {"course_id": 1},
                    "canvas_get_discussion": {"course_id": 1, "topic_id": 3},
                    "canvas_list_files": {"course_id": 1},
                    "canvas_list_enrollments": {},
                    "canvas_list_submissions": {"course_id": 1, "assignment_id": 2},
                    "canvas_get_submission": {"course_id": 1, "assignment_id": 2},
                    "canvas_list_calendar_events": {"course_id": 1},
                }
                for name, arguments in cases.items():
                    session.tool(name, arguments)
                window = session.tool("canvas_get_page", {"course_id": 1, "page": "intro", "text_limit": 2})
                assert window["data"]["body"] == "🙂漢"
                assert window["data"]["_mcp_text_windows"]["body"]["next_offset"] == 2
                before = len(CanvasHandler.requests)
                denied = session.rpc("tools/call", {"name": "canvas_create_assignment", "arguments": {"course_id": 1, "name": "Test"}})
                if not writes:
                    assert denied["error"]["code"] == -32602 and len(CanvasHandler.requests) == before
                else:
                    assert not denied["result"].get("isError")
                    session.tool("canvas_update_assignment", {"course_id": 1, "assignment_id": 2, "due_at": None})
                    session.tool("canvas_submit_assignment", {"course_id": 1, "assignment_id": 2, "submission_type": "online_text_entry", "body": "My answer"})
                    session.tool("canvas_grade_submission", {"course_id": 1, "assignment_id": 2, "user_id": 3, "posted_grade": "10", "comment": "Well done"})
                    session.tool("canvas_post_announcement", {"course_id": 1, "title": "News", "message": "<p>Hello</p>"})
                    assert [entry[0] for entry in CanvasHandler.requests[-5:]] == ["POST", "PUT", "POST", "PUT", "POST"]
                bad = session.rpc("tools/call", {"name": "canvas_list_courses", "arguments": {"per_page": 1000}})
                assert bad["error"]["code"] == -32602
                foreign = session.rpc("tools/call", {"name": "canvas_list_courses", "arguments": {"cursor": "https://evil.example/api/v1/courses"}})
                assert foreign["result"]["isError"]
            finally:
                session.close()
    finally:
        api.shutdown()
        api.server_close()
        thread.join(timeout=2)
    print(json.dumps({"binary_bytes": binary.stat().st_size, "modes": metrics, "result": "all 22 tools and MCP lifecycle passed"}, indent=2))


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--binary", type=Path, required=True)
    verify(parser.parse_args().binary.resolve())
