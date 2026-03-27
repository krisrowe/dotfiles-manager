"""GitHub remote management via gh CLI."""

import json
import subprocess

from . import repo


DEFAULT_REPO_NAME = "personal-dotfiles"


def _topic_for_store() -> str:
    """Get the GitHub topic for the current store."""
    from .config import get_invocation_store, get_active_store
    store = get_invocation_store() or get_active_store()
    if not store or store == "default":
        return "dotfiles-default"
    return f"dotfiles-{store}"


def discover_remote_stores() -> list[dict]:
    """Find all repos owned by user with any dotfiles-* topic.
    
    This operates strictly on GitHub state, independent of local configuration.
    """
    if not _gh_available():
        raise Exception("gh CLI not found.")
    
    user = _gh_user()
    if not user:
        raise Exception("Not authenticated with gh. Run: gh auth login")

    # Search for any repo with a topic starting with 'dotfiles-'
    result = subprocess.run(
        ["gh", "repo", "list", user, "--json", "nameWithOwner,repositoryTopics", "--limit", "100"],
        capture_output=True, text=True, check=False,
    )
    if result.returncode != 0:
        return []
    
    all_repos = json.loads(result.stdout) or []
    discovered = []
    
    for r in all_repos:
        # repositoryTopics can be null or a list of {"name": "topic"}
        topics_raw = r.get("repositoryTopics") or []
        for t_obj in topics_raw:
            t = t_obj.get("name", "")
            if t.startswith("dotfiles-"):
                store_name = t.replace("dotfiles-", "")
                discovered.append({
                    "repo": r["nameWithOwner"],
                    "store": store_name,
                    "topic": t
                })
    
    return discovered


def setup(repo_name: str | None = None) -> dict:
    """Explicitly link the current store to a GitHub repository.
    
    No longer performs 'magic' discovery by topic. Requires user to be informed.
    Sets the dotfiles-<store> topic on the target repo.
    """
    from .config import require_explicit_store
    require_explicit_store("remote_setup")
    
    repo.init()

    if not _gh_available():
        return {"success": False, "error": "gh CLI not found. Install: https://cli.github.com"}

    user = _gh_user()
    if not user:
        return {"success": False, "error": "Not authenticated with gh. Run: gh auth login"}

    topic = _topic_for_store()

    # Use default name if none provided
    name = repo_name or DEFAULT_REPO_NAME
    full_name = f"{user}/{name}"

    # Check if repo exists
    existing = _gh_repo_info(full_name)
    if existing:
        if not existing.get("isPrivate", False):
            return {
                "success": False,
                "error": f"Repo {full_name} exists but is PUBLIC. Dotfiles must be private.",
            }
        url = _preferred_url(existing)
    else:
        # Create private repo
        result = subprocess.run(
            ["gh", "repo", "create", name, "--private", "--description",
             f"Dotfiles store managed by dotgit"],
            capture_output=True, text=True, check=False,
        )
        if result.returncode != 0:
            return {"success": False, "error": f"Failed to create repo: {result.stderr}"}
        
        info = _gh_repo_info(full_name)
        url = _preferred_url(info) if info else f"https://github.com/{full_name}.git"

    # Set topic (idempotent)
    subprocess.run(
        ["gh", "repo", "edit", full_name, "--add-topic", topic],
        capture_output=True, text=True, check=False,
    )

    # Set remote
    repo.set_remote(url)

    return {
        "success": True,
        "repo": full_name,
        "url": url,
        "topic": topic,
    }


def show() -> dict:
    """Show current remote info."""
    from .config import require_explicit_store
    require_explicit_store("remote_show")
    
    if not repo.is_initialized():
        return {"configured": False, "error": "Repo not initialized"}

    url = repo.get_remote_url()
    if not url:
        return {"configured": False, "error": "No remote configured"}

    return {"configured": True, "url": url}


def _preferred_url(repo_info: dict) -> str:
    """Pick SSH or HTTPS URL based on gh auth git-protocol."""
    result = subprocess.run(
        ["gh", "auth", "status"],
        capture_output=True, text=True, check=False,
    )
    if "git_protocol: ssh" in result.stderr.lower() or "git_protocol: ssh" in result.stdout.lower():
        return repo_info.get("sshUrl") or repo_info.get("url", "")
    return repo_info.get("url", "") + ".git" if repo_info.get("url") else repo_info.get("sshUrl", "")


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


def _find_repos_with_topic(topic: str, user: str) -> list[dict]:
    """Find all repos owned by user with a specific topic."""
    result = subprocess.run(
        ["gh", "repo", "list", user, "--topic", topic, "--json",
         "nameWithOwner,sshUrl"],
        capture_output=True, text=True, check=False,
    )
    if result.returncode != 0:
        return []
    return json.loads(result.stdout) or []
