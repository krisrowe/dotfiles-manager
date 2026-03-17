"""High-level sync operations.

Orchestrates track/untrack/sync/restore workflows using repo primitives.
"""

import subprocess
from pathlib import Path

from .config import get_repo_dir, get_work_tree, get_exclude_file, get_config_dir
from . import repo


def track(path: str) -> dict:
    """Start tracking a file or directory.

    Initializes repo if needed. Commits immediately.
    Returns dict with tracked path info.
    """
    repo.init()
    _ensure_exclude_file()

    abs_path = Path(path).expanduser().resolve()
    work_tree = get_work_tree()

    if not abs_path.exists():
        return {"success": False, "error": f"Path does not exist: {abs_path}"}

    try:
        rel_path = abs_path.relative_to(work_tree)
    except ValueError:
        return {"success": False, "error": f"Path must be under {work_tree}"}

    # Reset any leftover staged state from previous failed attempts
    # without touching the working tree or tracked files.
    repo.reset_staged()

    repo.add(str(abs_path))
    try:
        committed = repo.commit(f"Track {rel_path}")
    except repo.DotGitError:
        # Commit failed (e.g., hook rejected) — unstage so we don't
        # leave dirty state that poisons future commands.
        repo.reset_staged()
        raise
    return {
        "success": True,
        "path": str(rel_path),
        "committed": committed,
    }


def untrack(path: str) -> dict:
    """Stop tracking a file or directory. Keeps local file.

    Returns dict with result.
    """
    abs_path = Path(path).expanduser().resolve()
    work_tree = get_work_tree()

    try:
        rel_path = abs_path.relative_to(work_tree)
    except ValueError:
        return {"success": False, "error": f"Path must be under {work_tree}"}

    tracked = repo.list_tracked()
    rel_str = str(rel_path)
    matches = [f for f in tracked if f == rel_str or f.startswith(rel_str + "/")]
    if not matches:
        return {"success": False, "error": f"Not tracked: {rel_path}"}

    repo.remove_from_tracking(str(abs_path))
    committed = repo.commit(f"Untrack {rel_path}")
    return {
        "success": True,
        "path": str(rel_path),
        "files_removed": len(matches),
        "committed": committed,
    }


def get_status() -> dict:
    """Get status of tracked files.

    Returns dict with changed files list.
    """
    if not repo.is_initialized():
        return {"initialized": False, "changes": []}
    changes = repo.status()
    return {"initialized": True, "changes": changes}


def get_list() -> dict:
    """List all tracked files.

    Returns dict with file list.
    """
    if not repo.is_initialized():
        return {"initialized": False, "files": []}
    files = repo.list_tracked()
    return {"initialized": True, "files": files, "count": len(files)}


def sync(skip_hooks: bool = False) -> dict:
    """Self-healing sync: commit local changes, pull, push.

    1. Init repo if needed
    2. Ensure exclude file tracked
    3. Stage + commit any dirty tracked files
    4. Pull --rebase from origin
    5. Push to origin

    Returns dict describing what happened.
    """
    repo.init()
    _ensure_exclude_file()

    actions = []

    # Commit local changes
    changes = repo.status()
    if changes:
        committed = repo.commit(
            _auto_commit_message(changes), skip_hooks=skip_hooks,
        )
        if committed:
            actions.append(f"Committed {len(changes)} changed file(s)")

    # Pull then push if remote exists
    if repo.has_remote():
        repo.pull()
        actions.append("Pulled from origin")

        if repo.has_unpushed():
            repo.push()
            actions.append("Pushed to origin")
        else:
            actions.append("Already up to date with origin")
    else:
        actions.append("No remote configured — skipped push/pull")

    return {"success": True, "actions": actions}


def restore(repo_url: str) -> dict:
    """Clone from GitHub and checkout dotfiles to home directory.

    If files conflict, reports them and stops. User must resolve
    manually (move/delete conflicting files) then run 'dot git checkout'.
    """
    repo_dir = get_repo_dir()

    if repo.is_initialized():
        return {
            "success": False,
            "error": "Repo already exists. Use 'dot sync' to pull changes.",
        }

    # Clone bare
    subprocess.run(
        ["git", "clone", "--bare", repo_url, str(repo_dir)],
        capture_output=True, text=True, check=True,
    )

    # Configure
    repo.init()  # Sets showUntrackedFiles, excludesFile

    # Try checkout
    result = repo.git_passthrough(["checkout"])
    if result.returncode == 0:
        return {"success": True, "actions": ["Cloned and checked out all files"]}

    # Checkout failed — report conflicts
    conflicting = _parse_checkout_conflicts(result.stderr)
    if conflicting:
        return {
            "success": False,
            "error": "Checkout blocked by existing files",
            "conflicting_files": conflicting,
            "hint": "Move or delete the listed files, then run: dot git checkout",
        }

    return {
        "success": False,
        "error": f"Checkout failed: {result.stderr}",
    }


def _ensure_exclude_file():
    """Ensure the exclude file exists and is tracked."""
    exclude_file = get_exclude_file()
    if not exclude_file.exists():
        exclude_file.parent.mkdir(parents=True, exist_ok=True)
        exclude_file.write_text(
            "# dotgit exclude file (gitignore format)\n"
            "# Managed by 'dot exclude' commands\n"
        )
    # Track the config dir
    config_dir = get_config_dir()
    if config_dir.exists():
        repo.add(str(config_dir))


def _auto_commit_message(changes: list[dict]) -> str:
    """Generate a commit message from changed files."""
    if len(changes) == 1:
        c = changes[0]
        return f"{c['status'].capitalize()} {c['path']}"
    return f"Sync {len(changes)} file(s)"


def _parse_checkout_conflicts(stderr: str) -> list[str]:
    """Parse conflicting file paths from git checkout stderr."""
    files = []
    for line in stderr.splitlines():
        line = line.strip()
        if line and not line.startswith("error:") and not line.startswith("Please"):
            files.append(line)
    return files
