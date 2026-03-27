"""Path configuration for dotgit.

Env var overrides for every path, enabling test isolation.
Production uses XDG conventions and ~/.dotfiles.
"""

import os
from pathlib import Path


# Store override for the current process, set by CLI --store or MCP store param.
_invocation_store: str | None = None


class RequireExplicitStoreError(Exception):
    """Raised when a risky command is used without an explicit --store flag."""


def set_invocation_store(name: str | None) -> None:
    """Set the active store for this specific command invocation."""
    global _invocation_store
    _invocation_store = name


def get_invocation_store() -> str | None:
    """Get the store name for this invocation, or None if no flag was used."""
    return _invocation_store


def require_explicit_store(command_name: str) -> None:
    """Raise if no explicit store flag was provided for a risky command.
    
    A command is considered risky if it is NOT in the SAFE_COMMANDS whitelist.
    """
    SAFE_COMMANDS = {
        "sync",
        "status",
        "list",
        "remote_show",
        "stores_list",
        "config_get_store",
        "export",
        "default_alias"
    }

    if not _invocation_store and command_name not in SAFE_COMMANDS:
        raise RequireExplicitStoreError(
            f"'{command_name}' is a risky command and requires an explicit --store flag. "
            f"Example: dot --store=work {command_name} <args>"
        )


def get_active_store() -> str | None:
    """Get the persistently configured machine-level active store name."""
    from . import stores
    return stores.get_active_store_name()


def set_active_store(name: str) -> None:
    """Set the persistently configured machine-level active store name."""
    from . import stores
    stores.set_active_store_name(name)


def get_repo_dir() -> Path:
    """Get the bare git repo directory.

    Resolution order:
    1. DOTGIT_REPO_DIR env var (test isolation)
    2. Explicit invocation override (_invocation_store)
    3. Persistently active store (from stores.yaml)
    
    Raises:
        StoreError: If no store can be resolved.
    """
    from . import stores
    stores.check_legacy_repo()

    env_path = os.getenv("DOTGIT_REPO_DIR")
    if env_path:
        return Path(env_path)

    # 2. Explicit override (CLI --store)
    if _invocation_store:
        return stores.get_store_repo_dir(_invocation_store)

    # 3. Persistent active store
    active = get_active_store()
    if active:
        return stores.get_store_repo_dir(active)

    raise stores.StoreError(
        "No active store configured for this machine.\n"
        "To start, create a store (e.g., 'home'): dot stores create home\n"
        "Or set an existing one as active: dot default <name>"
    )


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
