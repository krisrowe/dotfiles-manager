"""Store management — create, list, resolve paths.

Each store is an independent bare repo at ~/.dotfiles-<name>.
The default store (~/.dotfiles) is implicit and never persisted.
Store definitions live in ~/.config/dotgit/stores.yaml.
"""

import re
from pathlib import Path

import yaml

from .config import get_config_dir
from . import repo


class StoreError(Exception):
    """Error in store operations."""


def _stores_file() -> Path:
    """Path to the stores config file."""
    return get_config_dir() / "stores.yaml"


def _read_stores() -> dict:
    """Read stores.yaml, returning empty dict if absent."""
    path = _stores_file()
    if not path.exists():
        return {}
    with open(path) as f:
        return yaml.safe_load(f) or {}


def _write_stores(data: dict) -> None:
    """Write stores.yaml, creating the config dir if needed."""
    path = _stores_file()
    path.parent.mkdir(parents=True, exist_ok=True)
    with open(path, "w") as f:
        yaml.dump(data, f, default_flow_style=False)


def _validate_name(name: str) -> None:
    """Validate a store name."""
    if name == "default":
        raise StoreError("'default' is the implicit default store and cannot be created.")
    if not re.match(r"^[a-z0-9][a-z0-9-]*$", name):
        raise StoreError(
            f"Invalid store name: '{name}'. "
            "Use lowercase letters, numbers, and hyphens."
        )


def get_store_repo_dir(name: str) -> Path:
    """Get the bare repo path for a named store.

    Reads stores.yaml to verify the store exists.
    """
    data = _read_stores()
    stores = data.get("stores", {})
    if name not in stores:
        raise StoreError(f"Store '{name}' not found. Create it with: dot stores create {name}")
    repo_path = stores[name].get("repo", "")
    return Path(repo_path).expanduser()


def create(name: str) -> dict:
    """Create a new store.

    Initializes a bare repo at ~/.dotfiles-<name> and registers
    it in stores.yaml.
    """
    _validate_name(name)

    data = _read_stores()
    store_map = data.setdefault("stores", {})

    if name in store_map:
        return {"success": True, "created": False, "message": f"Store '{name}' already exists."}

    from .config import get_work_tree
    repo_path = get_work_tree() / f".dotfiles-{name}"
    store_map[name] = {"repo": str(repo_path)}
    _write_stores(data)

    # Initialize the bare repo at the store's path.
    # Temporarily override DOTGIT_REPO_DIR so repo.init() targets it.
    import os
    old_repo_dir = os.environ.get("DOTGIT_REPO_DIR")
    os.environ["DOTGIT_REPO_DIR"] = str(repo_path)
    try:
        repo.init()
    finally:
        if old_repo_dir is not None:
            os.environ["DOTGIT_REPO_DIR"] = old_repo_dir
        else:
            os.environ.pop("DOTGIT_REPO_DIR", None)

    return {
        "success": True,
        "created": True,
        "name": name,
        "repo": str(repo_path),
    }


def list_stores() -> dict:
    """List all stores, always including default."""
    from .config import get_repo_dir as _default_repo_dir
    import os

    # Default store path (without store override)
    env_path = os.getenv("DOTGIT_REPO_DIR")
    default_path = env_path if env_path else str(Path.home() / ".dotfiles")

    result = [{"name": "default", "repo": default_path}]

    data = _read_stores()
    for name, info in data.get("stores", {}).items():
        result.append({"name": name, "repo": info.get("repo", "")})

    return {"stores": result}
