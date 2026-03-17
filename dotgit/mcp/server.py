"""MCP Server for dotfile management.

Thin transport layer — all logic lives in SDK.
"""

from typing import Optional

from mcp.server.fastmcp import FastMCP
from pydantic import Field

from ..sdk import sync, exclude, remote, repo

mcp = FastMCP("dotgit")


# =========================================================================
# Core tools
# =========================================================================


@mcp.tool(
    name="dot_status",
    description="""Check the current state of the dotfiles system.

START HERE when the user asks about their dotfiles, wants a backup, or
mentions anything about configuration file management.

This tool answers three questions:
1. Is the dotfiles repo initialized on this machine?
2. Are there local changes to tracked files that haven't been synced?
3. What files are currently being tracked?

INTERPRETING RESULTS:
- initialized=false → The user hasn't set up dotgit yet. Guide them through:
  first-time setup (dot_track + dot_remote_setup + dot_sync) or restore
  from existing repo (dot_restore).
- initialized=true, changes=[] → Everything is clean. If the user wants a
  backup, call dot_sync to push current state to GitHub.
- initialized=true, changes=[...] → Files have been modified since last sync.
  Call dot_sync to commit and push them.

NEXT STEPS after calling this:
- If user wants to back up: call dot_sync
- If user wants to see what's tracked: call dot_list
- If user wants to add a file: call dot_track
- If user wants to check remote: call dot_remote_show""",
)
async def dot_status() -> dict:
    return sync.get_status()


@mcp.tool(
    name="dot_list",
    description="""List all files and directories currently tracked by dotgit.

Returns paths relative to the user's home directory. Use this to:
- Show the user what's being backed up
- Verify a file was added after dot_track
- Confirm a file was removed after dot_untrack
- Audit what's in the dotfiles repo

If initialized=false, the repo hasn't been set up yet.""",
)
async def dot_list() -> dict:
    return sync.get_list()


@mcp.tool(
    name="dot_track",
    description="""Start tracking a file or directory as a managed dotfile.

This is how files get added to the dotfiles repo. Accepts an absolute path
to any file or directory under the user's home directory. Initializes the
dotfiles repo automatically on first use.

WHAT HAPPENS:
1. If repo doesn't exist yet, creates bare repo at ~/.dotfiles
2. Adds the file/directory to git tracking
3. Commits immediately with message "Track <path>"

DIRECTORIES: Tracking a directory tracks ALL files in it recursively.
To exclude specific patterns within a tracked directory, use dot_exclude_add
first (e.g., exclude '*.pyc' before tracking a config directory).

COMMON PATHS TO TRACK:
- ~/.claude/CLAUDE.md, ~/.claude/settings.json
- ~/.gemini/GEMINI.md, ~/.gemini/settings.json
- ~/.config/<app>/ directories
- ~/.bashrc, ~/.zshrc, ~/.profile
- ~/.gitconfig

AFTER TRACKING: Call dot_sync to push to GitHub. Tracking alone only
commits locally — it does not push to the remote.""",
)
async def dot_track(
    path: str = Field(description="Absolute path to file or directory to track"),
) -> dict:
    return sync.track(path)


@mcp.tool(
    name="dot_untrack",
    description="""Stop tracking a file or directory.

The local file is NOT deleted — it remains on disk exactly as-is.
Only removes it from the dotfiles git repo. The removal is committed
immediately and will be pushed to GitHub on next dot_sync.

USE WHEN:
- User no longer wants a file backed up
- A file was tracked by mistake
- A directory contains files that shouldn't be in the repo

After untracking, the file won't appear in dot_list or dot_status.""",
)
async def dot_untrack(
    path: str = Field(description="Absolute path to file or directory to stop tracking"),
) -> dict:
    return sync.untrack(path)


