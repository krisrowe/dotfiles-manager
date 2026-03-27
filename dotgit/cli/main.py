"""CLI for dotgit.

Thin layer over SDK — all logic lives in dotgit.sdk.
"""

import json
import sys

import click

from ..sdk import sync, exclude, remote, repo, stores, ignore
from ..sdk.config import set_invocation_store, get_active_store, set_active_store


@click.group()
@click.version_option(version="0.1.0")
@click.option("--store", "store_name", default=None,
              help="Target a named store instead of the active one.")
def main(store_name):
    """Dotfile management backed by a bare git repo."""
    set_invocation_store(store_name)


def _require_explicit_store(ctx, command_name: str):
    """Enforce --store requirement for risky commands."""
    from ..sdk.config import get_invocation_store
    if not get_invocation_store():
        click.echo(f"Error: '{command_name}' is a risky command and requires an explicit --store flag.", err=True)
        click.echo(f"Example: dot --store=work {command_name} <args>", err=True)
        ctx.exit(1)


# =========================================================================
# Core commands
# =========================================================================


@main.command()
@click.argument("path")
@click.pass_context
def track(ctx, path: str):
    """Start tracking a file or directory. REQUIRES --store."""
    _require_explicit_store(ctx, "track")
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
@click.pass_context
def untrack(ctx, path: str):
    """Stop tracking a file or directory. REQUIRES --store."""
    _require_explicit_store(ctx, "untrack")
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
    from ..sdk.config import get_current_store, get_active_store
    active = get_current_store() or get_active_store() or "default"
    
    result = sync.get_status()
    if not result["initialized"]:
        click.echo(f"Store '{active}' not initialized. Run 'dot track <path>' to start.", err=True)
        sys.exit(1)
    if output_format == "json":
        click.echo(json.dumps(result, indent=2))
    else:
        click.echo(f"Store: {active}")
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


@main.command("export")
@click.argument("path")
def export_cmd(path: str):
    """Export the store as a git bundle file."""
    result = sync.export_bundle(path)
    if not result["success"]:
        click.echo(result["error"], err=True)
        sys.exit(1)
    click.echo(f"Exported to {result['path']}")


@main.command("import")
@click.argument("path")
def import_cmd(path: str):
    """Import a git bundle into the current store."""
    result = sync.import_bundle(path)
    if not result["success"]:
        click.echo(result["error"], err=True)
        sys.exit(1)
    for action in result["actions"]:
        click.echo(f"  {action}")


# =========================================================================
# Default / Alias command
# =========================================================================


@main.command("default")
@click.argument("name", required=False)
def default_alias(name: str | None):
    """View or set the active store. Alias for 'dot stores set-default'."""
    if name:
        try:
            set_active_store(name)
            click.echo(f"Active store set to: {name}")
        except stores.StoreError as e:
            click.echo(str(e), err=True)
            sys.exit(1)
    else:
        active = get_active_store()
        if active:
            click.echo(active)
        else:
            click.echo("default")


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


@remote_group.command("available")
def remote_available():
    """List remote dotfiles repositories discovered by GitHub topics."""
    try:
        results = remote.discover_remotes()
        if not results:
            click.echo("No remote dotfiles repositories discovered.")
            return
        
        click.echo(f"{'Repository':40s} {'Store/Topic'}")
        click.echo("-" * 60)
        for r in results:
            click.echo(f"{r['repo']:40s} {r['store']}")
    except Exception as e:
        click.echo(f"Error discovering remotes: {str(e)}", err=True)
        sys.exit(1)


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
              help="user = user-level config, project = project-level config")
def mcp_install(target: str, scope: str):
    """Register dot-mcp as an MCP server."""
    import subprocess

    if target == "claude":
        cmd = ["claude", "mcp", "add", "-s", scope, "dotgit", "--", "dot-mcp"]
        result = subprocess.run(cmd, capture_output=True, text=True, check=False)
        if result.returncode != 0:
            click.echo(f"Failed: {result.stderr.strip()}", err=True)
            raise SystemExit(1)
        click.echo(result.stdout.strip() or f"Registered dotgit MCP server ({scope} scope)")


@mcp_group.command("uninstall")
@click.argument("target", type=click.Choice(["claude"]))
@click.option("--scope", type=click.Choice(["user", "project"]), default="user")
def mcp_uninstall(target: str, scope: str):
    """Unregister dot-mcp from an MCP server."""
    import subprocess

    if target == "claude":
        cmd = ["claude", "mcp", "remove", "-s", scope, "dotgit"]
        result = subprocess.run(cmd, capture_output=True, text=True, check=False)
        if result.returncode != 0:
            click.echo(f"Failed: {result.stderr.strip()}", err=True)
            raise SystemExit(1)
        click.echo(result.stdout.strip() or f"Unregistered dotgit MCP server ({scope} scope)")


# =========================================================================
# Ignore commands
# =========================================================================


@main.group("ignore")
def ignore_group():
    """Manage global gitignore patterns."""
    pass


@ignore_group.command("init")
def ignore_init():
    """Ensure global gitignore has standard patterns and is tracked."""
    result = ignore.init()
    if result["added"]:
        for p in result["added"]:
            click.echo(f"  Added: {p}")
    else:
        click.echo("  All standard patterns already present.")
    click.echo(f"  File: {result['file']}")


@ignore_group.command("add")
@click.argument("pattern")
def ignore_add(pattern: str):
    """Add a pattern to the global gitignore."""
    result = ignore.add(pattern)
    if result.get("added"):
        click.echo(f"Ignored: {pattern}")
    else:
        click.echo(result.get("message", "Already ignored."))


@ignore_group.command("remove")
@click.argument("pattern")
def ignore_remove(pattern: str):
    """Remove a pattern from the global gitignore."""
    result = ignore.remove(pattern)
    if not result["success"]:
        click.echo(result["error"], err=True)
        sys.exit(1)
    click.echo(f"Removed: {pattern}")


@ignore_group.command("list")
def ignore_list():
    """Show current global gitignore patterns."""
    result = ignore.list_patterns()
    if not result["patterns"]:
        click.echo("No global gitignore patterns.")
    else:
        for p in result["patterns"]:
            click.echo(f"  {p}")


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
        if result.get("name") == get_active_store():
            click.echo(f"Automatically set '{result['name']}' as the active store.")
    else:
        click.echo(result.get("message", "Store already exists."))


@stores_group.command("set-default")
@click.argument("name")
def stores_set_default(name: str):
    """Set the active store for commands used without --store."""
    try:
        set_active_store(name)
        click.echo(f"Active store set to: {name}")
    except stores.StoreError as e:
        click.echo(str(e), err=True)
        sys.exit(1)


@stores_group.command("list")
def stores_list():
    """Show all registered stores. Active store is marked with *."""
    result = stores.list_stores()
    for s in result["stores"]:
        marker = "*" if s.get("active") else " "
        click.echo(f"{marker} {s['name']:20s} {s['repo']}")


# =========================================================================
# Git passthrough
# =========================================================================


@main.command("git", context_settings={"ignore_unknown_options": True,
                                        "allow_extra_args": True})
@click.pass_context
def git_passthrough(ctx):
    """Run a git command against the dotfiles repo. REQUIRES --store."""
    _require_explicit_store(ctx, "git")
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
