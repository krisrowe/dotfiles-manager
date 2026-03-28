# Contributing

## Design Principles: Exclude / Ignore

The exclude system controls what `dot status` shows — which untracked or
modified paths surface as needing attention and which are silently ignored.
This is critical because the work tree is `$HOME`, which contains thousands
of files the user will never want to track.

### Goals

1. **Clean status output.** `dot status` should feel like `git status` in a
   normal working directory — only actionable items, no noise. Users must be
   able to suppress entire directory trees (e.g. `~/.cache/`, `~/.local/`)
   so that genuinely untracked dotfiles are easy to spot.

2. **Single CLI workflow.** All exclude management must be available through
   `dot` CLI and MCP tools, with logic centralized in the SDK layer. Users
   should not need to switch to a different tool or manually edit git
   internals to manage exclusions.

3. **Portable exclusions as a first-class concern.** Building a useful
   exclude list is a real investment — it takes time to discover which
   paths under `$HOME` are noise. The tool must treat that investment as
   something worth preserving: make it easy to export, restore, and carry
   to new machines without re-doing the work. CLI output, MCP tool
   descriptions, documentation, and agent skills should actively surface
   the portability of exclusions so users are aware of it and can act on
   it. Preservation must be clean, low-friction, and secure — exclude
   lists must not transit through dotfiles stores, public repos, or
   any git remote not specifically designated for sensitive content,
   since the patterns themselves can reveal what exists on a machine.

4. **Multi-store awareness.** Multiple stores share `$HOME` as their work
   tree. The exclude mechanism must account for this — patterns may apply
   globally or per-store.

### Constraints

1. **No sensitive paths in tracked files.** Exclude patterns can reveal
   what software, services, or configurations exist on a machine. An exclude
   list committed to a public (or even private-but-shared) repo could leak
   the presence of sensitive tooling, personal projects, or confidential
   work. **Never commit exclude patterns to the dotfiles repo itself.**
   Exclude files must live in git internals (`info/exclude`) or in
   out-of-band configuration — not in tracked content.

2. **Use git's native mechanisms.** Git provides `info/exclude` (per-repo,
   untracked) and `core.excludesFile` / `~/.config/git/ignore` (global,
   user-managed). The tool should build on these rather than inventing
   parallel systems. This keeps behavior predictable for users who
   understand git.

3. **No cross-store side effects.** Adding an exclude pattern to one store
   must not silently modify another store's configuration. If a pattern
   should apply to all stores, that is the user's explicit choice, not an
   automatic sync.

4. **Transparency over magic.** Users should be able to see where patterns
   are stored and what git mechanism is in effect. The tool reduces
   cognitive load around git plumbing flags, not around understanding what
   git is doing.

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
