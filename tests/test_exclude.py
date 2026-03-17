"""Tests for exclude pattern management."""

from dotgit.sdk import exclude


def test_add_pattern(dotgit_env):
    """Adding a pattern writes it to the exclude file."""
    result = exclude.add("*.pyc")
    assert result["success"]
    assert result["added"]

    patterns = exclude.list_patterns()
    assert "*.pyc" in patterns["patterns"]


def test_add_duplicate(dotgit_env):
    """Adding the same pattern twice is a no-op."""
    exclude.add("*.pyc")
    result = exclude.add("*.pyc")
    assert result["success"]
    assert not result["added"]


def test_remove_pattern(dotgit_env):
    """Removing a pattern removes it from the file."""
    exclude.add("*.log")
    result = exclude.remove("*.log")
    assert result["success"]

    patterns = exclude.list_patterns()
    assert "*.log" not in patterns["patterns"]


def test_remove_nonexistent(dotgit_env):
    """Removing a pattern that doesn't exist fails gracefully."""
    result = exclude.remove("*.nope")
    assert not result["success"]


def test_list_empty(dotgit_env):
    """Listing patterns on fresh setup returns empty (or just comments)."""
    patterns = exclude.list_patterns()
    assert isinstance(patterns["patterns"], list)
