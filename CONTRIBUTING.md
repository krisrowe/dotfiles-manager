# Contributing

## Architecture

### SDK-First Design

All business logic lives in `dotgit/sdk/`. CLI and MCP are thin wrappers that call SDK functions, format output, and handle I/O. If you're writing logic in CLI or MCP, stop and move it to SDK.

- `sdk/config.py` — Path resolution with env var overrides
- `sdk/repo.py` — All git operations against the bare repo
- `sdk/sync.py` — High-level workflows: track, untrack, sync, restore
- `sdk/exclude.py` — Exclude pattern management
- `sdk/remote.py` — GitHub remote setup via `gh` CLI

### Bare Repo Under the Hood

The tool wraps the [Atlassian bare repo pattern](https://www.atlassian.com/git/tutorials/dotfiles). Every git command goes through `repo._git()` which injects `--git-dir=~/.dotfiles --work-tree=~`. Nothing else in the codebase calls git directly.

Key git config on the bare repo:
- `status.showUntrackedFiles = no` — only explicitly tracked files are visible
- `core.excludesFile = ~/.config/dotgit/exclude` — managed, tracked exclude file
- `core.hooksPath = /dev/null` — set when hooks are disabled

### Path Isolation via Env Vars

Every path is resolved through a `get_*()` function in `config.py` that checks an env var first. Tests override these for full isolation. Production uses defaults.

| Env Var | Default | Purpose |
|---------|---------|---------|
| `DOTGIT_REPO_DIR` | `~/.dotfiles` | Bare repo |
| `DOTGIT_WORK_TREE` | `$HOME` | Work tree |
| `DOTGIT_CONFIG_DIR` | `~/.config/dotgit` | Config + exclude file |

### Self-Healing Sync

`dot sync` handles any combination of dirty state without error:
1. Uncommitted changes → stage + commit automatically
2. Unpushed commits → push
3. Remote changes → pull with rebase
4. No remote → local commit only, skip push/pull

### Bail Out on Conflicts

When `dot sync` hits a merge conflict or `dot restore` finds existing files, the tool reports what happened and stops. It tells the user to resolve via `dot git` commands. No automatic merge UI, no backup-and-retry.

### Hooks: Two Mechanisms

- **Persistent**: `dot hooks disable` sets `core.hooksPath=/dev/null` in the bare repo config. Survives across commands until `dot hooks reset`.
- **Per-invocation**: `dot sync --no-hooks` passes `-c core.hooksPath=/dev/null` to git for that command only.

Tests use the persistent mechanism via the fixture.

### MCP Descriptions as Documentation

The MCP tool descriptions in `server.py` are the primary interface for AI agents. They must be complete, self-contained guides — telling the agent where to start, what to check, what to do next, and how to handle errors. Keep them rich and workflow-oriented.

## Testing

Tests use the `dotgit_env` fixture which creates isolated temp directories, overrides env vars (`HOME`, `GIT_CONFIG_GLOBAL`, `DOTGIT_*`), initializes the bare repo, and disables hooks — all using the same SDK functions the production code uses. No mocks.

```bash
pytest           # Run all tests
pytest -v        # Verbose
pytest -x        # Stop on first failure
```

## Adding a New Feature

1. Add SDK logic in `dotgit/sdk/`
2. Add CLI command in `dotgit/cli/main.py` (thin)
3. Add MCP tool in `dotgit/mcp/server.py` (thin, rich description)
4. Add tests using `dotgit_env` fixture
