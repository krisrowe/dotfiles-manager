import os
import re
from pathlib import Path

import pytest

from dotgit.sdk import stores, config, sync, repo, exclude


# =========================================================================
# Store creation and listing
# =========================================================================


def test_list_stores_default_only(dotgit_env):
    """With no stores.yaml, only the default store is listed."""
    result = stores.list_stores()
    assert len(result["stores"]) == 1
    assert result["stores"][0]["name"] == "home"


def test_create_store(dotgit_env):
    """Creating a store initializes a bare repo and registers it."""
    result = stores.create("work")
    assert result["success"]
    assert result["created"]

    repo_path = Path(result["repo"])
    assert (repo_path / "HEAD").exists()

    listed = stores.list_stores()
    names = [s["name"] for s in listed["stores"]]
    assert "home" in names
    assert "work" in names


def test_create_store_idempotent(dotgit_env):
    """Creating the same store twice doesn't error."""
    stores.create("work")
    result = stores.create("work")
    assert result["success"]
    assert not result["created"]


def test_create_store_default_rejected(dotgit_env):
    """Cannot create a store named 'default'."""
    with pytest.raises(stores.StoreError, match="reserved"):
        stores.create("default")


def test_create_store_invalid_name(dotgit_env):
    """Store names must be lowercase alphanumeric with hyphens."""
    with pytest.raises(stores.StoreError, match="Invalid"):
        stores.create("My Store!")


def test_create_store_name_must_start_with_alphanumeric(dotgit_env):
    """Store name cannot start with a hyphen."""
    with pytest.raises(stores.StoreError, match="Invalid"):
        stores.create("-bad")


def test_create_store_uppercase_rejected(dotgit_env):
    """Store names must be lowercase."""
    with pytest.raises(stores.StoreError, match="Invalid"):
        stores.create("MyStore")


def test_create_store_numbers_ok(dotgit_env):
    """Numeric store names are valid."""
    result = stores.create("store2")
    assert result["success"]
    assert result["created"]


def test_create_store_hyphens_ok(dotgit_env):
    """Hyphens in the middle of store names are valid."""
    result = stores.create("my-extras")
    assert result["success"]
    assert result["created"]


# =========================================================================
# Store resolution via config.get_repo_dir()
# =========================================================================


def test_get_repo_dir_home(dotgit_env):
    """Without --store, get_repo_dir returns the default path."""
    config.set_invocation_store(None)
    # With DOTGIT_REPO_DIR set (by fixture), env var wins
    assert config.get_repo_dir() == dotgit_env["repo_dir"]


def test_get_repo_dir_named_store(dotgit_env, monkeypatch):
    """With --store=work, get_repo_dir returns the work store path."""
    stores.create("work")

    # Remove the env var override so store resolution kicks in
    monkeypatch.delenv("DOTGIT_REPO_DIR", raising=False)
    config.set_invocation_store("work")

    repo_dir = config.get_repo_dir()
    assert "dotfiles-work" in str(repo_dir)

    # Cleanup
    config.set_invocation_store(None)


def test_env_var_overrides_store(dotgit_env, monkeypatch):
    """DOTGIT_REPO_DIR env var takes priority over --store."""
    stores.create("work")
    config.set_invocation_store("work")
    
    # Force set an env var
    monkeypatch.setenv("DOTGIT_REPO_DIR", "/tmp/forced-repo")

    # Env var should win
    assert str(config.get_repo_dir()) == "/tmp/forced-repo"

    config.set_invocation_store(None)


def test_nonexistent_store_errors(dotgit_env, monkeypatch):
    """Targeting a store that doesn't exist raises an error."""
    monkeypatch.delenv("DOTGIT_REPO_DIR", raising=False)
    config.set_invocation_store("nonexistent")

    with pytest.raises(stores.StoreError, match="not found"):
        config.get_repo_dir()

    config.set_invocation_store(None)


# =========================================================================
# Cross-store isolation
# =========================================================================


