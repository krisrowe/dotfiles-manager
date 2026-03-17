"""Tests for track/untrack/list operations."""

from dotgit.sdk import sync, repo


def test_track_new_file(dotgit_env):
    """Tracking a file adds it to the repo and commits."""
    home = dotgit_env["home_dir"]
    test_file = home / ".config" / "test" / "settings.json"
    test_file.parent.mkdir(parents=True)
    test_file.write_text('{"key": "value"}')

    result = sync.track(str(test_file))
    assert result["success"]
    assert result["committed"]
    assert ".config/test/settings.json" in result["path"]

    tracked = repo.list_tracked()
    assert any("settings.json" in f for f in tracked)


def test_track_directory(dotgit_env):
    """Tracking a directory adds all its files."""
    home = dotgit_env["home_dir"]
    config_dir = home / ".config" / "myapp"
    config_dir.mkdir(parents=True)
    (config_dir / "a.txt").write_text("a")
    (config_dir / "b.txt").write_text("b")

    result = sync.track(str(config_dir))
    assert result["success"]

    tracked = repo.list_tracked()
    assert any("a.txt" in f for f in tracked)
    assert any("b.txt" in f for f in tracked)


def test_track_nonexistent_path(dotgit_env):
    """Tracking a nonexistent path fails gracefully."""
    home = dotgit_env["home_dir"]
    result = sync.track(str(home / "does-not-exist"))
    assert not result["success"]
    assert "does not exist" in result["error"]


def test_untrack_keeps_local_file(dotgit_env):
    """Untracking removes from repo but keeps the local file."""
    home = dotgit_env["home_dir"]
    test_file = home / ".bashrc"
    test_file.write_text("export PATH=/usr/bin")

    sync.track(str(test_file))
    result = sync.untrack(str(test_file))

    assert result["success"]
    assert test_file.exists()  # Still on disk
    assert ".bashrc" not in repo.list_tracked()


def test_untrack_not_tracked(dotgit_env):
    """Untracking a file that isn't tracked fails gracefully."""
    home = dotgit_env["home_dir"]
    test_file = home / ".bashrc"
    test_file.write_text("export PATH=/usr/bin")

    result = sync.untrack(str(test_file))
    assert not result["success"]
    assert "Not tracked" in result["error"]


def test_list_empty(dotgit_env):
    """List on a fresh repo shows only dotgit's own config files."""
    result = sync.get_list()
    assert result["initialized"]


def test_list_after_tracking(dotgit_env):
    """List shows tracked files."""
    home = dotgit_env["home_dir"]
    test_file = home / ".vimrc"
    test_file.write_text("set number")

    sync.track(str(test_file))
    result = sync.get_list()
    assert any(".vimrc" in f for f in result["files"])
