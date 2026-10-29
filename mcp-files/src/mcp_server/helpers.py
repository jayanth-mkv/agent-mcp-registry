import os
from pathlib import Path
from fastmcp.exceptions import ToolError
from .config import get_workspace
from typing import Iterable


# ----------------------------- helpers ---------------------------------- #

def _resolve(rel: str, *, protect_root: bool = False) -> Path:
    """Resolve a relative path safely within the workspace sandbox."""
    base = get_workspace()
    candidate = base / rel
    p = candidate.resolve()
    if base not in p.parents and p != base:
        raise ValueError("Path escapes workspace")
    for component in (candidate, *candidate.parents):
        if component == base:
            break
        if component.is_symlink() or component.is_junction():
            raise ValueError("Symbolic links and junctions are not supported")
    if protect_root and p == base:
        raise ValueError("Cannot replace, move, or delete the workspace root")
    return p


def _iter_files() -> Iterable[Path]:
    for p in _iter_paths():
        if p.is_file():
            yield p


def _iter_paths(root: Path | None = None) -> Iterable[Path]:
    """Walk without following links; reject linked entries before using them."""
    start = root if root is not None else get_workspace()
    for current, directories, files in os.walk(start, followlinks=False):
        for name in directories + files:
            p = Path(current) / name
            if p.is_symlink() or p.is_junction():
                raise ValueError("Symbolic links and junctions are not supported")
            yield p


def _check_tree(root: Path) -> None:
    if root.is_dir():
        for _ in _iter_paths(root):
            pass


def _ok(msg: str) -> str:  # tiny convention wrapper
    return msg


def _err(e: Exception) -> str:  # pragma: no cover (simple path)
    raise ToolError(str(e)) from e

__all__ = ["_resolve", "_iter_files", "_iter_paths", "_check_tree", "_ok", "_err"]
