"""Store management — create, list, resolve paths.

Each store is an independent bare repo at ~/.dotfiles-<name>.
Named stores are registered in ~/.config/dotgit/stores.yaml.
"""

import re
import os
import sys
from pathlib import Path

import yaml

from .config import get_config_dir, get_work_tree
from . import repo


class StoreError(Exception):
    """Error in store operations."""


RESERVED_NAMES = {"default", "current", "active"}


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


def get_active_store_name() -> str | None:
    """Read and validate the active store from stores.yaml."""
    data = _read_stores()
    active_name = data.get("active_store")
    
    if not active_name:
        return None
        
    # Validation: ignore setting if it's reserved or doesn't exist
    if active_name in RESERVED_NAMES:
        return None
        
    stores = data.get("stores", {})
    if active_name not in stores:
        return None
        
    return active_name


def set_active_store_name(name: str) -> None:
    """Update the active store in stores.yaml."""
    if name in RESERVED_NAMES:
        raise StoreError(f"'{name}' is a reserved name and cannot be set as the active store.")

    data = _read_stores()
    stores = data.get("stores", {})
    if name not in stores:
        raise StoreError(f"Store '{name}' not found. Create it first with: dot stores create {name}")
    
    data["active_store"] = name
    _write_stores(data)


def _validate_name(name: str) -> None:
    """Validate a store name."""
    if name in RESERVED_NAMES:
        raise StoreError(f"'{name}' is a reserved name and cannot be used for a store.")
    if not re.match(r"^[a-z0-9][a-z0-9-]*$", name):
        raise StoreError(
            f"Invalid store name: '{name}'. "
            "Use lowercase letters, numbers, and hyphens."
        )


def check_legacy_repo() -> None:
    """Check for existence of ~/.dotfiles and warn user."""
    legacy_path = Path.home() / ".dotfiles"
    if legacy_path.exists():
        print(
            f"⚠️  WARNING: Legacy unnamed store found at {legacy_path}.\n"
            "This repository is being ignored. To use it, please rename it to a named store:\n"
            f"  mv {legacy_path} ~/.dotfiles-home\n"
            "Then register it with: dot stores create home",
            file=sys.stderr
        )


def get_store_repo_dir(name: str) -> Path:
    """Get the bare repo path for a named store."""
    if name in RESERVED_NAMES:
         raise StoreError(f"'{name}' is a reserved name and does not have a repository directory.")

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

    repo_path = get_work_tree() / f".dotfiles-{name}"
    store_map[name] = {"repo": str(repo_path)}
    
    # If no valid active store is set, make this one the active one
    if not get_active_store_name():
        data["active_store"] = name

    _write_stores(data)

    # Initialize the bare repo at the store's path.
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
    """List all stores, showing which one is active."""
    check_legacy_repo()
    
    data = _read_stores()
    active_name = get_active_store_name()
    stores_list = data.get("stores", {})
    
    result = []
    for name, info in stores_list.items():
        result.append({
            "name": name, 
            "repo": info.get("repo", ""),
            "active": name == active_name
        })

    return {"stores": result}
