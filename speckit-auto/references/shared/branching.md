# Shared: Branching + Worktree (Provider-Agnostic)

Applies identically to every provider. Loaded by Stage 01 of all providers.

## Preflight Worktree + Branch Setup

**Mandatory gate — must complete before any other Stage 01 action** (framework source check,
framework install, guidelines load, intake, or any provider stage call):

1. Base branch priority: `develop` → `main` → `master` (local first, then remote-tracking).
   If none exists, stop with a missing base-branch error.
2. Sync the base branch to latest before branching off it:
   - `git fetch origin <base-branch>`
   - `git checkout <base-branch>`
   - `git pull origin <base-branch>` (fast-forward only)
   - If fetch/pull fails (no remote, offline, conflict), log a warning and continue with the local
     copy of `<base-branch>` as-is — this is not a hard stop.
3. Resolve the deterministic branch name (final or provisional) exactly as defined below.
4. Branch name must exactly match the feature name the run will use for its `specs/` artifact folder
   (`<issue_id>-<short_title>` in `--issue` mode, `<NNN>-<slug>` in manual mode — see
   [intake.md](intake.md) → "Artifact Identity"). Branch and artifact folder are always the same
   string, never two different deterministic schemes.
   - `short_title` (Jira mode) and the final `<NNN>-<slug>` (manual mode) are only fully resolved
     during intake, which runs *after* this branch gate. If the full name is not yet known:
     - Jira mode: create/checkout a provisional branch named `<issue_id>` only.
     - Manual mode: create/checkout a provisional branch named from the requirement slug (best
       guess at this point, no timestamp — a timestamp would never match the feature name).
   - **Rename step (required once intake resolves the final feature name):** as soon as the
     provider's Stage 01 resolves `<issue_id>-<short_title>` or `<NNN>-<slug>`, and if the current
     branch name differs from it, run `git branch -m <final-name>` to rename the checked-out branch
     in place (do not create a second branch, do not delete/recreate). This must happen before any
     push or PR creation (Stage 04/05) — nothing upstream has been pushed yet at this point, so the
     rename is local-only and safe. Update `branch_name` in run state to the final name.
   - If [intake.md](intake.md)'s artifact-identity resolution finds an **existing** artifact folder
     from a prior run (a rerun), skip the provisional-name step and use that resolved final name
     directly when first creating/checking out the branch.
5. Ensure worktree root `<repo-root>/.worktrees/` is ignored:
   - if `.gitignore` exists and `.worktrees/` is missing, append it
   - if `.gitignore` does not exist, create it with `.worktrees/`
   - this edit is part of the feature branch commit flow; do not create a separate commit
6. Create or reuse a linked worktree for the resolved branch name:
   - canonical path: `<repo-root>/.worktrees/<branch-name>`
   - if a linked worktree already exists for that branch (rerun), reuse it and continue there
   - if branch exists without a linked worktree, add one at the canonical path
   - if branch does not exist, create it from synced `<base-branch>` while creating the worktree
7. Actually run the git command(s) now (do not describe the plan), switch execution into that
   linked worktree, and confirm the branch is checked out there before proceeding. Set
   `branch_created: true`, `branch_name`, and `worktree_path` in run state.
   - Every subsequent Stage 01 step (framework source check, framework install recovery, init, and
     provider stage calls) must execute from this linked worktree path on this branch. If a
     framework is missing there, install it there.
   - If `<repo-root>/.speckit/integration.json` exists in the source checkout, ensure
     `<worktree_path>/.speckit/integration.json` also exists with the same content before provider
     Stage 01 continues (create `<worktree_path>/.speckit/` if needed). This keeps the selected
     integration mode visible inside the linked worktree branch context.
8. **Rename alignment step (required once intake resolves final feature name):**
   - if current branch name differs, run `git branch -m <final-name>` inside the linked worktree
   - if current worktree path differs from canonical `<repo-root>/.worktrees/<final-name>`, move it
     with `git worktree move` when safe; if move fails, continue on current path and log warning
   - update run state `branch_name` and `worktree_path`

## Git Submodule Branch Handling (Implementation Stage)

Apply only when the repo uses git submodules.

1. Detect submodules from `.gitmodules` and track their paths.
2. The first time code changes are about to occur inside a submodule path (lazily, only for
   submodules actually modified):
   - base branch priority inside the submodule: `develop` → `main` → `master` (local first, then remote-tracking)
   - sync that base first: `git fetch origin <base-branch>` → `git checkout <base-branch>` →
     `git pull origin <base-branch>` (fast-forward only) inside the submodule; on fetch/pull
     failure, log a warning and continue with the local copy — not a hard stop
   - create/switch to a new working branch off the now-synced base, before editing any file there
   - branch name should be deterministic and aligned with the parent pipeline branch context
3. If no submodule exists, or no submodule files are modified, behavior is unchanged.

## Commit Ordering With Submodules

Commit submodule changes first, then commit the parent repo pointer updates. Never commit the
parent pointer before the submodule commit it points at exists.
