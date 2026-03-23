"""CLI for dotgit.

Thin layer over SDK — all logic lives in dotgit.sdk.
"""

import json
import sys

import click

from ..sdk import sync, exclude, remote, repo, stores
from ..sdk.config import set_current_store


@click.group()
@click.version_option(version="0.1.0")
@click.option("--store", "store_name", default=None,
              help="Target a named store instead of the default.")
def main(store_name):
    """Dotfile management backed by a bare git repo."""
    set_current_store(store_name)


# =========================================================================
# Core commands
# =========================================================================


@main.command()
@click.argument("path")
def track(path: str):
    """Start tracking a file or directory."""
    try:
        result = sync.track(path)
    except repo.DotGitError as e:
        click.echo(str(e), err=True)
        sys.exit(1)
    if not result["success"]:
        click.echo(result["error"], err=True)
        sys.exit(1)
    click.echo(f"Tracking {result['path']}")


@main.command()
@click.argument("path")
def untrack(path: str):
    """Stop tracking a file or directory (keeps local file)."""
    result = sync.untrack(path)
    if not result["success"]:
        click.echo(result["error"], err=True)
        sys.exit(1)
    click.echo(f"Untracked {result['path']} ({result['files_removed']} file(s))")


@main.command("list")
@click.option("--format", "output_format", type=click.Choice(["text", "json"]),
              default="text")
def list_files(output_format: str):
    """List all tracked files."""
    result = sync.get_list()
    if not result["initialized"]:
        click.echo("Not initialized. Run 'dot track <path>' to start.", err=True)
        sys.exit(1)
    if output_format == "json":
        click.echo(json.dumps(result, indent=2))
    else:
        if not result["files"]:
            click.echo("No files tracked.")
        else:
            for f in result["files"]:
                click.echo(f)
            click.echo(f"\n{result['count']} file(s) tracked")


@main.command()
@click.option("--format", "output_format", type=click.Choice(["text", "json"]),
              default="text")
def status(output_format: str):
    """Show modified tracked files."""
    result = sync.get_status()
    if not result["initialized"]:
        click.echo("Not initialized. Run 'dot track <path>' to start.", err=True)
        sys.exit(1)
    if output_format == "json":
        click.echo(json.dumps(result, indent=2))
    else:
        if not result["changes"]:
            click.echo("Clean — nothing to sync.")
        else:
            for c in result["changes"]:
                click.echo(f"  {c['status']:12s} {c['path']}")


@main.command("sync")
@click.option("--no-hooks", is_flag=True, default=False,
              help="Skip git hooks for this invocation only.")
def sync_cmd(no_hooks: bool):
    """Commit local changes, pull from origin, push to origin."""
    try:
        result = sync.sync(skip_hooks=no_hooks)
    except repo.DotGitError as e:
        click.echo(str(e), err=True)
        sys.exit(1)
    for action in result["actions"]:
        click.echo(f"  {action}")



# =========================================================================
# Exclude commands
# =========================================================================


@main.group("exclude")
def exclude_group():
    """Manage exclude patterns (gitignore format)."""
    pass


@exclude_group.command("add")
@click.argument("pattern")
def exclude_add(pattern: str):
    """Add an exclude pattern."""
    result = exclude.add(pattern)
    if result.get("added"):
        click.echo(f"Excluded: {pattern}")
    else:
        click.echo(result.get("message", "Already excluded"))


@exclude_group.command("remove")
@click.argument("pattern")
def exclude_remove(pattern: str):
    """Remove an exclude pattern."""
    result = exclude.remove(pattern)
    if not result["success"]:
        click.echo(result["error"], err=True)
        sys.exit(1)
    click.echo(f"Removed: {pattern}")


@exclude_group.command("list")
def exclude_list():
    """Show current exclude patterns."""
    result = exclude.list_patterns()
    if not result["patterns"]:
        click.echo("No exclude patterns configured.")
    else:
        for p in result["patterns"]:
            click.echo(f"  {p}")


# =========================================================================
# Remote commands
# =========================================================================


@main.group("remote")
def remote_group():
    """Manage GitHub remote."""
    pass


@remote_group.command("setup")
@click.option("--repo-name", default=None,
              help=f"GitHub repo name (default: {remote.DEFAULT_REPO_NAME})")
def remote_setup(repo_name: str | None):
    """Create or verify a private GitHub repo and set as origin."""
    result = remote.setup(repo_name)
    if not result["success"]:
        click.echo(result["error"], err=True)
        sys.exit(1)
    click.echo(f"Remote: {result['url']}")
    click.echo(f"Repo:   {result['repo']} (private)")


@remote_group.command("show")
def remote_show():
    """Show current remote URL."""
    result = remote.show()
    if not result["configured"]:
        click.echo(result["error"], err=True)
        sys.exit(1)
    click.echo(result["url"])