@mcp.tool(
    name="dot_sync",
    description="""Commit local changes and synchronize with GitHub. This is the
primary "backup" operation.

WHAT HAPPENS (in order):
1. Initializes repo if needed
2. Stages and commits any modified tracked files
3. Pulls from GitHub with rebase (gets changes from other machines)
4. Pushes to GitHub

SELF-HEALING: This command handles messy state gracefully:
- Uncommitted changes? Commits them automatically.
- Unpushed commits? Pushes them.
- No changes? Reports "already up to date."
- No remote? Skips push/pull and tells you.

WHEN TO USE:
- User says "back up my dotfiles" → call this
- User says "sync" or "push" → call this
- After dot_track to push newly tracked files to GitHub
- Periodically to keep GitHub in sync

PREREQUISITES:
- For push/pull to work, remote must be configured (dot_remote_setup)
- If no remote, sync still commits locally (useful before setting up remote)

CONFLICT HANDLING: If the pull encounters a merge conflict (extremely
rare for single-user dotfiles), sync will bail out. Tell the user to
resolve manually with 'dot git' commands:
  dot git status        — see what's conflicted
  dot git diff          — see the conflict markers
  dot git checkout --theirs <file>  — accept remote version
  dot git checkout --ours <file>    — keep local version
  dot git add <file>    — mark resolved
  dot git rebase --continue  — finish the rebase
Then run dot_sync again.""",
)
async def dot_sync(
    skip_hooks: bool = Field(
        default=False,
        description="Skip git hooks for this invocation only. Use only when the user explicitly requests it.",
    ),
) -> dict:
    return sync.sync(skip_hooks=skip_hooks)


@mcp.tool(
    name="dot_restore",
    description="""Restore dotfiles from GitHub onto a new machine.

USE WHEN: The user is on a fresh machine (or fresh OS install) and wants
to restore their dotfiles from a previously configured GitHub repo.

WHAT HAPPENS:
1. Clones the bare repo from the provided GitHub URL
2. Configures the repo (showUntrackedFiles=no, excludesFile)
3. Checks out all tracked files to their original home-relative paths

PREREQUISITES:
- dotgit must be installed (pipx install git+https://github.com/krisrowe/dotfiles-manager.git)
- SSH key or HTTPS credentials configured for GitHub
- The repo must NOT already exist locally (if it does, use dot_sync instead)

CONFLICT HANDLING: If files already exist at the target paths (common
when the OS creates default .bashrc etc.), checkout will fail. The tool
reports which files conflict. Tell the user:
  1. Review each conflicting file — decide if they want the local or repo version
  2. Move or delete conflicting files they want to replace
  3. Run: dot git checkout
  4. Then: dot sync

DO NOT call dot_restore if dot_status shows initialized=true.
Use dot_sync instead to pull changes.""",
)
async def dot_restore(
    repo_url: str = Field(
        description="GitHub repo SSH URL, e.g. git@github.com:USERNAME/personal-dotfiles.git"
    ),
) -> dict:
    return sync.restore(repo_url)


# =========================================================================
# Exclude tools
# =========================================================================


@mcp.tool(
    name="dot_exclude_add",
    description="""Add a gitignore-format pattern to the exclude list.

Excluded patterns prevent matching files from being tracked, even if
they're inside a tracked directory. Uses standard gitignore syntax.

COMMON PATTERNS:
- '*.pyc'              — Python bytecode
- '__pycache__/'       — Python cache dirs
- '*.log'              — Log files
- '.config/*/cache/'   — App cache directories
- '*.swp'              — Vim swap files

The exclude file is stored at ~/.config/dotgit/exclude and is itself
tracked by dotgit, so exclude patterns persist across machines via
dot_sync.

TIP: Add exclude patterns BEFORE tracking a directory to avoid
accidentally committing unwanted files.""",
)
async def dot_exclude_add(
    pattern: str = Field(description="Gitignore-format pattern to exclude"),
) -> dict:
    return exclude.add(pattern)


@mcp.tool(
    name="dot_exclude_remove",
    description="""Remove a pattern from the exclude list.

After removal, files matching the pattern will no longer be excluded.
They won't be automatically tracked — the user still needs to
dot_track them explicitly (showUntrackedFiles is off).""",
)
async def dot_exclude_remove(
    pattern: str = Field(description="Exact pattern string to remove (must match exactly)"),
) -> dict:
    return exclude.remove(pattern)


@mcp.tool(
    name="dot_exclude_list",
    description="""List all current exclude patterns.

Shows the active gitignore-format patterns from ~/.config/dotgit/exclude.
Comments and blank lines are filtered out.""",
)
async def dot_exclude_list() -> dict:
    return exclude.list_patterns()


# =========================================================================
# Remote tools
# =========================================================================


