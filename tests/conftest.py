"""Test fixtures for dotgit.

Creates isolated temp environments via env var overrides.
Every test gets its own bare repo, work tree, and config dir.
Hooks are disabled via the SDK to prevent global hooks from interfering.
"""

import os
import subprocess
import tempfile

import pytest


@pytest.fixture
def dotgit_env(tmp_path, monkeypatch):
    """Set up an isolated dotgit environment.

    Provides:
        - tmp bare repo at tmp_path/repo
        - tmp work tree at tmp_path/home
        - tmp config dir at tmp_path/config
        - tmp backup dir at tmp_path/backup
        - hooks disabled on the bare repo

    Returns a dict with the paths.
    """
    repo_dir = tmp_path / "repo"
    home_dir = tmp_path / "home"
    # Config dir must be under work tree so git can track it
    config_dir = home_dir / ".config" / "dotgit"

    home_dir.mkdir()
    config_dir.mkdir(parents=True)

    monkeypatch.setenv("DOTGIT_REPO_DIR", str(repo_dir))
    monkeypatch.setenv("DOTGIT_WORK_TREE", str(home_dir))
    monkeypatch.setenv("DOTGIT_CONFIG_DIR", str(config_dir))

    # Isolate from user's real git config (HOME controls XDG paths too)
    monkeypatch.setenv("HOME", str(home_dir))
    monkeypatch.setenv("GIT_CONFIG_GLOBAL", str(home_dir / ".gitconfig"))

    # Configure git user for commits in this test
    monkeypatch.setenv("GIT_AUTHOR_NAME", "Test")
    monkeypatch.setenv("GIT_AUTHOR_EMAIL", "test@example.com")
    monkeypatch.setenv("GIT_COMMITTER_NAME", "Test")
    monkeypatch.setenv("GIT_COMMITTER_EMAIL", "test@example.com")

    # Reset store state and initialize the bare repo
    from dotgit.sdk import config, repo
    config.set_current_store(None)
    repo.init()
    repo.hooks_disable()

    return {
        "repo_dir": repo_dir,
        "home_dir": home_dir,
        "config_dir": config_dir,
    }
