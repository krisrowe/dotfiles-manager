# Store Patterns

Stores can be named, organized, and backed up however you like. There
are no rules about how many stores to have, what to put in each, or
where to back them up. The examples below are just one pattern that
works well for separating data by sensitivity level.

## Example: Three-Tier Setup

### config (default store)

General configuration that contains no personal information or secrets.
Pre-commit hooks are enabled to enforce this — a scanner catches
anything personal before it reaches the remote.

```bash
dot track ~/.bashrc
dot track ~/.gitconfig
dot track ~/.config/myapp/settings.yaml
dot remote setup --repo-name my-config
dot sync
```

Backed up to a private GitHub repo.

**What goes here:** shell config, editor settings, tool configuration,
anything that passes a pre-commit scan for PII and secrets.

### personal

Configuration and data that contains personally identifiable
information — names, email addresses, employer-specific settings,
financial data, account identifiers — but not credentials or secrets.

```bash
dot stores create personal
dot --store=personal hooks disable
dot --store=personal track ~/.config/finance-app/profile.yaml
dot --store=personal track ~/.local/share/finance-app/records/
dot --store=personal remote setup --repo-name my-personal-config
dot --store=personal sync
```

Backed up to a private GitHub repo with hooks disabled (since the
files would trigger a PII scanner by design).

**What goes here:** app profiles with real names/employers, financial
records, tax configuration, data exports, anything with PII that
isn't a credential.

### secrets

Credentials, API keys, OAuth client secrets, tokens — things that
grant access to systems.

```bash
dot stores create secrets
dot --store=secrets hooks disable
dot --store=secrets track ~/.config/myapp/client_secret.json
dot --store=secrets track ~/.config/otherapp/api-key.txt
```

Some users are comfortable storing secrets in a private GitHub repo.
Others may not be — GitHub is accessed casually and frequently from
multiple machines, potentially machines owned or managed by different
entities, and many users wouldn't want that kind of access to become
a single point of failure for their credentials. GitHub repos can be
made public in one click, a leaked PAT exposes all private repos, and
even GitHub itself treats secrets differently from repo content
(Actions secrets are write-only and cannot be retrieved via the UI or
API).

For users who want secrets off GitHub, options include a self-hosted
git server, a cloud VM you control, or an encrypted bundle on a cloud
drive:

```bash
# Self-hosted git remote
dot --store=secrets remote set user@my-server:secrets.git
dot --store=secrets sync

# Or bundle to a cloud drive
dot --store=secrets git bundle create ~/cloud-drive/secrets.bundle --all
```

**What goes here:** OAuth client secrets, API keys, bearer tokens,
service account credentials, SSH private keys, anything that grants
access to a system.

**What does NOT go here:** OAuth refresh tokens or session credentials
for major cloud or device accounts (Google, Apple, Microsoft, etc.)
that act as master keys to an entire ecosystem of services. Compromise
of one of these tokens — even from a private bundle on a cloud drive —
becomes a single point of failure for everything tied to that identity.
These are the one class of credential users should re-authenticate
locally on each machine rather than backing up and restoring.

## Periodic Review

Each store is independently listable, making it easy to audit what's
where and reclassify as needed:

```bash
dot list                       # what's in the default store?
dot --store=personal list      # what personal data am I tracking?
dot --store=secrets list       # what secrets do I have?
```

Over time, files may move between stores. A config file that used to
have PII might get cleaned up and move to the default store. A token
that was in the personal store might get recognized as a credential
and move to secrets. The stores make this visible and manageable.
