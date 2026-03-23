"""Path configuration for dotgit.

Env var overrides for every path, enabling test isolation.
Production uses XDG conventions and ~/.dotfiles.
"""

import os
from pathlib import Path


# Module-level store override, set by CLI --store or MCP store param.
_current_store: str | None = None


def set_current_store(name: str | None) -> None:
    """Set the active store for this invocation."""
    global _current_store
    _current_store = name


def get_current_store() -> str | None:
    """Get the active store name, or None for default."""
    return _current_store


def get_repo_dir() -> Path:
    """Get the bare git repo directory.

    Resolution order:
    1. DOTGIT_REPO_DIR env var (test isolation)
    2. Named store from stores.yaml (if _current_store is set)
    3. ~/.dotfiles (default)
    """
    env_path = os.getenv("DOTGIT_REPO_DIR")
    if env_path:
        return Path(env_path)
    if _current_store and _current_store != "default":
        from . import stores
        return stores.get_store_repo_dir(_current_store)
    return Path.home() / ".dotfiles"


def get_config_dir() -> Path:
    """Get the config directory for dotgit's own config.

    Respects DOTGIT_CONFIG_DIR env var, otherwise ~/.config/dotgit
    """
    env_path = os.getenv("DOTGIT_CONFIG_DIR")
    if env_path:
        return Path(env_path)
    xdg_config = os.environ.get("XDG_CONFIG_HOME", os.path.expanduser("~/.config"))
    return Path(xdg_config) / "dotgit"


def get_work_tree() -> Path:
    """Get the work tree root (home directory).

    Respects DOTGIT_WORK_TREE env var, otherwise $HOME.
    """
    env_path = os.getenv("DOTGIT_WORK_TREE")
    if env_path:
        return Path(env_path)
    return Path.home()