def test_track_in_different_stores_isolated(dotgit_env, monkeypatch):
    """Files tracked in one store don't appear in another."""
    home = dotgit_env["home_dir"]

    # Track a file in the home store
    file_a = home / ".bashrc"
    file_a.write_text("# home config")
    sync.track(str(file_a))

    home_files = repo.list_tracked()
    assert any(".bashrc" in f for f in home_files)

    # Create and switch to a new store
    stores.create("work")
    config.set_invocation_store("work")
    
    # Track a different file in the work store
    file_b = home / ".workrc"
    file_b.write_text("# work config")
    sync.track(str(file_b))

    work_files = repo.list_tracked()
    assert any(".workrc" in f for f in work_files)
    assert not any(".bashrc" in f for f in work_files)

    # Switch back to home and verify
    config.set_invocation_store("home")
    home_files = repo.list_tracked()
    assert any(".bashrc" in f for f in home_files)
    assert not any(".workrc" in f for f in home_files)


def test_hooks_per_store_isolated(dotgit_env, monkeypatch):
    """Hook settings in one store don't affect another."""
    # Home store has hooks disabled by fixture
    assert repo.hooks_status() == "disabled"

    # Create a second store
    stores.create("work")
    config.set_invocation_store("work")
    repo.hooks_reset()
    assert repo.hooks_status() == "default"

    # Verify home store still has hooks disabled
    config.set_invocation_store("home")
    assert repo.hooks_status() == "disabled"


def test_exclude_per_store_isolated(dotgit_env, monkeypatch):
    """Exclude patterns in one store don't affect another."""
    # Add pattern to home store
    exclude.add("*.log")
    result = exclude.list_patterns()
    assert "*.log" in result["patterns"]

    # Create and switch to work store
    stores.create("work")
    config.set_invocation_store("work")

    # Work store should not have the pattern
    result = exclude.list_patterns()
    assert "*.log" not in result["patterns"]


# =========================================================================
# Exclude file migration
# =========================================================================


def test_exclude_file_lives_in_repo(dotgit_env):
    """Exclude file is inside the bare repo's info/ directory."""
    exclude_path = repo.get_exclude_file()
    assert "info" in str(exclude_path)
    assert str(dotgit_env["repo_dir"]) in str(exclude_path)


def test_exclude_migration_from_config_dir(dotgit_env):
    """Old config-dir exclude file is migrated to info/exclude."""
    # Write an old-style exclude file
    old_exclude = dotgit_env["config_dir"] / "exclude"
    old_exclude.write_text("*.log\n*.tmp\n")

    # Clear the current info/exclude
    new_exclude = dotgit_env["repo_dir"] / "info" / "exclude"
    new_exclude.write_text("# header\n")

    # Re-init triggers migration
    repo.init()

    assert not old_exclude.exists()
    content = new_exclude.read_text()
    assert "*.log" in content
    assert "*.tmp" in content


def test_sync_per_store_isolated(dotgit_env, monkeypatch):
    """Syncing one store doesn't affect another."""
    home = dotgit_env["home_dir"]

    # Track and modify a file in home store
    file_a = home / ".bashrc"
    file_a.write_text("home config")
    sync.track(str(file_a))
    file_a.write_text("modified home")

    # Create work store, track a different file
    stores.create("work")
    config.set_invocation_store("work")

    file_b = home / ".workrc"
    file_b.write_text("work config")
    sync.track(str(file_b))
    file_b.write_text("modified work")

    # Sync work store
    result = sync.sync()
    assert result["success"]
    assert any("Committed" in a for a in result["actions"])

    # home store should still have uncommitted changes
    config.set_invocation_store("home")
    status = sync.get_status()
    assert any(c["path"].endswith(".bashrc") for c in status["changes"])


def test_exclude_migration_skips_empty_file(dotgit_env):
    """Old exclude with only comments is deleted without migrating content."""
    old_exclude = dotgit_env["config_dir"] / "exclude"
    old_exclude.write_text("# just a comment\n")

    new_exclude = dotgit_env["repo_dir"] / "info" / "exclude"
    original_content = new_exclude.read_text()

    repo.init()

    assert not old_exclude.exists()
    assert new_exclude.read_text() == original_content
