# Alternatives

dotfiles-manager is one of several approaches to managing dotfiles with git.
This document compares the major alternatives to help you decide which fits
your workflow.

## Manual Bare Git Repo

The approach described in the
[Atlassian dotfiles tutorial](https://www.atlassian.com/git/tutorials/dotfiles).

### Summary

You create a bare git repository (e.g. `~/.dotfiles`), define a shell alias
like `dotgit="git --git-dir=$HOME/.dotfiles --work-tree=$HOME"`, set
`status.showUntrackedFiles no`, and then use that alias in place of `git` to
track and sync config files. No tools to install — just git and a shell alias.

### Pros and Cons

**Pros:**
- Zero dependencies beyond git
- Fully transparent — every operation is a visible git command
- Nothing to learn if you already know git
- No abstraction layer that can break, lag behind git, or behave unexpectedly

**Cons:**
- The alias must be configured on every machine before you can do anything,
  creating a bootstrap problem
- Managing multiple independent sets of dotfiles (e.g. personal vs. work)
  requires manually juggling multiple aliases and bare repos
- Easy to forget `status.showUntrackedFiles no`, which floods `git status`
  with your entire home directory
- No guardrails — `git rm` (without `--cached`) deletes the actual file,
  `git add .` stages everything under `$HOME`
- Remote setup is manual: create the GitHub repo, add the remote, set
  upstream tracking
- No built-in discovery — on a new machine you need to remember your repo
  URL and clone procedure

### When to use the manual approach instead

If you manage a single set of dotfiles, rarely set up new machines, and prefer
having zero dependencies, the manual alias approach is simpler and sufficient.
dotfiles-manager adds value when you want multi-store management, safe
defaults, remote discovery, or an AI-agent interface — without giving up the
transparency of the bare-repo pattern underneath. Your stores are still bare
git repos, so you can stop using the tool at any time and fall back to the
alias approach with nothing to migrate.

---

## chezmoi

[chezmoi](https://www.chezmoi.io/) is the most popular dedicated dotfiles
manager, with a large community and extensive feature set.

### Summary

chezmoi copies your dotfiles into a **source directory**
(`~/.local/share/chezmoi/`) which is a regular git repository. It then
**applies** the source state back to your home directory, optionally running
files through a template engine, encrypting secrets, or adjusting for the
target OS. Git operations happen inside the source directory using standard
git commands (via `chezmoi git -- <args>` or `chezmoi cd`).

The core workflow is:
```
chezmoi add ~/.bashrc        # copy into source dir
chezmoi edit ~/.bashrc       # edit the source copy
chezmoi apply                # deploy source → home
chezmoi git -- commit -am "update bashrc"
chezmoi git -- push
```

### Pros and Cons

**Pros:**
- Mature, well-documented, large community
- Powerful template engine — one source can produce different configs per OS,
  hostname, or environment
- Built-in secret management (1Password, Bitwarden, Vault, gpg, age)
- Encryption for sensitive files
- `chezmoi diff` previews changes before applying
- Three-way merge support for conflict resolution
- Works across Linux, macOS, Windows, and FreeBSD

**Cons:**
- Files are **copied**, not tracked in place — your actual dotfiles and the
  source copies can drift apart, requiring `chezmoi re-add` to reconcile
- Introduces its own concepts: source state vs. target state, file attributes
  encoded in filenames (e.g. `dot_bashrc.tmpl`), a template language
- The source directory layout does not mirror your home directory
  structure — filenames are transformed (e.g. `dot_` prefix, `encrypted_`
  prefix, `.tmpl` suffix)
- Heavier learning curve if you don't need templates or encryption
- Git operations are not first-class commands — you either use the
  passthrough (`chezmoi git --`) or drop into the source directory
  (`chezmoi cd`)
- Walking away from chezmoi requires reversing the copy: extracting your
  files from the source directory's transformed filenames back to their
  original paths. The tool is the source of truth, not git alone

### When to use chezmoi instead

chezmoi is the better choice when you need **templates** (one set of
dotfiles that adapts to different machines), **encryption** for secrets in
your dotfiles, or **cross-platform support** across Linux, macOS, and
Windows. If your dotfiles contain passwords, API keys, or machine-specific
values that need templating, chezmoi's feature set justifies its complexity.

dotfiles-manager is preferable when you want your files **tracked in
place** with no copy/apply cycle, a mental model that maps directly to git,
multi-store separation without filename transformations, and a lightweight
tool that adds ergonomics to the bare-repo pattern rather than replacing it
with a new abstraction. Because it uses the same bare-repo format as the
manual approach, there is no lock-in — you can stop using it at any time and
your dotfiles remain in standard git repos with nothing to export or
reconstruct.
