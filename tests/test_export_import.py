"""Tests for export/import bundle operations."""

from pathlib import Path

from dotgit.sdk import config, repo, sync, stores


def test_export_to_directory(dotgit_env):
    """Export to a directory auto-names the bundle file."""
    home = dotgit_env["home_dir"]
    test_file = home / ".bashrc"
    test_file.write_text("export PATH=/usr/bin")
    sync.track(str(test_file))

    export_dir = dotgit_env["home_dir"] / "backups"
    export_dir.mkdir()

    result = sync.export_bundle(str(export_dir))
    assert result["success"]
    assert result["path"].endswith("dotfiles.bundle")
    assert Path(result["path"]).exists()


def test_export_to_explicit_path(dotgit_env):
    """Export to an explicit file path uses that path."""
    home = dotgit_env["home_dir"]
    test_file = home / ".bashrc"
    test_file.write_text("export PATH=/usr/bin")
    sync.track(str(test_file))

    bundle_path = dotgit_env["home_dir"] / "backups" / "my-backup.bundle"
    result = sync.export_bundle(str(bundle_path))
    assert result["success"]
    assert result["path"].endswith("my-backup.bundle")
    assert bundle_path.exists()


def test_export_named_store(dotgit_env, monkeypatch):
    """Export a named store auto-names with the store name."""
    home = dotgit_env["home_dir"]

    # Create and populate a named store
    stores.create("work")
    work_repo = Path(stores.get_store_repo_dir("work"))
    monkeypatch.setenv("DOTGIT_REPO_DIR", str(work_repo))
    repo.init()
    repo.hooks_disable()

    test_file = home / ".workrc"
    test_file.write_text("work config")
    sync.track(str(test_file))

    config.set_current_store("work")

    export_dir = home / "backups"
    export_dir.mkdir()
    result = sync.export_bundle(str(export_dir))
    assert result["success"]
    assert "dotfiles-work.bundle" in result["path"]

    config.set_current_store(None)
    monkeypatch.setenv("DOTGIT_REPO_DIR", str(dotgit_env["repo_dir"]))


def test_export_not_initialized(dotgit_env, monkeypatch, tmp_path):
    """Export on an uninitialized repo fails."""
    empty_repo = tmp_path / "empty-repo"
    monkeypatch.setenv("DOTGIT_REPO_DIR", str(empty_repo))

    result = sync.export_bundle(str(tmp_path))
    assert not result["success"]
    assert "not initialized" in result["error"].lower()

    monkeypatch.setenv("DOTGIT_REPO_DIR", str(dotgit_env["repo_dir"]))


def test_import_into_new_store(dotgit_env, monkeypatch, tmp_path):
    """Import a bundle into a fresh (uninitialized) store."""
    home = dotgit_env["home_dir"]

    # Create a file and export from default store
    test_file = home / ".bashrc"
    test_file.write_text("original config")
    sync.track(str(test_file))

    bundle_path = tmp_path / "backup.bundle"
    result = sync.export_bundle(str(bundle_path))
    assert result["success"]

    # Import into a new bare repo
    new_repo = tmp_path / "new-repo"
    monkeypatch.setenv("DOTGIT_REPO_DIR", str(new_repo))

    result = sync.import_bundle(str(bundle_path))
    assert result["success"]

    # Verify files are in the new repo
    tracked = repo.list_tracked()
    assert any(".bashrc" in f for f in tracked)

    monkeypatch.setenv("DOTGIT_REPO_DIR", str(dotgit_env["repo_dir"]))


def test_import_same_bundle_twice(dotgit_env, monkeypatch, tmp_path):
    """Importing the same bundle into an already-initialized store succeeds."""
    home = dotgit_env["home_dir"]

    # Track a file and export
    test_file = home / ".bashrc"
    test_file.write_text("config")
    sync.track(str(test_file))

    bundle_path = tmp_path / "backup.bundle"
    sync.export_bundle(str(bundle_path))

    # Import into a new repo
    new_repo = tmp_path / "new-repo"
    monkeypatch.setenv("DOTGIT_REPO_DIR", str(new_repo))
    result = sync.import_bundle(str(bundle_path))
    assert result["success"]

    # Import the same bundle again — should succeed (nothing new)
    result = sync.import_bundle(str(bundle_path))
    assert result["success"]

    monkeypatch.setenv("DOTGIT_REPO_DIR", str(dotgit_env["repo_dir"]))


def test_import_nonexistent_bundle(dotgit_env):
    """Import a bundle that doesn't exist fails."""
    result = sync.import_bundle("/tmp/does-not-exist.bundle")
    assert not result["success"]
    assert "not found" in result["error"].lower()


def test_export_then_import_roundtrip(dotgit_env, monkeypatch, tmp_path):
    """Full roundtrip: track files, export, import elsewhere, verify."""
    home = dotgit_env["home_dir"]

    # Track multiple files
    file_a = home / ".bashrc"
    file_b = home / ".vimrc"
    file_a.write_text("bash config")
    file_b.write_text("vim config")
    sync.track(str(file_a))
    sync.track(str(file_b))

    # Export
    bundle_path = tmp_path / "roundtrip.bundle"
    sync.export_bundle(str(bundle_path))

    # Import into a fresh repo
    new_repo = tmp_path / "restored"
    monkeypatch.setenv("DOTGIT_REPO_DIR", str(new_repo))

    result = sync.import_bundle(str(bundle_path))
    assert result["success"]

    tracked = repo.list_tracked()
    assert any(".bashrc" in f for f in tracked)
    assert any(".vimrc" in f for f in tracked)

    monkeypatch.setenv("DOTGIT_REPO_DIR", str(dotgit_env["repo_dir"]))