# =========================================================================
# Hooks commands
# =========================================================================


@main.group("hooks")
def hooks_group():
    """Manage git hooks for the dotfiles repo."""
    pass


@hooks_group.command("disable")
def hooks_disable():
    """Disable git hooks on the dotfiles repo (persistent)."""
    try:
        repo.hooks_disable()
        click.echo("Hooks disabled for dotfiles repo.")
    except repo.DotGitError as e:
        click.echo(str(e), err=True)
        sys.exit(1)


@hooks_group.command("reset")
def hooks_reset():
    """Restore global hooks on the dotfiles repo."""
    try:
        repo.hooks_reset()
        click.echo("Hooks reset to global defaults.")
    except repo.DotGitError as e:
        click.echo(str(e), err=True)
        sys.exit(1)


@hooks_group.command("show")
def hooks_show():
    """Show current hooks state."""
    try:
        state = repo.hooks_status()
        click.echo(f"Hooks: {state}")
    except repo.DotGitError as e:
        click.echo(str(e), err=True)
        sys.exit(1)


# =========================================================================
# MCP registration
# =========================================================================


@main.group("mcp")
def mcp_group():
    """Manage MCP server registration."""
    pass


@mcp_group.command("install")
@click.argument("target", type=click.Choice(["claude"]))
@click.option("--scope", type=click.Choice(["user", "project"]), default="user",
              help="user = ~/.claude/settings.json, project = .claude/settings.local.json")
def mcp_install(target: str, scope: str):
    """Register dot-mcp as an MCP server."""
    import json
    from pathlib import Path

    if target == "claude":
        if scope == "user":
            settings_path = Path.home() / ".claude" / "settings.json"
        else:
            settings_path = Path.cwd() / ".claude" / "settings.local.json"

        settings_path.parent.mkdir(parents=True, exist_ok=True)

        if settings_path.exists():
            with open(settings_path) as f:
                settings = json.load(f)
        else:
            settings = {}

        if "mcpServers" not in settings:
            settings["mcpServers"] = {}

        settings["mcpServers"]["dotgit"] = {
            "command": "dot-mcp",
        }

        with open(settings_path, "w") as f:
            json.dump(settings, f, indent=2)
            f.write("\n")

        click.echo(f"Registered dotgit MCP server in {settings_path}")


@mcp_group.command("uninstall")
@click.argument("target", type=click.Choice(["claude"]))
@click.option("--scope", type=click.Choice(["user", "project"]), default="user")
def mcp_uninstall(target: str, scope: str):
    """Unregister dot-mcp from an MCP server."""
    import json
    from pathlib import Path

    if target == "claude":
        if scope == "user":
            settings_path = Path.home() / ".claude" / "settings.json"
        else:
            settings_path = Path.cwd() / ".claude" / "settings.local.json"

        if not settings_path.exists():
            click.echo(f"Settings file not found: {settings_path}")
            return

        with open(settings_path) as f:
            settings = json.load(f)

        if "mcpServers" in settings and "dotgit" in settings["mcpServers"]:
            del settings["mcpServers"]["dotgit"]
            with open(settings_path, "w") as f:
                json.dump(settings, f, indent=2)
                f.write("\n")
            click.echo(f"Unregistered dotgit MCP server from {settings_path}")
        else:
            click.echo("dotgit MCP server not registered")


# =========================================================================
# Stores commands
# =========================================================================


@main.group("stores")
def stores_group():
    """Manage dotfile stores."""
    pass


@stores_group.command("create")
@click.argument("name")
def stores_create(name: str):
    """Create a new store."""
    try:
        result = stores.create(name)
    except stores.StoreError as e:
        click.echo(str(e), err=True)
        sys.exit(1)
    if result.get("created"):
        click.echo(f"Created store '{result['name']}' at {result['repo']}")
    else:
        click.echo(result.get("message", "Store already exists."))


@stores_group.command("list")
def stores_list():
    """Show all registered stores."""
    result = stores.list_stores()
    for s in result["stores"]:
        click.echo(f"  {s['name']:20s} {s['repo']}")


# =========================================================================
# Git passthrough
# =========================================================================


@main.command("git", context_settings={"ignore_unknown_options": True,
                                        "allow_extra_args": True})
@click.pass_context
def git_passthrough(ctx):
    """Run a git command against the dotfiles repo."""
    try:
        result = repo.git_passthrough(ctx.args)
    except repo.DotGitError as e:
        click.echo(str(e), err=True)
        sys.exit(1)
    if result.stdout:
        click.echo(result.stdout, nl=False)
    if result.stderr:
        click.echo(result.stderr, err=True, nl=False)
    sys.exit(result.returncode)


if __name__ == "__main__":
    main()
