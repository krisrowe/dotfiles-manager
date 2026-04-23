"""Global gitignore management.

Manages patterns in ~/.config/git/ignore (the global gitignore).
Because dotgit uses $HOME as the work tree, Git naturally respects
this file for all stores. Users should track this file in a store
of their choice (e.g., 'work' or 'secrets') to version it.
"""

import sys
from pathlib import Path
from .config import get_work_tree

STANDARD_PATTERNS = [
    ".credentials.json",
    "client_secrets.json",
    ".DS_Store",
    "*.pyc",
    "__pycache__/",
]

def _ignore_file() -> Path:
    """Path to the global gitignore file."""
    return get_work_tree() / ".config" / "git" / "ignore"

def _read_lines() -> list[str]:
    """Read non-comment, non-blank lines."""
    path = _ignore_file()
    if not path.exists():
        return []
    return [
        ln.strip()
        for ln in path.read_text().splitlines()
        if ln.strip() and not ln.strip().startswith("#")
    ]

def _read_raw() -> str:
    """Read the full file content."""
    path = _ignore_file()
    if not path.exists():
        return ""
    return path.read_text()

def _write(content: str) -> None:
    """Write the ignore file, creating parent dirs if needed."""
    path = _ignore_file()
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(content)

def init() -> dict:
    """Ensure global gitignore exists with standard patterns.

    Idempotent — adds missing standard patterns, skips existing ones.
    Also tracks the ignore file in the active store.
    """
    existing = _read_lines()
    added = []

    for pattern in STANDARD_PATTERNS:
        if pattern not in existing:
            added.append(pattern)

    if added:
        raw = _read_raw()
        if raw and not raw.endswith("\n"):
            raw += "\n"
        raw += "\n".join(added) + "\n"
        _write(raw)

    # Track in the active store
    from . import sync
    from .config import get_invocation_store, set_invocation_store, get_active_store
    ignore_path = _ignore_file()
    if ignore_path.exists():
        active = get_active_store()
        if active:
            prev_store = get_invocation_store()
            set_invocation_store(active)
            try:
                sync.track(str(ignore_path))
            finally:
                set_invocation_store(prev_store)

    return {
        "success": True,
        "added": added,
        "file": str(_ignore_file()),
    }

def add(pattern: str) -> dict:
    """Add a pattern to the global gitignore. Idempotent."""
    if pattern.startswith("!"):
        print(
            "VISIBILITY WARNING: Ignore exceptions ('!') create a blackout for the parent folder.\n"
            "                   If this directory contains valuable files, consider ignoring\n"
            "                   its specific siblings instead. This keeps the parent folder\n"
            "                   'open' so you have a chance to notice and make a conscious\n"
            "                   choice when new files appear there in the future.\n",
            file=sys.stderr
        )

    existing = _read_lines()
    if pattern in existing:
        return {"success": True, "added": False, "message": f"Already ignored: {pattern}"}

    raw = _read_raw()
    if raw and not raw.endswith("\n"):
        raw += "\n"
    raw += pattern + "\n"
    _write(raw)

    return {"success": True, "added": True, "pattern": pattern}

def remove(pattern: str) -> dict:
    """Remove a pattern from the global gitignore."""
    path = _ignore_file()
    if not path.exists():
        return {"success": False, "error": "No global gitignore file found."}

    existing = _read_lines()
    if pattern in existing:
        if pattern not in existing:
            return {"success": False, "error": f"Pattern not found: {pattern}"}

    raw_lines = path.read_text().splitlines(keepends=True)
    new_lines = [ln for ln in raw_lines if ln.strip() != pattern]
    path.write_text("".join(new_lines))

    return {"success": True, "removed": True, "pattern": pattern}

def list_patterns() -> dict:
    """List all patterns in the global gitignore."""
    patterns = _read_lines()
    return {"patterns": patterns, "file": str(_ignore_file())}
