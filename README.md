# dotfiles-manager

Back up and sync your dotfiles across machines using git. No new concepts to learn — it's just git under the hood, wrapped in a simple CLI.

Uses the [Atlassian bare repo pattern](https://www.atlassian.com/git/tutorials/dotfiles): your config files stay where they are, git tracks them invisibly, and GitHub keeps a versioned backup.

## Why

- **One command to back up**: `dot sync` commits and pushes everything
- **One command to restore**: `dot restore <url>` on a new machine
- **Full version history**: Roll back any file with `dot git log`
- **No new mental model**: It's git. If you know git, you know everything
- **Works without GitHub**: Local-only mode until you're ready to push
- **AI-agent friendly**: MCP server lets Claude or other assistants manage your dotfiles

## Install

```bash
pipx install git+https://github.com/krisrowe/dotfiles-manager.git
```

This gives you two commands: `dot` (CLI) and `dot-mcp` (MCP server).

## Quick Start

### 1. Track your config files

```bash
dot track ~/.bashrc
dot track ~/.claude/CLAUDE.md
dot track ~/.config/myapp/
```

Each `dot track` commits immediately to a local bare repo at `~/.dotfiles`.

### 2. (Optional) Set up GitHub backup

```bash
dot remote setup
```

Creates a **private** repo on GitHub (default name: `personal-dotfiles`) using the `gh` CLI.

### 3. Sync

```bash
dot sync
```

Commits any changes, pulls from GitHub, pushes to GitHub. One command does everything.

## Restore on a New Machine

```bash
pipx install git+https://github.com/krisrowe/dotfiles-manager.git
dot restore git@github.com:YOUR_USERNAME/personal-dotfiles.git
```

All tracked files are checked out to their original paths. If files already exist at those paths, `dot restore` reports the conflicts and tells you how to resolve them.

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

### MCP server

Register as an MCP server for AI assistant integration:

| Command | Description |
|---------|-------------|
| `dot mcp install claude` | Register with Claude Code |
| `dot mcp install claude --scope=project` | Register for current project only |
| `dot mcp uninstall claude` | Unregister from Claude Code |

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

### Advanced

| Command | Description |
|---------|-------------|
| `dot git <args>` | Run any git command against the dotfiles repo |

Examples:
```bash
dot git log --oneline -10       # Recent history
dot git diff HEAD~1             # Last commit's changes
dot git blame .bashrc           # Who changed what
dot git bundle create backup.bundle --all  # Archive entire repo to a file
```

## How It Works

A bare git repo lives at `~/.dotfiles`. Your home directory is the work tree. `showUntrackedFiles = no` means git only sees files you explicitly `dot track`.

```
~/.dotfiles/          ← bare git database (no working tree of its own)
~/.config/dotgit/exclude  ← gitignore-format excludes (tracked by the repo)
~/                    ← work tree (your actual home directory)
```

Every `dot` command translates to `git --git-dir=~/.dotfiles --work-tree=~ <command>`.

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

Put that file on Google Drive, a USB stick, wherever. Restore from it:

```bash
dot restore ~/dotfiles-backup.bundle
```

## Environment Variables

For testing and advanced use. Production uses the defaults.

| Variable | Default | Description |
|----------|---------|-------------|
| `DOTGIT_REPO_DIR` | `~/.dotfiles` | Bare repo location |
| `DOTGIT_WORK_TREE` | `$HOME` | Work tree root |
| `DOTGIT_CONFIG_DIR` | `~/.config/dotgit` | Config/exclude file location |

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
