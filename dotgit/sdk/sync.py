"""High-level sync operations.

Orchestrates track/untrack/sync/restore workflows using repo primitives.
"""

import subprocess
import os
import tempfile
from pathlib import Path

from .config import get_repo_dir, get_work_tree, require_explicit_store
from . import repo


def track(path: str) -> dict:
    """Start tracking a file or directory. REQUIRES explicit store.

    Initializes repo if needed. Commits immediately.
    Returns dict with tracked path info.
    """
    require_explicit_store("track")
    repo.init()

    abs_path = Path(path).expanduser().resolve()
    work_tree = get_work_tree()

    if not abs_path.exists():
        return {"success": False, "error": f"Path does not exist: {abs_path}"}

    try:
        rel_path = abs_path.relative_to(work_tree)
    except ValueError:
        return {"success": False, "error": f"Path must be under {work_tree}"}

    # Reset any leftover staged state from previous failed attempts
    repo.reset_staged()

    repo.add(str(abs_path))
    try:
        committed = repo.commit(f"Track {rel_path}")
    except repo.DotGitError:
        repo.reset_staged()
        raise
    return {
        "success": True,
        "path": str(rel_path),
        "committed": committed,
    }


def untrack(path: str) -> dict:
    """Stop tracking a file or directory. Keeps local file. REQUIRES explicit store.
    """
    require_explicit_store("untrack")
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


def get_status(include_untracked: bool = False, include_ignored: bool = False) -> dict:
    """Get status of tracked files. Safe (uses active).

    Args:
        include_untracked: If True, discover dotfiles in $HOME not tracked by ANY store.
        include_ignored: If True, show top-level hidden items ignored by the current store.
    """
    require_explicit_store("status")
    if not repo.is_initialized():
        return {"initialized": False, "changes": [], "untracked": [], "ignored": []}
    
    changes = repo.status()
    untracked = []
    ignored = []

    if include_untracked:
        untracked = _get_cross_store_untracked()
    
    if include_ignored:
        ignored = _get_ignored()

    return {
        "initialized": True, 
        "changes": changes,
        "untracked": untracked,
        "ignored": ignored
    }


def _get_ignored() -> list[str]:
    """Find specific hidden paths ignored by the current store.
    
    Summarizes to 2 levels deep for accuracy (e.g. .gemini/antigravity/).
    """
    repo_dir = get_repo_dir()
    work_tree = get_work_tree()
    pathspec = ".[a-zA-Z0-9]*"
    
    result = subprocess.run(
        ["git", f"--git-dir={repo_dir}", f"--work-tree={work_tree}", 
         "status", "--ignored", "--porcelain", "--untracked-files=normal", "--", pathspec],
        capture_output=True, text=True, check=False, cwd=work_tree
    )
    
    if result.returncode != 0:
        return []

    ignored_summary = set()
    for line in result.stdout.splitlines():
        if line.startswith("!! "):
            path = line[3:].strip().strip('"')
            ignored_summary.add(path)
            
    return sorted(list(ignored_summary))


def _get_cross_store_untracked() -> list[str]:
    """Find files in $HOME that are not tracked by any registered store.
    
    Uses Git's native core.excludesFile to inject other stores' tracked files
    as dynamic ignores, perfectly handling directory/file mismatches.
    """
    from . import stores as stores_mod
    
    work_tree = get_work_tree()
    active_repo = get_repo_dir()
    all_stores_info = stores_mod.list_stores()["stores"]
    show_all = os.getenv("DOTGIT_SHOW_ALL") == "1"
    
    pathspec = ".[a-zA-Z0-9]*"
    
    # 1. Collect all files tracked in OTHER stores
    other_tracked = []
    for s in all_stores_info:
        repo_dir = Path(s["repo"]).expanduser()
        other_tracked.append(repo_dir.name + "/") # Ignore the store's git dir itself
        
        if repo_dir.resolve() == active_repo.resolve():
            continue
            
        result = subprocess.run(
            ["git", f"--git-dir={repo_dir}", "ls-files"],
            capture_output=True, text=True, check=False
        )
        if result.returncode == 0:
            other_tracked.extend(result.stdout.splitlines())

    # 2. Write global ignores + other_tracked to a temp file to act as a dynamic gitignore
    with tempfile.NamedTemporaryFile(mode='w', delete=False) as tmp:
        # Include global ignore file if it exists so we don't lose those rules
        global_ignore = work_tree / ".config" / "git" / "ignore"
        if global_ignore.exists():
            tmp.write(global_ignore.read_text())
            tmp.write("\n")
            
        for f in other_tracked:
            tmp.write(f"/{f}\n") # Root it to the work tree
        tmp_path = tmp.name

    try:
        # 3. Use git status --porcelain, injecting the temp file as an extra exclude file
        cmd = ["git", f"--git-dir={active_repo}", f"--work-tree={work_tree}", 
               "-c", f"core.excludesFile={tmp_path}",
               "status", "--porcelain", "--untracked-files=normal"]
        
        if not show_all:
            cmd.extend(["--", pathspec])

        result = subprocess.run(
            cmd, capture_output=True, text=True, check=False, cwd=work_tree
        )
        
        if result.returncode != 0:
            return []

        truly_untracked = []
        for line in result.stdout.splitlines():
            if line.startswith("?? "):
                path = line[3:].strip().strip('"')
                truly_untracked.append(path)
        
        return sorted(truly_untracked)
    finally:
        if os.path.exists(tmp_path):
            os.remove(tmp_path)


