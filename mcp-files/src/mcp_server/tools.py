import json
import shutil
import time
from .helpers import _resolve, _iter_files, _iter_paths, _check_tree, _ok, _err
from .mcp import mcp
from .config import get_workspace

# ----------------------------- file + dir ops --------------------------- #


@mcp.tool
def create_file(path: str, content: str = "") -> str:
    """Create a new text file without overwriting an existing file."""
    try:
        p = _resolve(path)
        p.parent.mkdir(parents=True, exist_ok=True)
        with p.open("x", encoding="utf-8") as f:
            f.write(content)
        return _ok(f"created: {path}")
    except Exception as e:  # pragma: no cover
        return _err(e)


@mcp.tool
def read_file(path: str) -> str:
    """Read a text file."""
    try:
        return _resolve(path).read_text(encoding="utf-8")
    except FileNotFoundError:
        return f"Not found: {path}"
    except Exception as e:  # pragma: no cover
        return _err(e)


@mcp.tool
def write_file(path: str, content: str) -> str:
    """Overwrite (or create) a file."""
    try:
        p = _resolve(path)
        p.parent.mkdir(parents=True, exist_ok=True)
        p.write_text(content, encoding="utf-8")
        return _ok(f"written: {path}")
    except Exception as e:  # pragma: no cover
        return _err(e)


@mcp.tool
def append_file(path: str, content: str) -> str:
    """Append to a file (creates if missing)."""
    try:
        p = _resolve(path)
        p.parent.mkdir(parents=True, exist_ok=True)
        with p.open("a", encoding="utf-8") as f:
            f.write(content)
        return _ok(f"appended: {path}")
    except Exception as e:  # pragma: no cover
        return _err(e)


@mcp.tool
def delete_path(path: str) -> str:
    """Delete file or directory (recursive)."""
    try:
        p = _resolve(path, protect_root=True)
        _check_tree(p)
        if p.is_dir():
            shutil.rmtree(p)
        elif p.exists():
            p.unlink()
        else:
            return f"Not found: {path}"
        return _ok(f"deleted: {path}")
    except Exception as e:  # pragma: no cover
        return _err(e)


@mcp.tool
def rename_path(src: str, dst: str) -> str:
    """Rename a file or directory inside the workspace."""
    try:
        s = _resolve(src, protect_root=True)
        d = _resolve(dst, protect_root=True)
        _check_tree(s)
        _check_tree(d)
        d.parent.mkdir(parents=True, exist_ok=True)
        s.rename(d)
        return _ok(f"renamed: {src} -> {dst}")
    except FileNotFoundError:
        return f"Not found: {src}"
    except Exception as e:  # pragma: no cover
        return _err(e)


@mcp.tool
def copy_path(src: str, dst: str) -> str:
    """Copy file or directory."""
    try:
        s = _resolve(src)
        d = _resolve(dst, protect_root=True)
        if not s.exists():
            return f"Not found: {src}"
        if s == d or s in d.parents:
            raise ValueError("Cannot copy a path into itself")
        _check_tree(s)
        _check_tree(d)
        if s.is_dir():
            shutil.copytree(s, d, dirs_exist_ok=True)
        else:
            d.parent.mkdir(parents=True, exist_ok=True)
            shutil.copy2(s, d)
        return _ok(f"copied: {src} -> {dst}")
    except Exception as e:  # pragma: no cover
        return _err(e)


@mcp.tool
def move_path(src: str, dst: str) -> str:
    """Move file or directory."""
    try:
        s = _resolve(src, protect_root=True)
        d = _resolve(dst, protect_root=True)
        if not s.exists():
            return f"Not found: {src}"
        if s == d or s in d.parents:
            raise ValueError("Cannot move a path into itself")
        _check_tree(s)
        _check_tree(d)
        d.parent.mkdir(parents=True, exist_ok=True)
        shutil.move(str(s), str(d))
        return _ok(f"moved: {src} -> {dst}")
    except Exception as e:  # pragma: no cover
        return _err(e)


@mcp.tool
def list_files() -> str:
    """List all files (relative)."""
    try:
        files = sorted(str(p.relative_to(get_workspace())) for p in _iter_files())
        return "\n".join(files) if files else "(none)"
    except Exception as e:  # pragma: no cover
        return _err(e)


@mcp.tool
def list_dirs() -> str:
    """List all directories (relative)."""
    try:
        dirs = sorted(str(p.relative_to(get_workspace())) for p in _iter_paths() if p.is_dir())
        return "\n".join(dirs) if dirs else "(none)"
    except Exception as e:  # pragma: no cover
        return _err(e)


@mcp.tool
def search_file(path: str, term: str) -> str:
    """Return matching lines containing term."""
    try:
        p = _resolve(path)
        lines = []
        for i, line in enumerate(p.read_text(encoding="utf-8").splitlines(), 1):
            if term in line:
                lines.append(f"{i}: {line.strip()}")
        return "\n".join(lines) if lines else "(no matches)"
    except FileNotFoundError:
        return f"Not found: {path}"
    except Exception as e:  # pragma: no cover
        return _err(e)


@mcp.tool
def file_info(path: str) -> str:
    """Basic metadata (JSON)."""
    try:
        p = _resolve(path)
        if not p.exists():
            return f"Not found: {path}"
        st = p.stat()
        info = {
            "path": path,
            "type": "dir" if p.is_dir() else "file",
            "size": st.st_size,
            "modified": time.strftime("%Y-%m-%d %H:%M:%S", time.localtime(st.st_mtime)),
            "created": time.strftime("%Y-%m-%d %H:%M:%S", time.localtime(st.st_ctime)),
            "absolute": str(p),
        }
        if p.is_file():
            try:
                info["lines"] = sum(1 for _ in p.open("r", encoding="utf-8"))
            except Exception:
                pass
        return json.dumps(info, indent=2)
    except Exception as e:  # pragma: no cover
        return _err(e)


@mcp.tool
def workspace_stats() -> str:
    """Aggregate workspace stats (JSON)."""
    try:
        files = 0
        dirs = 0
        size = 0
        exts: dict[str, int] = {}
        for p in _iter_paths():
            if p.is_dir():
                dirs += 1
            elif p.is_file():
                files += 1
                try:
                    size += p.stat().st_size
                except OSError:
                    pass
                ext = p.suffix.lower() or "<none>"
                exts[ext] = exts.get(ext, 0) + 1
        data = {
            "workspace": str(get_workspace()),
            "files": files,
            "directories": dirs,
            "bytes": size,
            "extensions": dict(sorted(exts.items(), key=lambda x: (-x[1], x[0]))),
        }
        return json.dumps(data, indent=2)
    except Exception as e:  # pragma: no cover
        return _err(e)


@mcp.tool
def path_exists(path: str) -> str:
    """Return one of: file | dir | none."""
    try:
        p = _resolve(path)
        if p.is_file():
            return "file"
        if p.is_dir():
            return "dir"
        return "none"
    except Exception:  # pragma: no cover
        return "none"

