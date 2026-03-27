import pytest
import sys
from pathlib import Path
from dotgit.sdk import stores, config, sync, repo

def test_reserved_names_rejected(dotgit_env):
    """Reserved names cannot be used as store names."""
    for name in ["default", "current", "active"]:
        with pytest.raises(stores.StoreError, match=f"'{name}' is a reserved name"):
            stores.create(name)

def test_risky_command_requires_explicit_store(dotgit_env, monkeypatch):
    """Risky commands fail without an explicit --store flag."""
    # Reset to no active store
    monkeypatch.setattr(config, "_invocation_store", None)
    # Ensure no active store in config
    stores._write_stores({}) 

    with pytest.raises(config.RequireExplicitStoreError, match="risky command"):
        sync.track("somefile")

def test_safe_command_fails_without_active_store(dotgit_env, monkeypatch):
    """Safe commands fail if no active store is configured."""
    monkeypatch.setattr(config, "_invocation_store", None)
    stores._write_stores({}) 

    with pytest.raises(stores.StoreError, match="No active store configured"):
        sync.get_status()

def test_legacy_dotfiles_warning(dotgit_env, capsys):
    """Presence of ~/.dotfiles triggers a warning to stderr."""
    legacy_path = Path.home() / ".dotfiles"
    legacy_path.mkdir()
    
    stores.check_legacy_repo()
    
    captured = capsys.readouterr()
    assert "WARNING: Legacy unnamed store found" in captured.err
    assert "mv" in captured.err

def test_invalid_active_store_in_yaml_is_ignored(dotgit_env, monkeypatch):
    """If stores.yaml has a nonexistent active_store, it's treated as None."""
    stores._write_stores({
        "active_store": "nonexistent",
        "stores": {"work": {"repo": "/tmp/repo"}}
    })
    
    assert config.get_active_store() is None

def test_reserved_active_store_in_yaml_is_ignored(dotgit_env):
    """If stores.yaml has a reserved name as active_store, it's treated as None."""
    stores._write_stores({
        "active_store": "default",
        "stores": {"work": {"repo": "/tmp/repo"}}
    })
    
    assert config.get_active_store() is None

def test_first_store_becomes_active_automatically(dotgit_env, monkeypatch):
    """The first store created becomes the active one if none exists."""
    # Ensure starting clean
    stores._write_stores({})
    monkeypatch.setattr(config, "_invocation_store", None)
    
    stores.create("home")
    assert config.get_active_store() == "home"

def test_explicit_store_overrides_active(dotgit_env):
    """--store flag overrides the persistent active store."""
    stores.create("home")
    stores.create("work")
    stores.set_active_store_name("home")
    
    config.set_invocation_store("work")
    assert config.get_repo_dir().name == ".dotfiles-work"
