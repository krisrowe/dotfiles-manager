"""Global gitignore management.

Manages patterns in ~/.config/git/ignore (the global gitignore).
Also syncs patterns to each store's info/exclude.
"""

from pathlib import Path

from .config import get_work_tree


STANDARD_PATTERNS = [
    ".credentials.json",
    "client_secrets.json",
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
    Also tracks the ignore file in the default store.
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

    # Track in default store (always default, regardless of --store)
    from . import sync
    from .config import get_current_store, set_current_store
    ignore_path = _ignore_file()
    if ignore_path.exists():
        prev_store = get_current_store()
        set_current_store(None)
        try:
            sync.track(str(ignore_path))
        finally:
            set_current_store(prev_store)

    # Add patterns to each store's info/exclude
    _sync_to_stores()

    return {
        "success": True,
        "added": added,
        "file": str(_ignore_file()),
    }


def add(pattern: str) -> dict:
    """Add a pattern to the global gitignore. Idempotent."""
    existing = _read_lines()
    if pattern in existing:
        return {"success": True, "added": False, "message": f"Already ignored: {pattern}"}

    raw = _read_raw()
    if raw and not raw.endswith("\n"):
        raw += "\n"
    raw += pattern + "\n"
    _write(raw)

    # Also add to each store's info/exclude
    _add_to_stores(pattern)

    return {"success": True, "added": True, "pattern": pattern}


def remove(pattern: str) -> dict:
    """Remove a pattern from the global gitignore."""
    path = _ignore_file()
    if not path.exists():
        return {"success": False, "error": "No global gitignore file found."}

    existing = _read_lines()
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


def _sync_to_stores() -> None:
    """Add standard patterns to each store's info/exclude."""
    for pattern in STANDARD_PATTERNS:
        _add_to_stores(pattern)


def _add_to_stores(pattern: str) -> None:
    """Add a pattern to every store's info/exclude."""
    from . import stores as stores_mod
    from .repo import get_exclude_file
    from .config import get_repo_dir
    import os

    # Default store
    exclude = get_exclude_file()
    _add_to_exclude(exclude, pattern)

    # Named stores
    data = stores_mod._read_stores()
    for name, info in data.get("stores", {}).items():
        repo_path = Path(info.get("repo", "")).expanduser()
        exclude = repo_path / "info" / "exclude"
        if exclude.parent.exists():
            _add_to_exclude(exclude, pattern)


def _add_to_exclude(exclude_path: Path, pattern: str) -> None:
    """Add a pattern to an exclude file if not already present."""
    if not exclude_path.exists():
        return
    content = exclude_path.read_text()
    existing = [ln.strip() for ln in content.splitlines() if ln.strip() and not ln.strip().startswith("#")]
    if pattern in existing:
        return
    if not content.endswith("\n"):
        content += "\n"
    content += pattern + "\n"
    exclude_path.write_text(content)
