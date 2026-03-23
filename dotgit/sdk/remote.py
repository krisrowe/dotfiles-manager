"""GitHub remote management via gh CLI."""

import json
import subprocess

from . import repo


DEFAULT_REPO_NAME = "personal-dotfiles"


def _topic_for_store() -> str:
    """Get the GitHub topic for the current store."""
    from .config import get_current_store
    store = get_current_store()
    if not store or store == "default":
        return "dotfiles-default"
    return f"dotfiles-{store}"


def setup(repo_name: str | None = None) -> dict:
    """Create or verify a private GitHub repo and set it as origin.

    Idempotent. Uses gh CLI.

    Validates that the store's topic (dotfiles-<store-name>) is not
    already on a different repo, then ensures it is set on the target
    repo. Exits successfully only if the GitHub account is in a valid
    state for topic-based restore.

    Args:
        repo_name: GitHub repo name. Defaults to 'personal-dotfiles'.
    """
    repo.init()

    # Check gh is available
    if not _gh_available():
        return {"success": False, "error": "gh CLI not found. Install: https://cli.github.com"}

    # Get authenticated user
    user = _gh_user()
    if not user:
        return {"success": False, "error": "Not authenticated with gh. Run: gh auth login"}

    topic = _topic_for_store()

    # Discovery: if no repo name given, look for an existing repo with the topic
    if not repo_name:
        existing_repos = _find_repos_with_topic(topic, user)
        if len(existing_repos) == 1:
            name = existing_repos[0].get("nameWithOwner", "").split("/")[-1]
        elif len(existing_repos) > 1:
            names = [r.get("nameWithOwner", "") for r in existing_repos]
            return {
                "success": False,
                "error": (
                    f"Multiple repos have topic '{topic}': {', '.join(names)}. "
                    f"Remove the topic from all but one, or pass --repo-name explicitly."
                ),
            }
        else:
            name = DEFAULT_REPO_NAME
    else:
        name = repo_name

    full_name = f"{user}/{name}"

    # Validate topic uniqueness before doing anything else
    topic_error = _validate_topic(topic, full_name, user)
    if topic_error:
        return {"success": False, "error": topic_error}

    # Check if repo exists
    existing = _gh_repo_info(full_name)
    if existing:
        # Verify it's private
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
             "Personal dotfiles managed by dotgit"],
            capture_output=True, text=True, check=False,
        )
        if result.returncode != 0:
            return {"success": False, "error": f"Failed to create repo: {result.stderr}"}

        # Get URL
        info = _gh_repo_info(full_name)
        url = _preferred_url(info) if info else f"https://github.com/{full_name}.git"

    # Ensure topic is set on the repo (idempotent)
    subprocess.run(
        ["gh", "repo", "edit", full_name, "--add-topic", topic],
        capture_output=True, text=True, check=False,
    )

    # Set remote on bare repo
    repo.set_remote(url)

    return {
        "success": True,
        "repo": full_name,
        "url": url,
        "topic": topic,
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


def _preferred_url(repo_info: dict) -> str:
    """Pick SSH or HTTPS URL based on gh auth git-protocol."""
    result = subprocess.run(
        ["gh", "auth", "status", "--show-token"],
        capture_output=True, text=True, check=False,
    )
    # If gh is configured for HTTPS (default), prefer HTTPS URL
    if "git_protocol: ssh" not in result.stderr.lower():
        return repo_info.get("url", "") + ".git" if repo_info.get("url") else repo_info.get("sshUrl", "")
    return repo_info.get("sshUrl") or repo_info.get("url", "")


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


def _validate_topic(topic: str, target_repo: str, user: str) -> str | None:
    """Check that no other repo has this topic.

    Returns an error message if the topic is on a different repo,
    or None if everything is valid.
    """
    repos_with_topic = _find_repos_with_topic(topic, user)

    for r in repos_with_topic:
        repo_full = r.get("nameWithOwner", "")
        if repo_full != target_repo:
            return (
                f"Topic '{topic}' is already on repo '{repo_full}'. "
                f"This would make topic-based restore ambiguous. "
                f"Remove the topic from '{repo_full}' first: "
                f"gh repo edit {repo_full} --remove-topic {topic}"
            )

    return None


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


def _gh_repo_info(full_name: str) -> dict | None:
    result = subprocess.run(
        ["gh", "repo", "view", full_name, "--json",
         "name,owner,isPrivate,sshUrl,url"],
        capture_output=True, text=True, check=False,
    )
    if result.returncode != 0:
        return None
    return json.loads(result.stdout)
