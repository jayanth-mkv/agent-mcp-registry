"""Exercise the installed CLI and guard against workspace escapes."""

import asyncio
import json
from pathlib import Path
import sys

from fastmcp import Client
from fastmcp.client.transports import StdioTransport
import pytest

from mcp_server import config, mcp
from mcp_server.helpers import _resolve


def test_stdio_file_lifecycle_and_workspace_override(tmp_path):
    async def check():
        transport = StdioTransport(
            command=sys.executable,
            args=["-m", "mcp_server.cli", "--workspace", str(tmp_path)],
        )
        async with Client(transport) as client:
            tools = await client.list_tools()
            assert len(tools) == 14

            async def call(name, **arguments):
                result = await client.call_tool(name, arguments)
                return result.content[0].text

            await call("create_file", path="notes/a.txt", content="first")
            assert (tmp_path / "notes/a.txt").read_text() == "first"
            duplicate = await client.call_tool("create_file", {"path": "notes/a.txt"}, raise_on_error=False)
            assert duplicate.is_error
            assert (tmp_path / "notes/a.txt").read_text() == "first"
            await call("write_file", path="notes/a.txt", content="hello")
            await call("append_file", path="notes/a.txt", content="\nworld")
            assert await call("read_file", path="notes/a.txt") == "hello\nworld"
            assert await call("search_file", path="notes/a.txt", term="world") == "2: world"
            assert json.loads(await call("file_info", path="notes/a.txt"))["lines"] == 2
            assert "notes" in await call("list_dirs")
            assert "a.txt" in await call("list_files")
            assert await call("path_exists", path="notes/a.txt") == "file"
            await call("copy_path", src="notes", dst="backup")
            await call("move_path", src="backup/a.txt", dst="moved.txt")
            await call("rename_path", src="moved.txt", dst="renamed.txt")
            stats = json.loads(await call("workspace_stats"))
            assert Path(stats["workspace"]) == tmp_path.resolve()
            assert stats["files"] == 2
            for tool, arguments in (
                ("read_file", {"path": "../outside.txt"}),
                ("write_file", {"path": "../outside.txt", "content": "escape"}),
                ("delete_path", {"path": "."}),
                ("move_path", {"src": ".", "dst": "new"}),
                ("rename_path", {"src": ".", "dst": "new"}),
                ("copy_path", {"src": "notes", "dst": "notes/recursive"}),
            ):
                result = await client.call_tool(tool, arguments, raise_on_error=False)
                assert result.is_error, (tool, result)
            await call("delete_path", path="notes")
            assert await call("path_exists", path="notes") == "none"
            assert (tmp_path / "renamed.txt").is_file()

    asyncio.run(check())


@pytest.mark.parametrize("path", ["../outside.txt", "nested/../../outside.txt"])
def test_relative_escape_is_rejected(tmp_path, monkeypatch, path):
    monkeypatch.setattr(config, "_workspace", tmp_path)
    with pytest.raises(ValueError, match="escapes"):
        _resolve(path)


def test_absolute_escape_is_rejected(tmp_path, monkeypatch):
    monkeypatch.setattr(config, "_workspace", tmp_path)
    with pytest.raises(ValueError, match="escapes"):
        _resolve(str(tmp_path.parent / "outside.txt"))


def test_environment_workspace_is_loaded_lazily(tmp_path, monkeypatch):
    monkeypatch.setattr(config, "_workspace", None)
    target = tmp_path / "from-env"
    monkeypatch.setenv("MCP_WORKSPACE_DIR", str(target))
    assert not target.exists()
    assert config.get_workspace() == target.resolve()
    assert target.is_dir()


def test_linked_files_cannot_be_read_or_copied(tmp_path, monkeypatch):
    root = tmp_path / "workspace"
    root.mkdir()
    outside = tmp_path / "outside.txt"
    outside.write_text("private")
    source = root / "source"
    source.mkdir()
    try:
        (source / "link.txt").symlink_to(outside)
    except OSError:
        pytest.skip("Creating symlinks requires Windows Developer Mode or elevated rights")
    monkeypatch.setattr(config, "_workspace", root)

    async def check():
        async with Client(mcp) as client:
            for name, args in (
                ("read_file", {"path": "source/link.txt"}),
                ("copy_path", {"src": "source", "dst": "copy"}),
            ):
                assert (await client.call_tool(name, args, raise_on_error=False)).is_error
        assert not (root / "copy").exists()
        assert outside.read_text() == "private"

    asyncio.run(check())


@pytest.mark.skipif(sys.platform != "win32", reason="Windows junction regression")
def test_junction_tree_cannot_be_copied(tmp_path, monkeypatch):
    import _winapi

    root = tmp_path / "workspace"
    source = root / "source"
    source.mkdir(parents=True)
    outside = tmp_path / "private"
    outside.mkdir()
    (outside / "secret.txt").write_text("private")
    _winapi.CreateJunction(str(outside), str(source / "linked"))
    monkeypatch.setattr(config, "_workspace", root)

    async def check():
        async with Client(mcp) as client:
            for name, arguments in (
                ("read_file", {"path": "source/linked/secret.txt"}),
                ("copy_path", {"src": "source", "dst": "copy"}),
            ):
                assert (await client.call_tool(name, arguments, raise_on_error=False)).is_error
        assert not (root / "copy").exists()
        assert (outside / "secret.txt").read_text() == "private"

    asyncio.run(check())
