"""Tests for global gitignore management."""

from pathlib import Path

from dotgit.sdk import ignore


def test_init_creates_ignore_file(dotgit_env):
    """Init creates global gitignore with standard patterns."""
    result = ignore.init()
    assert result["success"]
    assert ".credentials.json" in result["added"]
    assert "client_secrets.json" in result["added"]

    ignore_file = Path(result["file"])
    assert ignore_file.exists()
    content = ignore_file.read_text()
    assert ".credentials.json" in content
    assert "client_secrets.json" in content


def test_init_idempotent(dotgit_env):
    """Running init twice doesn't duplicate patterns."""
    ignore.init()
    result = ignore.init()
    assert result["added"] == []

    ignore_file = Path(result["file"])
    content = ignore_file.read_text()
    assert content.count(".credentials.json") == 1


def test_add_pattern(dotgit_env):
    """Add a custom pattern."""
    result = ignore.add("*.secret")
    assert result["success"]
    assert result["added"]

    patterns = ignore.list_patterns()
    assert "*.secret" in patterns["patterns"]


def test_add_idempotent(dotgit_env):
    """Adding the same pattern twice is a no-op."""
    ignore.add("*.secret")
    result = ignore.add("*.secret")
    assert result["success"]
    assert not result["added"]


def test_remove_pattern(dotgit_env):
    """Remove an existing pattern."""
    ignore.add("*.secret")
    result = ignore.remove("*.secret")
    assert result["success"]
    assert result["removed"]

    patterns = ignore.list_patterns()
    assert "*.secret" not in patterns["patterns"]


def test_remove_nonexistent(dotgit_env):
    """Removing a pattern that doesn't exist fails."""
    result = ignore.remove("nonexistent")
    assert not result["success"]


def test_list_empty(dotgit_env):
    """List on empty gitignore returns no patterns."""
    result = ignore.list_patterns()
    assert result["patterns"] == []


def test_init_syncs_to_store_exclude(dotgit_env):
    """Init adds standard patterns to the store's info/exclude."""
    ignore.init()

    exclude_file = dotgit_env["repo_dir"] / "info" / "exclude"
    content = exclude_file.read_text()
    assert ".credentials.json" in content
    assert "client_secrets.json" in content


def test_add_syncs_to_store_exclude(dotgit_env):
    """Adding a pattern also adds it to store excludes."""
    ignore.add("*.secret")

    exclude_file = dotgit_env["repo_dir"] / "info" / "exclude"
    content = exclude_file.read_text()
    assert "*.secret" in content


def test_init_preserves_existing_patterns(dotgit_env):
    """Init doesn't clobber existing patterns in the ignore file."""
    home = dotgit_env["home_dir"]
    ignore_file = home / ".config" / "git" / "ignore"
    ignore_file.parent.mkdir(parents=True, exist_ok=True)
    ignore_file.write_text("*.existing\n")

    ignore.init()

    content = ignore_file.read_text()
    assert "*.existing" in content
    assert ".credentials.json" in content
