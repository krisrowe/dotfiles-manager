# Managing Sensitive Data in Dotfiles

## The Problem

Dotfiles frequently contain personally identifiable information (PII) and
other sensitive values: account identifiers, API keys, real names, email
addresses, employer-specific configuration, cloud project IDs, and absolute
paths that embed usernames. A pre-commit scanner catches these before they
reach a remote, but blocking every commit on every finding is blunt. Some
dotfiles are inherently personal and will always trigger the scanner.

This creates tension:

- **You want the scanner running** on public or potentially-public repos so
  nothing sensitive slips through.
- **You also want to track private config** that will always contain personal
  data, without fighting the scanner on every commit.

## Why Not Just Use a Private GitHub Repo for Everything?

A private GitHub repo is convenient but is a weak container for genuinely
sensitive information:

- **Access tokens are broad.** A personal access token that leaks (browser
  session, dotfile, CI log) can expose every private repo in the account.
- **Visibility is one click away.** Repo settings let you flip a private repo
  to public instantly. There is no confirmation gate proportional to the risk.
- **Shoulder-surfing.** Showing someone a repo, reviewing a PR, or
  screen-sharing a terminal can inadvertently expose private repo contents
  that happen to be open in another tab or pane.
- **No audit expectation.** Most people do not treat GitHub private repos as
  a controlled data store. There are no access reviews, no expiry, no
  encryption at rest beyond what GitHub provides by default.

For files that are merely *personal* (your shell aliases, your editor config),
a private GitHub repo is fine. For files that contain *sensitive* data
(credentials, financial identifiers, real account numbers), a cloud drive with
device-level encryption or a dedicated secrets manager is more appropriate.

## Design: Multiple Stores

The solution is **named stores** — independent bare repos, each with its own
tracking, hooks configuration, remote, and backup target. The default store
works exactly as dotfiles-manager does today. Additional stores are opt-in.

### Stores Overview

| Store | Contents | Pre-commit hooks | Backup target |
|-------|----------|-----------------|---------------|
| `default` | Shell config, editor settings, tool config — anything that passes the scanner | Enabled | GitHub (private repo) |
| `sensitive` (example) | Files with PII, credentials, employer-specific config | Disabled | Cloud drive or encrypted archive |

Each store is a separate bare repo (e.g., `~/.dotfiles` for default,
`~/.dotfiles-sensitive` for a store named "sensitive"). Each has its own
git config, so hook settings (`core.hooksPath`) are per-store with no
additional mechanism needed.

### Active Store

There is always an **active store**. All commands (`dot track`, `dot sync`,
`dot list`, `dot status`, etc.) operate on the active store. The active
store defaults to `default` and persists across shell sessions.

```bash
dot store use sensitive    # switch active store
dot track ~/.config/myapp/secrets.conf
dot sync
dot store use default      # switch back
```

This means existing users see **zero behavior change**. If you never create
a second store, no config file exists and everything works as it does today.

### Configuration

Today there is **no XDG configuration** for this tool. The only file in
`~/.config/dotgit/` is an exclude file (gitignore-format patterns for
filtering tracked directories), but it is functionally per-repo state and
should be relocated into each bare repo's `info/exclude` (git's built-in
mechanism). This cleanup should happen before or alongside the multi-store
work, so that `~/.config/dotgit/` starts clean.

Store definitions will live in `~/.config/dotgit/stores.yaml`. This file
only exists once a non-default store is created. The default store
(`~/.dotfiles`) is implicit and never needs an entry.

```yaml
active: default
stores:
  sensitive:
    repo: ~/.dotfiles-sensitive
```

This should be the **only** file in `~/.config/dotgit/`, and it should only
exist when a non-default store has been created. The goal is to minimize
configuration footprint — a single-store user should have no XDG config
at all.

### CLI Commands

#### Store management

| Command | Description |
|---------|-------------|
| `dot store create <name>` | Create a new empty store (init bare repo, register in config) |
| `dot store use <name>` | Switch the active store |
| `dot store list` | Show all stores and which is active |

#### Restore with stores

`dot restore` gains an optional `--store` flag:

