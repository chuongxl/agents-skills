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
