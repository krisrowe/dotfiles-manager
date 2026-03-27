# Contributing

## Architecture

### SDK-First Design

All business logic lives in `dotgit/sdk/`. CLI and MCP are thin wrappers that call SDK functions, format output, and handle I/O. If you're writing logic in CLI or MCP, stop and move it to SDK.

- `sdk/config.py` — Path resolution with env var overrides, store resolution, and safety whitelisting.
- `sdk/repo.py` — All git operations against the bare repo.
- `sdk/sync.py` — High-level workflows: track, untrack, sync.
- `sdk/stores.py` — Store management: create, list, path resolution, active store config.
- `sdk/exclude.py` — Exclude pattern management.
- `sdk/remote.py` — GitHub remote setup and discovery via `gh` CLI.

### Command Safety

The tool divides commands into two categories to prevent accidental repository pollution:

1.  **Safe Commands**: Can use the **active store** (configured per machine via `dot default`) implicitly. Examples: `sync`, `status`, `list`.
2.  **Risky Commands**: Require an explicit `--store` flag. Examples: `track`, `untrack`, `git`, `remote setup`.

This logic is enforced at the SDK level in `sdk/config.py` via `require_explicit_store()`.

### Path Isolation via Env Vars

Every path is resolved through `config.py` using this priority:
1. Environment Variable (for test isolation)
2. Explicit Invocation Override (`--store` flag)
3. Persistently Active Store (`stores.yaml`)
4. Legacy Fallback (`~/.dotfiles`)

### SDK Primitives

- `repo._git()`: Wraps the `git` command, injecting `--git-dir` and `--work-tree`.
- `status.showUntrackedFiles = no`: Crucial setting to ensure only explicitly tracked files are visible.

## Multiple Stores

### Active Store Configuration

Each machine can have one persistently active store. This is stored in `~/.config/dotgit/stores.yaml`.

```yaml
active_store: work
stores:
  personal:
    repo: ~/.dotfiles-personal
  work:
    repo: ~/.dotfiles-work
```

### `remote setup` and Topic Discovery

`dot remote setup` attaches a local store to a GitHub repository. It:
1. Determines the topic: `dotfiles-<store>`.
2. Sets the topic on the GitHub repository.
3. Configures the remote origin.

Users can discover existing remote stores using `dot remote available`, which queries GitHub for the `dotfiles-*` topic pattern.

## Testing

Tests use the `dotgit_env` fixture for isolation. 

**Note for tests**: Because `track` and other risky commands now require an explicit store context, the `dotgit_env` fixture automatically sets the invocation store to `default` to maintain compatibility with existing test logic.

```bash
pytest           # Run all tests
pytest -v        # Verbose
```

## Adding a New Feature

1. Add SDK logic in `dotgit/sdk/`.
2. Register safe commands in the `SAFE_COMMANDS` whitelist in `sdk/config.py`.
3. Add CLI command in `dotgit/cli/main.py`.
4. Add MCP tool in `dotgit/mcp/server.py`.
5. Add tests.
