# Shared: Branching + Worktree (Provider-Agnostic)

Applies identically to every provider. Loaded by Stage 01 of all providers.

## Preflight Worktree + Branch Setup

**Mandatory gate — must complete before any other Stage 01 action** (framework source check,
framework install, guidelines load, intake, or any provider stage call):

1. Base branch priority: `develop` → `main` → `master` (local first, then remote-tracking).
   If none exists, stop with a missing base-branch error.
2. Sync the base branch to latest before branching off it (fetch + checkout + fast-forward pull).
   A fetch/pull failure is a warning, not a stop — continue with the local copy as-is.
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
   - If [intake.md](intake.md)'s artifact-identity resolution finds an **existing** artifact folder
      from a prior run (a rerun), skip the provisional-name step and use that resolved final name
      directly.
5. Execute the whole gate — base resolution/sync, `.worktrees/` gitignore enforcement, worktree
   create/reuse at the canonical path `<repo-root>/.worktrees/<branch-name>`, and branch
   check-out verification — as **one bash call**:

   ```bash
   bash <skill-dir>/scripts/worktree-bootstrap.sh --branch <branch-name>
   ```

   It prints one compact JSON object: `{ok, repo_root, base, branch, worktree_path, reused,
   warnings[]}`. On `ok:true`, switch execution into `worktree_path` for the rest of the run and
   set `branch_created: true`, `branch_name`, and `worktree_path` in run state. `warnings[]`
   (e.g. fetch/pull fallback) are logged and continued. On `ok:false`, the `error` string is the
   reportable failure — missing base branch and branch-checked-out-elsewhere are the hard stops.
   The `.gitignore` edit the script may make is part of the feature branch commit flow; never
   create a separate commit for it.
6. **Rename alignment (required once intake resolves the final feature name)** — again one bash
   call, run from inside the linked worktree:

   ```bash
   bash <skill-dir>/scripts/worktree-bootstrap.sh --rename-to <final-name>
   ```

   It renames the branch in place (`git branch -m`, never delete/recreate) and moves the worktree
   to the canonical `<repo-root>/.worktrees/<final-name>` path when safe; a failed move is a
   warning — continue on the current path. It returns `{ok, branch, worktree_path, warnings[]}`;
   update run state `branch_name` and `worktree_path` from it. This must happen before any push or
   PR creation (Stage 04/05) — nothing upstream has been pushed yet at this point, so the rename
   is local-only and safe.

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

## Persist Run-State After Stage 01

After Stage 01 completes (worktree linked, intake done, project context built, artifact folder
created), save the run-state so later stages can resume without re-running Stage 01. This is
mandatory even when the pipeline continues in the same turn — on stateless API hosts the
transcript is cumulative but attention to earlier content degrades; the file is the authoritative
resume point.

Write to `<worktree_path>/.speckit/run-state.json` (mkdir -p first). The format and field
definitions are in [run-state.md](run-state.md). At minimum, populate:

- `worktree_path` — from the bootstrap script output or the resolved path
- `current_stage: "stage-02"` — Stage 01 is done
- `integration` — the resolved provider
- `mode` — `"default"` or `"yolo"`
- `project_context` — summary, repo_map, linked_guidelines, loaded_guidelines from Stage 01
- `spec_path`, `plan_path`, `tasks_path`, `ticket_path`, `execution_report_path` — artifact paths
  relative to the worktree root

Persist call (single bash invocation):

```bash
mkdir -p <worktree_path>/.speckit && cat > <worktree_path>/.speckit/run-state.json << 'EOF'
{ ... }
EOF
```

Subsequent stages (02, 03) also persist run-state before declaring completion — see each
stage file's "Persist run-state" step.
