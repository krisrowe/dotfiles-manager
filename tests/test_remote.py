"""Tests for remote topic derivation (no network)."""

from dotgit.sdk import config
from dotgit.sdk.remote import _topic_for_store


def test_topic_default_store():
    """Default store gets dotfiles-default topic."""
    config.set_invocation_store(None)
    assert _topic_for_store() == "dotfiles-default"


def test_topic_explicit_default():
    """Explicitly naming 'default' also gets dotfiles-default."""
    config.set_invocation_store("default")
    assert _topic_for_store() == "dotfiles-default"
    config.set_invocation_store(None)


def test_topic_named_store():
    """Named stores get dotfiles-<name> topic."""
    config.set_invocation_store("sensitive")
    assert _topic_for_store() == "dotfiles-sensitive"
    config.set_invocation_store("work")
    assert _topic_for_store() == "dotfiles-work"
    config.set_invocation_store(None)
