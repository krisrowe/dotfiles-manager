# Contributing

## Architecture

### SDK-First Design

All business logic lives in `dotgit/sdk/`. CLI and MCP are thin wrappers that call SDK functions, format output, and handle I/O. If you're writing logic in CLI or MCP, stop and move it to SDK.

- `sdk/config.py` — Path resolution with env var overrides, store resolution
- `sdk/repo.py` — All git operations against the bare repo
- `sdk/sync.py` — High-level workflows: track, untrack, sync
- `sdk/stores.py` — Store management: create, list, path resolution
- `sdk/exclude.py` — Exclude pattern management
- `sdk/remote.py` — GitHub remote setup via `gh` CLI

### Bare Repo Under the Hood

The tool wraps the [Atlassian bare repo pattern](https://www.atlassian.com/git/tutorials/dotfiles). Every git command goes through `repo._git()` which injects `--git-dir=<repo> --work-tree=~`. Nothing else in the codebase calls git directly.

Key git config on each bare repo:
- `status.showUntrackedFiles = no` — only explicitly tracked files are visible
- `core.hooksPath = /dev/null` — set when hooks are disabled

### Path Isolation via Env Vars

Every path is resolved through a `get_*()` function in `config.py` that checks an env var first. Tests override these for full isolation. Production uses defaults.

| Env Var | Default | Purpose |
|---------|---------|---------|
| `DOTGIT_REPO_DIR` | `~/.dotfiles` | Bare repo (default store) |
| `DOTGIT_WORK_TREE` | `$HOME` | Work tree |
| `DOTGIT_CONFIG_DIR` | `~/.config/dotgit` | Config file location |

### Self-Healing Sync

`dot sync` handles any combination of dirty state without error:
1. Uncommitted changes → stage + commit automatically
2. Unpushed commits → push
3. Remote changes → pull with rebase
4. No remote → local commit only, skip push/pull

### Bail Out on Conflicts

When `dot sync` hits a merge conflict, the tool reports what happened and stops. It tells the user to resolve via `dot git` commands. No automatic merge UI, no backup-and-retry.

### Hooks: Two Mechanisms

- **Persistent**: `dot hooks disable` sets `core.hooksPath=/dev/null` in the bare repo config. Survives across commands until `dot hooks reset`.
- **Per-invocation**: `dot sync --no-hooks` passes `-c core.hooksPath=/dev/null` to git for that command only.

Hooks are per-store — each bare repo has its own `core.hooksPath` config. No additional mechanism needed for multi-store.

Tests use the persistent mechanism via the fixture.

### MCP Descriptions as Documentation

The MCP tool descriptions in `server.py` are the primary interface for AI agents. They must be complete, self-contained guides — telling the agent where to start, what to check, what to do next, and how to handle errors. Keep them rich and workflow-oriented.

## Multiple Stores

### Design Decisions

**No active store.** There is no "switch" command or ambient state tracking which store is active. The default store is always the default. `--store=<name>` is a top-level CLI option (and MCP parameter) that explicitly targets a named store. This avoids silent misrouting — you always know which store a command targets by reading the command.

**Path convention.** Store paths are derived from the name: `~/.dotfiles-<name>`. Users don't choose paths. The default store is `~/.dotfiles`.

**Minimal configuration footprint.** Today there is no XDG configuration for this tool. The only file that existed in `~/.config/dotgit/` was an exclude file (gitignore-format patterns for filtering tracked directories), but it was functionally per-repo state and has been relocated into each bare repo's `info/exclude` (git's built-in mechanism). A single-store user has no XDG config at all.

Store definitions live in `~/.config/dotgit/stores.yaml`, created only when a non-default store is created. The default store is implicit and never needs an entry.

```yaml
stores:
  sensitive:
    repo: ~/.dotfiles-sensitive
  work:
    repo: ~/.dotfiles-work
```

### `remote setup` Idempotency and Topic Validation

`dot remote setup` (with or without `--store`) is idempotent. It:

1. Determines the correct topic for the store (`dotfiles-default` for the
   default store, `dotfiles-<name>` for named stores).
2. Checks whether that topic already exists on any repo in the user's
   GitHub account.
3. If the topic is on the correct repo: confirms valid state, exits
   successfully.
4. If the topic is on a different repo: **errors** — a duplicate topic
   would make topic-based setup ambiguous. The user must resolve the conflict
   manually (remove the topic from the wrong repo).
5. If no repo has the topic: creates the repo (if needed) and applies the
   topic.

This validation runs even when no work would otherwise be done. `remote setup` only exits successfully if the GitHub account is in a valid state where topic-based restore would work unambiguously.

### Implementation

The core change is in `config.py`: `get_repo_dir()` accepts an optional store name, looks up the path in `stores.yaml` if provided, and falls back to `~/.dotfiles` when not provided or when no config file exists. The top-level `--store` option in `cli/main.py` sets the store name in a context that `get_repo_dir()` reads, so no individual command needs modification. Everything upstream calls `get_repo_dir()` and automatically becomes store-aware.

Store management functions (create, list) live in `dotgit/sdk/stores.py`.

## Testing

Tests use the `dotgit_env` fixture which creates isolated temp directories, overrides env vars (`HOME`, `GIT_CONFIG_GLOBAL`, `DOTGIT_*`), initializes the bare repo, and disables hooks — all using the same SDK functions the production code uses. No mocks.

Multi-store tests extend this by:

- Setting `DOTGIT_CONFIG_DIR` to a temp dir so `stores.yaml` is isolated
- Creating multiple bare repos in temp dirs
- Exercising full end-to-end flows: create store, track files in different
  stores, sync each independently, verify files are in the correct repos

No mocking of git, filesystem, or subprocess calls. The tests run real git commands against real (temporary) bare repos.

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
