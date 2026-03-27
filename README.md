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
- **Safety First**: Dangerous commands require explicit store confirmation
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
# Set the active store for the current machine
dot default personal

# Track files (requires explicit --store for safety)
dot --store=personal track ~/.bashrc
dot --store=personal track ~/.config/myapp/

# Setup remote and sync (can use active store implicitly)
dot remote setup --repo-name my-dotfiles
dot sync
```

Each `dot track` commits immediately to a local bare repo (e.g. `~/.dotfiles-personal`).
`dot remote setup` creates a **private** GitHub repo and sets a
`dotfiles-personal` topic for discovery. `dot sync` pushes.

### New machine: discover and set up existing stores

```bash
# Discover available dotfiles on your GitHub account
dot remote available

# Setup a discovered store
dot --store=personal remote setup --repo-name my-dotfiles
dot default personal
dot sync
```

`remote setup` attaches to the existing repo. `sync` pulls everything down and checks out
tracked files to their original paths.

### Day-to-day: back up changes

```bash
dot sync
```

Commits any changes, pulls from GitHub, pushes to GitHub. Uses the **active store** configured for the current machine.

### Multiple stores: separate repos for different purposes

```bash
# Create a second store
dot stores create work

# Track files scoped to the store (REQUIRED flag)
dot --store=work track ~/.config/work-app/settings.conf

# Sync specifically for the work store
dot --store=work sync

# Or switch your active store and sync normally
dot default work
dot sync
```

## Commands

### Day-to-day

| Command | Description |
|---------|-------------|
| `dot track <path>` | Start tracking (Requires `--store`) |
| `dot untrack <path>` | Stop tracking (Requires `--store`) |
| `dot list` | List all tracked files in active store |
| `dot status` | Show modified files in active store |
| `dot sync` | Commit + pull + push active store |
| `dot default [NAME]` | View or set the machine's active store |

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
| `dot remote show` | Show remote URL of active store |
| `dot remote available` | Discover available stores on GitHub |

### Git hooks

Your global git hooks run on dotfile commits by default. If they interfere:

| Command | Description |
|---------|-------------|
| `dot hooks disable` | Disable hooks on current store (persistent) |
| `dot hooks reset` | Restore global hooks |
| `dot hooks show` | Show current hooks state |

### Stores

| Command | Description |
|---------|-------------|
| `dot stores create <name>` | Create a new store at `~/.dotfiles-<name>` |
| `dot stores list` | Show all stores (* = active) |

### Pass-through git

| Command | Description |
|---------|-------------|
| `dot git <args>` | Run git commands (Requires `--store`) |

```bash
dot --store=work git log --oneline -10
dot --store=personal git diff HEAD~1
```

## Multiple Stores

Manage independent bare repos from one CLI with `--store`. Each store gets
its own tracking, hooks configuration, git remote, and backup strategy.

`--store` is a top-level option. When omitted, the **active store** configured via `dot default` is used for safe commands (sync, status), while risky commands (track, git) will require an explicit flag to prevent accidental cross-contamination.

## MCP Server

The MCP server exposes the same SDK functions as the CLI. All MCP tools accept an optional `store` parameter.

### Register with Claude Code

```bash
dot mcp install claude
```

## How It Works

Each store is a bare git repo (e.g. `~/.dotfiles-work`). Your home directory is the work tree. `showUntrackedFiles = no` means git only sees files you explicitly track.

Every `dot` command translates to
`git --git-dir=~/.dotfiles-<store> --work-tree=~ <command>`.

## License

MIT
