"""Tests for multi-store functionality."""

from pathlib import Path

import pytest

from dotgit.sdk import config, repo, stores, sync, exclude


@pytest.fixture
def store_env(dotgit_env):
    """Extend dotgit_env with store isolation."""
    # dotgit_env already sets DOTGIT_CONFIG_DIR to a temp dir,
    # so stores.yaml will be created there.
    return dotgit_env


# =========================================================================
# Store creation and listing
# =========================================================================


def test_list_stores_default_only(store_env):
    """With no stores.yaml, only the default store is listed."""
    result = stores.list_stores()
    assert len(result["stores"]) == 1
    assert result["stores"][0]["name"] == "default"


def test_create_store(store_env):
    """Creating a store initializes a bare repo and registers it."""
    result = stores.create("work")
    assert result["success"]
    assert result["created"]

    repo_path = Path(result["repo"])
    assert (repo_path / "HEAD").exists()

    listed = stores.list_stores()
    names = [s["name"] for s in listed["stores"]]
    assert "default" in names
    assert "work" in names


def test_create_store_idempotent(store_env):
    """Creating the same store twice doesn't error."""
    stores.create("work")
    result = stores.create("work")
    assert result["success"]
    assert not result["created"]


def test_create_store_default_rejected(store_env):
    """Cannot create a store named 'default'."""
    with pytest.raises(stores.StoreError, match="default"):
        stores.create("default")


def test_create_store_invalid_name(store_env):
    """Store names must be lowercase alphanumeric with hyphens."""
    with pytest.raises(stores.StoreError, match="Invalid"):
        stores.create("My Store!")


def test_create_store_name_must_start_with_alphanumeric(store_env):
    """Store name cannot start with a hyphen."""
    with pytest.raises(stores.StoreError, match="Invalid"):
        stores.create("-bad")


# =========================================================================
# Store resolution via config.get_repo_dir()
# =========================================================================


def test_get_repo_dir_default(store_env):
    """Without --store, get_repo_dir returns the default path."""
    config.set_current_store(None)
    # With DOTGIT_REPO_DIR set (by fixture), env var wins
    assert config.get_repo_dir() == store_env["repo_dir"]


def test_get_repo_dir_named_store(store_env, monkeypatch):
    """With --store=work, get_repo_dir returns the work store path."""
    stores.create("work")

    # Remove the env var override so store resolution kicks in
    monkeypatch.delenv("DOTGIT_REPO_DIR")
    config.set_current_store("work")

    repo_dir = config.get_repo_dir()
    assert "dotfiles-work" in str(repo_dir)

    # Cleanup
    config.set_current_store(None)


def test_env_var_overrides_store(store_env):
    """DOTGIT_REPO_DIR env var takes priority over --store."""
    stores.create("work")
    config.set_current_store("work")

    # Env var is set by fixture — it should still win
    assert config.get_repo_dir() == store_env["repo_dir"]

    config.set_current_store(None)


def test_nonexistent_store_errors(store_env, monkeypatch):
    """Targeting a store that doesn't exist raises an error."""
    monkeypatch.delenv("DOTGIT_REPO_DIR")
    config.set_current_store("nonexistent")

    with pytest.raises(stores.StoreError, match="not found"):
        config.get_repo_dir()

    config.set_current_store(None)


# =========================================================================
# Cross-store isolation
# =========================================================================


def test_track_in_different_stores_isolated(store_env, monkeypatch):
    """Files tracked in one store don't appear in another."""
    home = store_env["home_dir"]

    # Track a file in the default store
    file_a = home / ".bashrc"
    file_a.write_text("# default config")
    sync.track(str(file_a))

    default_files = repo.list_tracked()
    assert any(".bashrc" in f for f in default_files)

    # Create and switch to a new store
    # We need to set up a real second store with its own bare repo
    work_repo_dir = store_env["repo_dir"].parent / "work-repo"
    stores.create("work")

    # Override repo dir to the work store's repo
    # (since DOTGIT_REPO_DIR overrides store resolution, we point it there)
    monkeypatch.setenv("DOTGIT_REPO_DIR", str(work_repo_dir))
    repo.init()
    repo.hooks_disable()

    # Track a different file in the work store
    file_b = home / ".workrc"
    file_b.write_text("# work config")
    sync.track(str(file_b))

    work_files = repo.list_tracked()
    assert any(".workrc" in f for f in work_files)
    assert not any(".bashrc" in f for f in work_files)

    # Switch back to default and verify
    monkeypatch.setenv("DOTGIT_REPO_DIR", str(store_env["repo_dir"]))
    default_files = repo.list_tracked()
    assert any(".bashrc" in f for f in default_files)
    assert not any(".workrc" in f for f in default_files)


def test_hooks_per_store_isolated(store_env, monkeypatch):
    """Hook settings in one store don't affect another."""
    # Default store has hooks disabled by fixture
    assert repo.hooks_status() == "disabled"

    # Create a second store
    work_repo_dir = store_env["repo_dir"].parent / "work-repo"
    stores.create("work")

    monkeypatch.setenv("DOTGIT_REPO_DIR", str(work_repo_dir))
    repo.init()
    # Don't disable hooks on this one

    repo.hooks_reset()
    assert repo.hooks_status() == "default"

    # Verify default store still has hooks disabled
    monkeypatch.setenv("DOTGIT_REPO_DIR", str(store_env["repo_dir"]))
    assert repo.hooks_status() == "disabled"


def test_exclude_per_store_isolated(store_env, monkeypatch):
    """Exclude patterns in one store don't affect another."""
    # Add pattern to default store
    exclude.add("*.log")
    result = exclude.list_patterns()
    assert "*.log" in result["patterns"]

    # Create and switch to work store
    work_repo_dir = store_env["repo_dir"].parent / "work-repo"
    stores.create("work")

    monkeypatch.setenv("DOTGIT_REPO_DIR", str(work_repo_dir))
    repo.init()

    # Work store should not have the pattern
    result = exclude.list_patterns()
    assert "*.log" not in result["patterns"]


# =========================================================================
# Exclude file migration
# =========================================================================


def test_exclude_file_lives_in_repo(store_env):
    """Exclude file is inside the bare repo's info/ directory."""
    exclude_path = repo.get_exclude_file()
    assert "info" in str(exclude_path)
    assert str(store_env["repo_dir"]) in str(exclude_path)


def test_exclude_migration_from_config_dir(store_env):
    """Old config-dir exclude file is migrated to info/exclude."""
    # Write an old-style exclude file
    old_exclude = store_env["config_dir"] / "exclude"
    old_exclude.write_text("*.log\n*.tmp\n")

    # Clear the current info/exclude
    new_exclude = store_env["repo_dir"] / "info" / "exclude"
    new_exclude.write_text("# header\n")

    # Re-init triggers migration
    repo.init()

    assert not old_exclude.exists()
    content = new_exclude.read_text()
    assert "*.log" in content
    assert "*.tmp" in content


def test_exclude_migration_skips_empty_file(store_env):
    """Old exclude with only comments is deleted without migrating content."""
    old_exclude = store_env["config_dir"] / "exclude"
    old_exclude.write_text("# just a comment\n")

    new_exclude = store_env["repo_dir"] / "info" / "exclude"
    original_content = new_exclude.read_text()

    repo.init()

    assert not old_exclude.exists()
    assert new_exclude.read_text() == original_content
