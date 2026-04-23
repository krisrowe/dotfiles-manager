---
name: workstation-portability
description: "Workstation and workspace backup, portability, and reusability for code, configuration, AI tooling, dotfiles, plugins, and skills. Use when ensuring environment readiness, configuring new tools (Gemini, Claude, Jetski), registering user-scoped MCP servers/skills, or verifying backup posture. INVOKE ANYTIME the dotfiles-manager 'dot' CLI is used or whenever user-scoped workstation settings or dotfiles are being modified."
---

Maintain a posture of "Always Prepared" by ensuring your local workstation 
investments are portable, protected, and strictly categorized by sensitivity.

## 1. Store Architecture & Security Boundaries

| Store Tier | Remote Target | Content Type | Security Mandate |
| :--- | :--- | :--- | :--- |
| **`home`/`work`** | **GitHub (Private)** | Editor/CLI settings, shell profiles, logic. | **NO SENSITIVE DATA.** No company names, customer names, real names, emails, or absolute workspace paths. |
| **`personal`** | **GitHub (Private)** | Personal records, tax info, contact lists. | **PRIVATE.** Ensure hooks/scanners are active. |
| **`secrets`** | **NONE (Local)** | SSH config, tokens, credentials, TF state. | **LOCAL ONLY.** Never push to a remote. |

## 2. Mandatory Pre-Sync Review

Before executing `dot sync` or any command that pushes to GitHub, you **MUST** 
conduct a comprehensive review of all pending changes:

1.  **Inventory:** Run `dot status` to identify all modified and untracked files.
2.  **Log Review:** Use `dot git log @{u}..HEAD --oneline` to audit every commit message that has not yet been pushed.
3.  **Content Review:** Use `dot git diff @{u}..HEAD -p` to inspect every line of every commit ahead of the remote tracking branch.
4.  **The Privacy Judgment Call:** Look beyond secrets/tokens. Verify the diff 
    does not contain:
    - **Company/Org Names:** Your employer's name, customer names, or proprietary project names.
    - **Personal Info:** Real names (yours/colleagues), email addresses, phone numbers.
    - **Workspace Paths:** Absolute paths revealing your local layout (`/Users/name/...`).
    - **Identifiers:** Cloud project IDs, Drive folder IDs, or specific resource names.
5.  **Confirm Store:** Ensure you are not adding a sensitive file to a 
    GitHub-tracked store by mistake.

## 3. The "Explicit Siblings" Philosophy

For directories containing both portable config and ephemeral noise:
- **Avoid** ignoring the parent directory entirely (the "Black Box" mistake).
- **Instead**, ignore the specific high-noise **siblings** (individual files, 
  logs, caches, or sub-folders you don't want).
- **Benefit:** This keeps the parent "open" so that any new, important configuration 
  files or sub-folders will surface in `dot status` for review.

## 4. Confidence Check Workflow

- **`dot status --stats`**: Verify the environment balance (Tracked vs. Discovered).
- **`dot status --ignored`**: Audit your "Black Boxes" to ensure no new 
  valuable configuration is accidentally buried.
- **Git Repo Scan**: Search for local git repositories with uncommitted changes 
  to identify work-at-risk.

### What "ready" looks like
- `dot status` is clean (no modified tracked files).
- All custom agent `commands/` and `skills/` are tracked in the appropriate store.
- Sensitive state is safely committed to the `secrets` store.
- `dot --store work sync` has pushed all changes to GitHub after a manual review of all pending commits.
