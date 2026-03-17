"""Tests for status and sync operations."""

from dotgit.sdk import sync, repo


def test_status_clean(dotgit_env):
    """Status on a clean repo shows no changes."""
    result = sync.get_status()
    assert result["initialized"]
    assert result["changes"] == []


def test_status_after_modification(dotgit_env):
    """Status shows modified tracked files."""
    home = dotgit_env["home_dir"]
    test_file = home / ".bashrc"
    test_file.write_text("original")
    sync.track(str(test_file))

    test_file.write_text("modified")
    result = sync.get_status()
    assert any(c["path"].endswith(".bashrc") for c in result["changes"])


def test_sync_commits_and_reports(dotgit_env):
    """Sync commits dirty tracked files."""
    home = dotgit_env["home_dir"]
    test_file = home / ".bashrc"
    test_file.write_text("original")
    sync.track(str(test_file))

    test_file.write_text("modified")
    result = sync.sync()
    assert result["success"]
    assert any("Committed" in a for a in result["actions"])

    # Status should be clean after sync
    status = sync.get_status()
    assert status["changes"] == []


def test_sync_no_changes(dotgit_env):
    """Sync with nothing to do is a no-op."""
    result = sync.sync()
    assert result["success"]
    assert any("No remote" in a for a in result["actions"])


def test_sync_skip_hooks(dotgit_env):
    """Sync with skip_hooks works (per-invocation override)."""
    home = dotgit_env["home_dir"]
    test_file = home / ".profile"
    test_file.write_text("export FOO=bar")
    sync.track(str(test_file))

    test_file.write_text("export FOO=baz")
    result = sync.sync(skip_hooks=True)
    assert result["success"]
