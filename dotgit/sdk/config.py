"""Path configuration for dotgit.

Env var overrides for every path, enabling test isolation.
Production uses XDG conventions and ~/.dotfiles.
"""

import os
from pathlib import Path


def get_repo_dir() -> Path:
    """Get the bare git repo directory.

    Respects DOTGIT_REPO_DIR env var, otherwise ~/.dotfiles
    """
    env_path = os.getenv("DOTGIT_REPO_DIR")
    if env_path:
        return Path(env_path)
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


def get_exclude_file() -> Path:
    """Get the path to the exclude file (gitignore-format).

    This file is tracked by dotgit itself so excludes persist across machines.
    """
    return get_config_dir() / "exclude"


def get_work_tree() -> Path:
    """Get the work tree root (home directory).

    Respects DOTGIT_WORK_TREE env var, otherwise $HOME.
    """
    env_path = os.getenv("DOTGIT_WORK_TREE")
    if env_path:
        return Path(env_path)
    return Path.home()