def get_stats() -> dict:
    """Gather comprehensive statistics for the active environment."""
    from . import stores as stores_mod
    from . import ignore
    
    stats = {
        "stores": {},
        "global_ignores": 0,
        "untracked": 0,
    }
    
    # 1. Store counts
    all_stores = stores_mod.list_stores()["stores"]
    for s in all_stores:
        store_name = s["name"]
        repo_dir = Path(s["repo"]).expanduser()
        if not repo_dir.exists():
            stats["stores"][store_name] = 0
            continue
            
        result = subprocess.run(
            ["git", f"--git-dir={repo_dir}", "ls-files"],
            capture_output=True, text=True, check=False
        )
        if result.returncode == 0:
            stats["stores"][store_name] = len(result.stdout.splitlines())
        else:
            stats["stores"][store_name] = 0
            
    # 2. Global ignores count
    patterns = ignore.list_patterns().get("patterns", [])
    stats["global_ignores"] = len(patterns)
    
    # 3. Untracked count
    stats["untracked"] = len(_get_cross_store_untracked())
    
    return stats


def get_list() -> dict:
    """List all tracked files. Safe (uses active)."""
    require_explicit_store("list")
    if not repo.is_initialized():
        return {"initialized": False, "files": []}
    files = repo.list_tracked()
    return {"initialized": True, "files": files, "count": len(files)}


def sync(skip_hooks: bool = False) -> dict:
    """Self-healing sync: commit local changes, pull, push. Safe (uses active)."""
    require_explicit_store("sync")
    repo.init()

    actions = []

    changes = repo.status()
    if changes:
        committed = repo.commit(
            _auto_commit_message(changes), skip_hooks=skip_hooks,
        )
        if committed:
            actions.append(f"Committed {len(changes)} changed file(s)")

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


def export_bundle(path: str) -> dict:
    """Export the store as a git bundle file. Safe (uses active)."""
    require_explicit_store("export")
    if not repo.is_initialized():
        return {"success": False, "error": "Repo not initialized."}

    dest = Path(path).expanduser().resolve()
    if dest.is_dir():
        from .config import get_invocation_store, get_active_store
        store = get_invocation_store() or get_active_store() or "default"
        dest = dest / f"dotfiles-{store}.bundle"

    dest.parent.mkdir(parents=True, exist_ok=True)
    result = repo.git_passthrough(["bundle", "create", str(dest), "--all"], skip_safety=True)
    if result.returncode != 0:
        return {"success": False, "error": result.stderr.strip() or "Bundle creation failed."}
    return {"success": True, "path": str(dest)}


def import_bundle(path: str) -> dict:
    """Import a git bundle into the current store. REQUIRES explicit store."""
    require_explicit_store("import")
    bundle = Path(path).expanduser().resolve()
    if not bundle.exists():
        return {"success": False, "error": f"Bundle not found: {bundle}"}

    repo_dir = get_repo_dir()
    if repo.is_initialized():
        repo.git_passthrough(["fetch", str(bundle)], skip_safety=True)
        result = repo.git_passthrough(["merge", "FETCH_HEAD", "--ff-only"], skip_safety=True)
        if result.returncode != 0:
            return {"success": False, "error": "Merge failed. Resolve manually."}
        return {"success": True, "actions": ["Fetched and merged from bundle"]}

    import subprocess as sp
    sp.run(["git", "clone", "--bare", str(bundle), str(repo_dir)], capture_output=True, text=True)
    repo.init()
    repo.git_passthrough(["checkout"], skip_safety=True)
    return {"success": True, "actions": ["Imported and checked out bundle"]}


def _auto_commit_message(changes: list[dict]) -> str:
    if len(changes) == 1:
        return f"{changes[0]['status'].capitalize()} {changes[0]['path']}"
    return f"Sync {len(changes)} file(s)"
