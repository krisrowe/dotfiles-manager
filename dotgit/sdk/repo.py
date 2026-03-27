"""Bare git repo operations.

All git commands go through this module. Nothing else in the codebase
should call git directly.
"""

import subprocess
from pathlib import Path

from .config import get_repo_dir, get_work_tree, require_explicit_store


class DotGitError(Exception):
    """Base error for dotgit operations."""


class RepoNotInitializedError(DotGitError):
    """Raised when the bare repo doesn't exist."""


def _git(
    *args: str,
    check: bool = True,
    skip_hooks: bool = False,
) -> subprocess.CompletedProcess:
    """Run a git command against the bare repo with the home work tree.

    Args:
        skip_hooks: If True, passes -c core.hooksPath=/dev/null for this
            invocation only. Does not affect persistent repo config.
    """
    repo_dir = get_repo_dir()
    work_tree = get_work_tree()
    cmd = [
        "git",
        f"--git-dir={repo_dir}",
        f"--work-tree={work_tree}",
    ]
    if skip_hooks:
        cmd.append("-c")
        cmd.append("core.hooksPath=/dev/null")
    cmd.extend(args)
    return subprocess.run(
        cmd, capture_output=True, text=True, check=check,
    )


def is_initialized() -> bool:
    """Check if the bare repo exists."""
    repo_dir = get_repo_dir()
    return (repo_dir / "HEAD").exists()


def init() -> Path:
    """Initialize the bare repo and configure it.

    Idempotent — safe to call if already initialized.
    Returns the repo directory path.
    """
    repo_dir = get_repo_dir()
    if not is_initialized():
        subprocess.run(
            ["git", "init", "--bare", "-b", "main", str(repo_dir)],
            capture_output=True, text=True, check=True,
        )

    # Ensure showUntrackedFiles is off
    _git("config", "status.showUntrackedFiles", "no")

    # Ensure info/exclude exists (git's built-in exclude mechanism)
    info_dir = repo_dir / "info"
    info_dir.mkdir(exist_ok=True)
    exclude_file = info_dir / "exclude"
    if not exclude_file.exists():
        exclude_file.write_text(
            "# dotgit exclude file (gitignore format)\n"
            "# Managed by 'dot exclude' commands\n"
        )

    # Migrate old exclude file from config dir if present
    _migrate_exclude_file(exclude_file)

    # Remove stale core.excludesFile config if set
    _git("config", "--unset", "core.excludesFile", check=False)

    return repo_dir


def get_exclude_file() -> Path:
    """Get the path to the exclude file (inside the bare repo)."""
    return get_repo_dir() / "info" / "exclude"


def _migrate_exclude_file(new_exclude: Path) -> None:
    """Migrate exclude file from old config dir location if present."""
    from .config import get_config_dir
    old_exclude = get_config_dir() / "exclude"
    if not old_exclude.exists():
        return
    # Only migrate if the old file has user content beyond the header
    old_content = old_exclude.read_text()
    has_user_content = any(
        line.strip() and not line.strip().startswith("#")
        for line in old_content.splitlines()
    )
    if has_user_content:
        # Append old patterns to new file
        new_exclude.write_text(new_exclude.read_text() + old_content)
    old_exclude.unlink()


def _require_repo():
    """Raise if repo not initialized."""
    if not is_initialized():
        raise RepoNotInitializedError(
            "Dotfiles repo not initialized. Run 'dot remote setup' or 'dot sync' first."
        )


# =========================================================================
# Hooks management
# =========================================================================


def hooks_disable() -> None:
    """Persistently disable hooks on the bare repo.

    Sets core.hooksPath=/dev/null in the repo config.
    """
    _require_repo()
    _git("config", "core.hooksPath", "/dev/null")


def hooks_reset() -> None:
    """Remove persistent hooks override, restoring global hooks."""
    _require_repo()
    _git("config", "--unset", "core.hooksPath", check=False)


def hooks_status() -> str:
    """Return current hooks state: 'disabled', 'custom', or 'default'."""
    _require_repo()
    result = _git("config", "--get", "core.hooksPath", check=False)
    if result.returncode != 0:
        return "default"
    path = result.stdout.strip()
    if path == "/dev/null":
        return "disabled"
    return f"custom ({path})"


# =========================================================================
# File tracking
# =========================================================================


def status() -> list[dict]:
    """Get status of tracked files.

    Returns list of dicts with 'status' and 'path' keys.
    """
    _require_repo()
    result = _git("status", "--porcelain")
    files = []
    for line in result.stdout.rstrip("\n").splitlines():
        if not line:
            continue
        code = line[:2].strip()
        path = line[3:]
        status_map = {
            "M": "modified",
            "A": "added",
            "D": "deleted",
            "R": "renamed",
            "T": "type_changed",
        }
        files.append({
            "status": status_map.get(code, code),
            "path": path,
        })
    return files


