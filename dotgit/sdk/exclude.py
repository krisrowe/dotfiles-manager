"""Exclude pattern management.

Manages the gitignore-format exclude file at ~/.config/dotgit/exclude.
"""

from .config import get_exclude_file
from . import repo


def add(pattern: str) -> dict:
    """Add an exclude pattern. No-op if already present."""
    repo.init()
    exclude_file = get_exclude_file()
    exclude_file.parent.mkdir(parents=True, exist_ok=True)

    lines = _read_lines()
    if pattern in lines:
        return {"success": True, "added": False, "message": f"Already excluded: {pattern}"}

    with open(exclude_file, "a") as f:
        f.write(f"{pattern}\n")

    return {"success": True, "added": True, "pattern": pattern}


def remove(pattern: str) -> dict:
    """Remove an exclude pattern."""
    exclude_file = get_exclude_file()
    if not exclude_file.exists():
        return {"success": False, "error": "No exclude file found"}

    lines = _read_lines()
    if pattern not in lines:
        return {"success": False, "error": f"Pattern not found: {pattern}"}

    new_lines = [ln for ln in _read_raw_lines() if ln.strip() != pattern]
    exclude_file.write_text("".join(new_lines))
    return {"success": True, "removed": True, "pattern": pattern}


def list_patterns() -> dict:
    """List all exclude patterns (ignoring comments and blanks)."""
    patterns = _read_lines()
    return {"patterns": patterns, "count": len(patterns)}


def _read_lines() -> list[str]:
    """Read non-comment, non-blank lines from the exclude file."""
    exclude_file = get_exclude_file()
    if not exclude_file.exists():
        return []
    return [
        ln.strip()
        for ln in exclude_file.read_text().splitlines()
        if ln.strip() and not ln.strip().startswith("#")
    ]


def _read_raw_lines() -> list[str]:
    """Read all lines preserving format (with newlines)."""
    exclude_file = get_exclude_file()
    if not exclude_file.exists():
        return []
    with open(exclude_file) as f:
        return f.readlines()