```bash
# Restore the default store (unchanged from today)
dot restore git@github.com:USER/personal-dotfiles.git

# Restore into a named store
dot restore git@github.com:USER/personal-dotfiles-sensitive.git --store=sensitive
```

When `--store` is provided, the tool clones the bare repo to
`~/.dotfiles-<name>` and registers it in `stores.yaml`.

#### Topic-based discovery

Each store's GitHub repo gets a topic following the convention
`dotgit-<store-name>` (e.g., `dotgit-default`, `dotgit-sensitive`).
`dot remote setup` sets this topic automatically.

On a new machine, discovery finds all your stores:

```bash
dot restore --discover
```

This queries `gh repo list --topic dotgit-*` to find all dotgit-managed
repos, maps each topic to a store name, and restores them. Stores backed
up outside GitHub (cloud drive, etc.) are not discoverable this way and
must be restored manually from a bundle file.

### MCP Tools

MCP tools operate on the **active store**, same as CLI commands. Additional
MCP tools expose store management:

| Tool | Description |
|------|-------------|
| `dot_store_list` | List all stores and active store |
| `dot_store_use` | Switch active store |
| `dot_store_create` | Create a new store |

All existing MCP tools (`dot_track`, `dot_sync`, `dot_list`, etc.) continue
to work unchanged — they operate on whatever store is active. An AI agent
that needs to work with a specific store switches to it first, does its work,
then switches back.

### Hooks Are Already Per-Store

Each bare repo has its own `core.hooksPath` git config. The existing
`dot hooks disable` / `dot hooks reset` commands already operate on the
current repo. With multiple stores, they naturally operate on the active
store:

```bash
dot store use sensitive
dot hooks disable          # disables hooks on the sensitive store only

dot store use default
dot hooks show             # shows "default" — hooks still enabled here
```

No new mechanism is needed.

## Backup Strategies for Non-GitHub Stores

Stores that should not live on GitHub can be backed up via:

| Method | How | Pros | Cons |
|--------|-----|------|------|
| **Git bundle to cloud drive** | `dot git bundle create` then sync to Google Drive / iCloud / OneDrive | Simple, full history, offline access, device-level encryption | Manual unless scripted |
| **Git bundle to GCS bucket** | Upload bundle to a GCS bucket with IAM + encryption | Strong access control, audit logging, encryption at rest | Requires GCP setup |
| **Encrypted archive** | `tar` + `gpg` or `age` to cloud drive | Encryption independent of storage provider | Key management overhead |
| **Git remote on cloud drive** | Bare repo on a mounted cloud drive folder as the git remote | Automatic sync via cloud drive client | Depends on cloud drive git support; conflict risk |

The `git bundle` approach is the simplest starting point. `dot git bundle
create` already works today. A future enhancement could have `dot sync`
on non-GitHub stores automatically bundle to a configured cloud drive path.

## Migration Path

Starting from a single default store and adding a sensitive store:

1. **Run a pre-commit scan** on the default store to see what triggers.
2. **Triage findings.** For each flagged file: scrub and keep in default,
   or move to the sensitive store.
3. **Create the sensitive store.** `dot store create sensitive`
4. **Disable hooks on it.** `dot store use sensitive && dot hooks disable`
5. **Move files.** `dot store use default && dot untrack <file>`, then
   `dot store use sensitive && dot track <file>`.
6. **Set up backup** for the sensitive store (bundle to cloud drive, or
   `dot remote setup` if GitHub is acceptable for now).
7. **Clean default store history** if sensitive data was previously committed
   (matters if the default store might ever become public).

## Periodic Review

Periodic review of the sensitive store helps keep it small and intentional:

- **What is here?** `dot store use sensitive && dot list`
- **Does it still need to be here?** Credentials may have been rotated,
  config may have been made generic.
- **Am I comfortable with where it is stored?** If on GitHub, should it
  move to cloud drive? If on cloud drive, is that still appropriate?
- **Can anything move to the default store?** Scrubbing a file of PII and
  moving it to the scanner-clean default store reduces the sensitive store's
  surface area.

This review is lightweight when the sensitive store is small and
well-defined, which is the main argument for keeping it separate rather
than mixing everything behind an allowlist.