def list_tracked() -> list[str]:
    """List all tracked files (relative to work tree).

    Uses ls-tree against HEAD rather than ls-files (the index),
    because the index can get out of sync in bare repo setups.
    Runs without --work-tree since ls-tree reads the committed
    tree, not the working directory.
    """
    _require_repo()
    repo_dir = get_repo_dir()
    result = subprocess.run(
        ["git", f"--git-dir={repo_dir}", "ls-tree", "-r", "--name-only", "HEAD"],
        capture_output=True, text=True, check=False,
    )
    if result.returncode != 0:
        return []
    return [f for f in result.stdout.strip().splitlines() if f]


def add(path: str) -> None:
    """Stage a file or directory for tracking."""
    _require_repo()
    _git("add", path)


def reset_staged() -> None:
    """Unstage all staged changes without touching the working tree."""
    _require_repo()
    _git("reset", check=False)


def remove_from_tracking(path: str) -> None:
    """Remove a file from tracking without deleting it locally."""
    _require_repo()
    _git("rm", "--cached", "-r", path)


def commit(message: str, skip_hooks: bool = False) -> bool:
    """Commit staged changes. Returns True if a commit was created.

    Args:
        skip_hooks: Per-invocation hook skip via -c flag. For persistent
            disable, use hooks_disable() instead.
    """
    _require_repo()
    # Stage all changes to tracked files
    _git("add", "-u", skip_hooks=skip_hooks)
    # Check if there's anything to commit
    result = _git("diff", "--cached", "--quiet", check=False, skip_hooks=skip_hooks)
    if result.returncode == 0:
        return False
    try:
        _git("commit", "-m", message, skip_hooks=skip_hooks)
    except subprocess.CalledProcessError as e:
        output = (e.stdout or "") + (e.stderr or "")
        raise DotGitError(output.strip() or "Commit failed") from None
    return True


# =========================================================================
# Remote operations
# =========================================================================


def has_remote() -> bool:
    """Check if a remote named 'origin' exists."""
    _require_repo()
    result = _git("remote", "get-url", "origin", check=False)
    return result.returncode == 0


def get_remote_url() -> str | None:
    """Get the origin remote URL, or None."""
    _require_repo()
    result = _git("remote", "get-url", "origin", check=False)
    if result.returncode != 0:
        return None
    return result.stdout.strip()


def set_remote(url: str) -> None:
    """Set or update the origin remote URL."""
    _require_repo()
    if has_remote():
        _git("remote", "set-url", "origin", url)
    else:
        _git("remote", "add", "origin", url)


def push() -> None:
    """Push to origin. Sets upstream on first push."""
    _require_repo()
    result = _git("branch", "--show-current")
    branch = result.stdout.strip() or "main"
    _git("push", "-u", "origin", branch)


def pull() -> None:
    """Pull from origin with rebase.

    Handles the 'new machine' case: if the local branch has no commits
    but the remote does, reset the local branch to match the remote and
    check out all files.
    """
    _require_repo()
    if not has_remote():
        return
    result = _git("fetch", "origin", check=False)
    if result.returncode != 0:
        return

    # Detect "new machine" state: no local commits yet
    has_local = _git("rev-parse", "HEAD", check=False).returncode == 0

    if not has_local:
        # Check if remote has a branch we can adopt
        branch_result = _git("branch", "--show-current", check=False)
        branch = (branch_result.stdout.strip() or "main")
        remote_ref = f"origin/{branch}"
        remote_exists = _git("rev-parse", remote_ref, check=False)
        if remote_exists.returncode == 0:
            _git("reset", remote_ref)
            _git("checkout", "HEAD", "--", str(get_work_tree()), check=False)
            _git("branch", f"--set-upstream-to={remote_ref}", branch,
                 check=False)
        return

    tracking = _git(
        "rev-parse", "--abbrev-ref", "--symbolic-full-name", "@{u}",
        check=False,
    )
    if tracking.returncode != 0:
        return
    _git("rebase", tracking.stdout.strip(), check=False)


def has_unpushed() -> bool:
    """Check if there are commits not pushed to origin."""
    _require_repo()
    if not has_remote():
        return True
    result = _git("log", "--oneline", "@{u}..HEAD", check=False)
    if result.returncode != 0:
        return True
    return bool(result.stdout.strip())


def git_passthrough(args: list[str], skip_safety: bool = False) -> subprocess.CompletedProcess:
    """Run an arbitrary git command against the bare repo.
    
    Args:
        skip_safety: If True, bypass the explicit store requirement check.
            Used internally by other SDK functions that have already validated
            the store.
    """
    if not skip_safety:
        require_explicit_store("git")
    _require_repo()
    return _git(*args, check=False)
