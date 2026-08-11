# Shared: Branching (Provider-Agnostic)

Applies identically to every provider. Loaded by Stage 01 of all providers.

## Preflight Branch Setup

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
3. Create or switch to the working branch off the now-synced base branch:
   - if the deterministic branch name does not exist → create it from the synced base
   - if it already exists (a rerun) → check it out and **continue on it**; never reset, force-move,
     or recreate it, and never append a suffix to make a new one
4. Branch name must be deterministic:
   - Jira mode: include the Jira key (use the `issue_id`/`short_title` resolved in
     [intake.md](intake.md) so branch and artifact names stay aligned across reruns)
   - Non-Jira mode: requirement slug + timestamp
5. Actually run the git command(s) now (do not describe the plan) and confirm the working branch is
   checked out before proceeding. Set `branch_created: true` and `branch_name` in run state
   (`branch_created` means "the working branch is now checked out", whether created or reused).

Git worktrees are **not** used by any provider — see global rule 3. If a provider's native workflow
prescribes worktrees, that part is skipped in favor of the plain-branch flow above.

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
