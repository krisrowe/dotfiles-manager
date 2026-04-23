# Contributing

## Design Principles: Exclude / Ignore

The exclude system controls what `dot status` shows — which untracked or
modified paths surface as needing attention and which are silently ignored.

#### Strategy: Promote for Privacy

Unlike V1, which avoided tracking ignore patterns to prevent leaking machine
state, V2 embraces **Store Promotion**.

1.  **Version Everything:** The global ignore file (`~/.config/git/ignore`)
    should be tracked in a dotfiles store to ensure it is portable across
    machines.

2.  **Sensitivity Alignment:** Users should track their ignore file in a
    store that matches its sensitivity:
    *   **`work` / `home`**: For general ignores (e.g. `.DS_Store`, `node_modules`).
    *   **`personal` / `secrets`**: If the ignore file contains patterns
        that reveal sensitive paths or private projects, promote it to a
        higher-tier store.

3.  **Git-Native Hierarchy:**
    *   **Global (`~/.config/git/ignore`)**: Portable patterns that apply
        to all stores. Managed via `dot ignore`.
    *   **Local (`.git/info/exclude`)**: Machine-specific or store-specific
        noise that should never be portable. Managed via `dot exclude`.

4.  **No Logic Fan-out:** The tool no longer duplicates global patterns into
    every store's internals. Since all stores share `$HOME` as a work tree,
    they naturally respect the global gitignore path.

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
- `status.showUntrackedFiles = no`: Crucial setting to ensure only explicitly tracked files are visible in raw git. The `dot status` command overrides this dynamically.

## Lay of the Land (V2 Discovery Philosophy)

The "V2" architecture provides a summarized view of the home directory using native Git optimizations.

1.  **Fast by Default:** `dot status` defaults to showing modified tracked files and **hidden** untracked files (`.*`) at the root of the work tree.
    *   **Performance:** ~0.1s on a machine with 30GB+ of hidden data.
    *   **Logic:** Uses a pathspec filter (`.[a-zA-Z0-9]*`) to prevent Git from even attempting to scan massive non-hidden directories (like `Library/` or `Desktop/`).

2.  **Explicit Discovery:** The `--ignored` flag enables Git's full discovery engine. 
    *   **Performance:** ~2s on a workstation with 32GB of hidden data (primarily `.gemini/` and `.cache/`). This is a significant improvement over unfiltered scans (which take ~13s+).
    *   **Summarized view:** Uses `--untracked-files=normal` to keep output readable; directories are summarized as single entries unless only specific sub-paths are ignored.

3.  **Cross-Store Awareness:** The untracked list automatically filters out files managed by **any other** registered store.

### How to Piece Together the State

| View | Command | Best For |
| :--- | :--- | :--- |
| **Tracked** | `dot list` | Auditing exactly what is being backed up. |
| **Changes** | `dot status` | Seeing what needs to be synced. |
| **New Stuff** | `dot status` | Finding hidden dotfiles you forgot to track. |
| **Full Scan** | `dot status --ignored` | Verifying your ignore rules are working. |

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