@mcp.tool(
    name="dot_remote_setup",
    description="""Create or verify a private GitHub repo and configure it as the remote.

FIRST-TIME SETUP: Call this after dot_track to set up the GitHub remote
before the first dot_sync. Creates a private repo on GitHub using the
gh CLI, sets the 'dotfiles' topic, and configures it as the origin remote.

IDEMPOTENT: Safe to call multiple times. If the repo already exists,
verifies it's private and updates the remote URL if needed.

SAFETY: Refuses to proceed if the GitHub repo exists but is PUBLIC.
Dotfiles should always be private since they may reference sensitive
paths or configuration.

PREREQUISITES:
- gh CLI must be installed (https://cli.github.com)
- User must be authenticated (gh auth login)

DEFAULT REPO NAME: 'personal-dotfiles'. Override with repo_name parameter.

AFTER SETUP: Call dot_sync to push tracked files to GitHub.""",
)
async def dot_remote_setup(
    repo_name: Optional[str] = Field(
        default=None,
        description="GitHub repo name. Default: 'personal-dotfiles'",
    ),
) -> dict:
    return remote.setup(repo_name)


@mcp.tool(
    name="dot_remote_show",
    description="""Show the current remote URL for the dotfiles repo.

Use to verify the remote is configured correctly, or to get the URL
for dot_restore on another machine.

If configured=false, the user needs to run dot_remote_setup first.""",
)
async def dot_remote_show() -> dict:
    return remote.show()


# =========================================================================
# Hooks tools
# =========================================================================


@mcp.tool(
    name="dot_hooks_disable",
    description="""Persistently disable git hooks on the dotfiles bare repo.

Sets core.hooksPath=/dev/null in the bare repo's git config. This
persists until dot_hooks_reset is called. Only affects the dotfiles
repo — all other git repos on the machine are unaffected.

USE WHEN: The user's global pre-commit hooks (e.g., pre-commit hooks)
interfere with dotfile commits, causing errors or slowdowns.

This is a persistent setting on the machine where it's run. Other
machines are not affected.""",
)
async def dot_hooks_disable() -> dict:
    try:
        repo.hooks_disable()
        return {"success": True, "state": "disabled"}
    except repo.DotGitError as e:
        return {"success": False, "error": str(e)}


@mcp.tool(
    name="dot_hooks_reset",
    description="""Restore global git hooks on the dotfiles repo.

Removes the core.hooksPath override, so the user's global hooks
(e.g., pre-commit hooks) will run on dotfile commits again.""",
)
async def dot_hooks_reset() -> dict:
    try:
        repo.hooks_reset()
        return {"success": True, "state": "default"}
    except repo.DotGitError as e:
        return {"success": False, "error": str(e)}


@mcp.tool(
    name="dot_hooks_show",
    description="""Show current hooks state for the dotfiles repo.

Returns one of:
- 'default' — global hooks apply (normal state)
- 'disabled' — hooks are off (dot_hooks_disable was called)
- 'custom (path)' — hooks point to a custom path""",
)
async def dot_hooks_show() -> dict:
    try:
        state = repo.hooks_status()
        return {"state": state}
    except repo.DotGitError as e:
        return {"error": str(e)}


# =========================================================================
# Git passthrough
# =========================================================================


@mcp.tool(
    name="dot_git",
    description="""Run an arbitrary git command against the dotfiles bare repo.

This is the escape hatch for advanced operations. The tool automatically
injects --git-dir and --work-tree flags so you don't need to.

COMMON USES:
- dot_git(["log", "--oneline", "-10"])  — recent commit history
- dot_git(["diff"])                     — see uncommitted changes
- dot_git(["diff", "HEAD~1"])           — see last commit's changes
- dot_git(["blame", ".claude/CLAUDE.md"]) — who changed what
- dot_git(["checkout", "--", ".bashrc"]) — discard local changes to a file
- dot_git(["status"])                   — raw git status output

CONFLICT RESOLUTION (after failed dot_sync):
- dot_git(["status"])                   — see conflicted files
- dot_git(["diff"])                     — see conflict markers
- dot_git(["checkout", "--theirs", "<file>"])  — accept remote
- dot_git(["checkout", "--ours", "<file>"])    — keep local
- dot_git(["add", "<file>"])            — mark resolved
- dot_git(["rebase", "--continue"])     — finish rebase

RESTORE CONFLICT RESOLUTION (after failed dot_restore):
- dot_git(["checkout"])                 — retry after user moved conflicting files""",
)
async def dot_git(
    args: list[str] = Field(description="Git subcommand and arguments as a list of strings"),
) -> dict:
    try:
        result = repo.git_passthrough(args)
        return {
            "returncode": result.returncode,
            "stdout": result.stdout,
            "stderr": result.stderr,
        }
    except repo.DotGitError as e:
        return {"error": str(e)}


# =========================================================================
# Entry point
# =========================================================================


def run_server():
    """Run the MCP server with stdio transport."""
    mcp.run()


if __name__ == "__main__":
    run_server()
