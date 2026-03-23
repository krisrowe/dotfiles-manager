# dotfiles-manager

Back up and sync your dotfiles across machines using git. No new concepts
to learn — it's just git under the hood, wrapped in a simple CLI.

Uses the [Atlassian bare repo pattern](https://www.atlassian.com/git/tutorials/dotfiles):
your config files stay where they are, git tracks them invisibly, and GitHub
keeps a versioned backup.

## Why

- **One command to back up**: `dot sync` commits and pushes everything
- **One command to set up a new machine**: `dot remote setup` + `dot sync`
- **Full version history**: Roll back any file with `dot git log`
- **No new mental model**: It's git. If you know git, you know everything
- **Works without GitHub**: Local-only mode until you're ready to push
- **Multiple stores**: Manage independent repos from one CLI with `--store`
- **AI-agent friendly**: MCP server lets Claude or other assistants manage your dotfiles

## Architecture

All business logic lives in the SDK (`dotgit/sdk/`). The CLI and MCP server
are thin interface layers — they parse arguments, call SDK functions, and
format output. No business logic in CLI or MCP.

```
dotgit/
  sdk/       ← all logic: tracking, syncing, remote setup, hooks, stores
  cli/       ← thin CLI wrapper (calls SDK, formats for terminal)
  mcp/       ← thin MCP wrapper (calls SDK, exposes as tool schema)
```

See [CONTRIBUTING.md](CONTRIBUTING.md) for architecture and testing details.

## Install

```bash
pipx install git+https://github.com/krisrowe/dotfiles-manager.git
```

This gives you two commands: `dot` (CLI) and `dot-mcp` (MCP server).

## User Journeys

### First machine: start tracking dotfiles

```bash
dot track ~/.bashrc
dot track ~/.claude/CLAUDE.md
dot track ~/.config/myapp/
dot remote setup --repo-name my-dotfiles
dot sync
```

Each `dot track` commits immediately to a local bare repo at `~/.dotfiles`.
`dot remote setup` creates a **private** GitHub repo and sets a
`dotfiles-default` topic for discovery on other machines. `dot sync` pushes.

### New machine: set up from existing GitHub repo

```bash
pipx install git+https://github.com/krisrowe/dotfiles-manager.git
dot remote setup --repo-name my-dotfiles
dot sync
```

`remote setup` finds the existing repo by name, verifies it's private,
and sets it as the remote. `sync` pulls everything down and checks out
tracked files to their original paths.

### Day-to-day: back up changes

```bash
dot sync
```

Commits any changes, pulls from GitHub, pushes to GitHub. One command does
everything.

### Multiple stores: separate repos for different purposes

```bash
# Create a second store
dot stores create work

# Track files, set up remote, sync — all scoped to the store
dot --store=work track ~/.config/work-app/settings.conf
dot --store=work remote setup --repo-name my-work-dotfiles
dot --store=work sync
```

### New machine with multiple stores

```bash
# Set up each store by name — topics let setup find the right repo
dot remote setup --repo-name my-dotfiles
dot --store=work remote setup --repo-name my-work-dotfiles
dot sync
dot --store=work sync
```

`dot remote setup` is idempotent — it creates the repo if it doesn't
exist, or attaches to it if it does. It validates that the
`dotfiles-<store-name>` topic is not duplicated across repos so there's
never ambiguity.

## Commands

### Day-to-day

| Command | Description |
|---------|-------------|
| `dot track <path>` | Start tracking a file or directory |
| `dot untrack <path>` | Stop tracking (keeps local file) |
| `dot list` | Show all tracked files |
| `dot status` | Show modified tracked files |
| `dot sync` | Commit + pull + push |

### Exclude patterns

Control what gets ignored inside tracked directories.

| Command | Description |
|---------|-------------|
| `dot exclude add <pattern>` | Add a gitignore-format pattern |
| `dot exclude remove <pattern>` | Remove a pattern |
| `dot exclude list` | Show current patterns |

### Remote management

| Command | Description |
|---------|-------------|
| `dot remote setup [--repo-name NAME]` | Create/verify private GitHub repo |
| `dot remote show` | Show remote URL |

### Git hooks

Your global git hooks run on dotfile commits by default. If they interfere:

| Command | Description |
|---------|-------------|
| `dot hooks disable` | Disable hooks on dotfiles repo (persistent) |
| `dot hooks reset` | Restore global hooks |
| `dot hooks show` | Show current hooks state |

### Stores

| Command | Description |
|---------|-------------|
| `dot stores create <name>` | Create a new store at `~/.dotfiles-<name>` |
| `dot stores list` | Show all registered stores |

### Pass-through git

| Command | Description |
|---------|-------------|
| `dot git <args>` | Run any git command against the dotfiles repo |

```bash
dot git log --oneline -10       # Recent history
dot git diff HEAD~1             # Last commit's changes
dot git blame .bashrc           # Who changed what
dot git bundle create backup.bundle --all  # Archive entire repo
```

## Multiple Stores

Manage independent bare repos from one CLI with `--store`. Each store gets
its own tracking, hooks configuration, git remote, and backup strategy.

Reasons to use multiple stores:

- **Sensitivity levels.** Different pre-commit hooks (or no hooks) and
  different backup targets for different classes of data.
- **Personas.** Work config vs. personal config, or any other role-based
  separation.
- **Backup targets.** GitHub, a self-hosted git server, a cloud drive
  bundle, or anywhere else — each store can back up independently.
- **Auditability.** Each store is independently listable
  (`dot --store=<name> list`), making it easy to review and reclassify.

See [Store Patterns](docs/store-patterns.md) for an example multi-store
setup separating config, personal data, and secrets.

`--store` is a top-level option that applies to every command. When omitted,
the default store is used — no behavior change from single-store usage.

## MCP Server

The MCP server exposes the same SDK functions as the CLI, so AI agents
have the same capabilities. All MCP tools accept an optional `store`
parameter, matching the CLI `--store` option.

### Register with Claude Code

```bash
dot mcp install claude
```

Or register for the current project only:

```bash
dot mcp install claude --scope=project
```

Or manually add to your Claude settings:

```json
{
  "mcpServers": {
    "dotgit": {
      "command": "dot-mcp"
    }
  }
}
```

| Command | Description |
|---------|-------------|
| `dot mcp install claude` | Register with Claude Code |
| `dot mcp install claude --scope=project` | Register for current project only |
| `dot mcp uninstall claude` | Unregister from Claude Code |

## How It Works

A bare git repo lives at `~/.dotfiles`. Your home directory is the work
tree. `showUntrackedFiles = no` means git only sees files you explicitly
`dot track`.

```
~/.dotfiles/    ← bare git database (no working tree of its own)
~/              ← work tree (your actual home directory)
```

Every `dot` command translates to
`git --git-dir=~/.dotfiles --work-tree=~ <command>`.

With multiple stores, each store is a separate bare repo
(`~/.dotfiles-<name>`) sharing the same `$HOME` work tree.

## Local-Only Mode

Don't want GitHub? Just skip `dot remote setup`. Everything works locally:

```bash
dot track ~/.bashrc
dot sync                # Commits locally, reports "no remote"
dot git log             # Full local history
```

Add GitHub later with `dot remote setup` — all history is preserved.

## Archiving

Export the entire repo (with full history) to a single file:

```bash
dot git bundle create ~/dotfiles-backup.bundle --all
```

Put that file on Google Drive, a USB stick, wherever.

## Development

```bash
git clone https://github.com/krisrowe/dotfiles-manager.git
cd dotfiles-manager
pip install -e ".[dev]"
pytest
```

See [CONTRIBUTING.md](CONTRIBUTING.md) for architecture and testing details.

## License

MIT
