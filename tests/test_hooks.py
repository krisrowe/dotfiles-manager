"""Tests for hooks management."""

from dotgit.sdk import repo


def test_hooks_disabled_by_fixture(dotgit_env):
    """Test fixture disables hooks by default."""
    assert repo.hooks_status() == "disabled"


def test_hooks_reset(dotgit_env):
    """Resetting hooks restores default state."""
    repo.hooks_reset()
    assert repo.hooks_status() == "default"


def test_hooks_disable_after_reset(dotgit_env):
    """Can disable hooks again after reset."""
    repo.hooks_reset()
    repo.hooks_disable()
    assert repo.hooks_status() == "disabled"
