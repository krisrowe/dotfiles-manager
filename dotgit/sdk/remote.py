"""GitHub remote management via gh CLI."""

import json
import subprocess

from . import repo


DEFAULT_REPO_NAME = "personal-dotfiles"
TOPIC = "dotfiles"


def setup(repo_name: str | None = None) -> dict:
    """Create or verify a private GitHub repo and set it as origin.

    Idempotent. Uses gh CLI.

    Args:
        repo_name: GitHub repo name. Defaults to 'personal-dotfiles'.
    """
    repo.init()
    name = repo_name or DEFAULT_REPO_NAME

    # Check gh is available
    if not _gh_available():
        return {"success": False, "error": "gh CLI not found. Install: https://cli.github.com"}

    # Get authenticated user
    user = _gh_user()
    if not user:
        return {"success": False, "error": "Not authenticated with gh. Run: gh auth login"}

    full_name = f"{user}/{name}"

    # Check if repo exists
    existing = _gh_repo_info(full_name)
    if existing:
        # Verify it's private
        if not existing.get("isPrivate", False):
            return {
                "success": False,
                "error": f"Repo {full_name} exists but is PUBLIC. Dotfiles must be private.",
            }
        url = existing.get("sshUrl") or existing.get("url")
    else:
        # Create private repo
        result = subprocess.run(
            ["gh", "repo", "create", name, "--private", "--description",
             "Personal dotfiles managed by dotgit"],
            capture_output=True, text=True, check=False,
        )
        if result.returncode != 0:
            return {"success": False, "error": f"Failed to create repo: {result.stderr}"}

        # Set topic
        subprocess.run(
            ["gh", "repo", "edit", full_name, "--add-topic", TOPIC],
            capture_output=True, text=True, check=False,
        )

        # Get URL
        info = _gh_repo_info(full_name)
        url = info.get("sshUrl") or info.get("url") if info else f"git@github.com:{full_name}.git"

    # Set remote on bare repo
    repo.set_remote(url)

    return {
        "success": True,
        "repo": full_name,
        "url": url,
        "private": True,
    }


def show() -> dict:
    """Show current remote info."""
    if not repo.is_initialized():
        return {"configured": False, "error": "Repo not initialized"}

    url = repo.get_remote_url()
    if not url:
        return {"configured": False, "error": "No remote configured"}

    return {"configured": True, "url": url}


def _gh_available() -> bool:
    result = subprocess.run(
        ["gh", "--version"], capture_output=True, text=True, check=False,
    )
    return result.returncode == 0


def _gh_user() -> str | None:
    result = subprocess.run(
        ["gh", "api", "user", "--jq", ".login"],
        capture_output=True, text=True, check=False,
    )
    if result.returncode != 0:
        return None
    return result.stdout.strip()


def _gh_repo_info(full_name: str) -> dict | None:
    result = subprocess.run(
        ["gh", "repo", "view", full_name, "--json",
         "name,owner,isPrivate,sshUrl,url"],
        capture_output=True, text=True, check=False,
    )
    if result.returncode != 0:
        return None
    return json.loads(result.stdout)
