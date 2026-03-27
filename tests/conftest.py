"""Test fixtures for dotgit.

Creates isolated temp environments via env var overrides.
Every test gets its own bare repo, work tree, and config dir.
Hooks are disabled via the SDK to prevent global hooks from interfering.
"""

import os
import subprocess
import tempfile
from pathlib import Path

import pytest


@pytest.fixture
def dotgit_env(tmp_path, monkeypatch):
    """Set up an isolated dotgit environment.

    Provides:
        - tmp bare repo for store 'home'
        - tmp work tree at tmp_path/home
        - tmp config dir at tmp_path/config
        - hooks disabled on the bare repo

    Returns a dict with the paths.
    """
    home_dir = tmp_path / "home"
    # Config dir must be under work tree so git can track it
    config_dir = home_dir / ".config" / "dotgit"

    home_dir.mkdir()
    config_dir.mkdir(parents=True)

    # We do NOT set DOTGIT_REPO_DIR here because we want stores.py 
    # to manage the path (~/.dotfiles-home).
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

    # Reset store state and initialize a named bare repo
    from dotgit.sdk import config, repo, stores
    
    # Force reset of any internal module state
    config.set_invocation_store(None)
    
    # We create a named store 'home' for tests.
    # This initializes the bare repo and sets 'home' as active in stores.yaml.
    stores.create("home")
    
    # Set the invocation context so risky commands (like track) work in tests.
    config.set_invocation_store("home")
    
    # Disable hooks so they don't interfere with test commits
    repo.hooks_disable()

    return {
        "repo_dir": Path(stores.get_store_repo_dir("home")),
        "home_dir": home_dir,
        "config_dir": config_dir,
    }
