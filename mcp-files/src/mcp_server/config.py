"""Runtime configuration without filesystem changes during import."""

import os
from pathlib import Path

DEFAULT_HOST = "127.0.0.1"
DEFAULT_PORT = 8000
_workspace: Path | None = None


def configure_workspace(path: str | None = None) -> Path:
    global _workspace
    root = Path(path or os.getenv("MCP_WORKSPACE_DIR", "workspace")).resolve()
    root.mkdir(parents=True, exist_ok=True)
    if not root.is_dir():
        raise ValueError("Workspace must be a directory")
    _workspace = root
    return root


def get_workspace() -> Path:
    return _workspace if _workspace is not None else configure_workspace()
