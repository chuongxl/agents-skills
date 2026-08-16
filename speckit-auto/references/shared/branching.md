# Shared: Workspace, Branching + Submodules (Provider-Agnostic)

Applies identically to every provider. Loaded by Stage 01 of all providers.

## Workspace Gate (Runs After Intake)

**Mandatory gate — must complete before any business-code write and before the provider's Stage 02
entry step.** It runs *after* the framework source check, install recovery, guidelines load, and
intake, because intake is what resolves the final feature name. Creating the workspace once with
that final name removes the provisional-name/rename/move churn entirely.

The three steps that precede this gate are safe by construction: the framework check and guidelines
load are read-only, and intake writes `ticket.md` to a staging path and relocates it once the
artifact folder exists (global rule 4a). Framework installation writes to the base checkout, and
that is correct — `.speckit/` is repo-level tooling, not feature-branch content.

1. Resolve the base branch: `develop` → `main` → `master` (local first, then remote-tracking).
   If none exists, stop with a missing base-branch error.
2. Sync that base at the repo level, best-effort:
   - `git fetch origin <base-branch>`
   - `git checkout <base-branch>`
   - `git pull origin <base-branch>` (fast-forward only)
   - A fetch/pull failure logs a warning and continues with the local copy. Never a stop.
   - Base handling *inside* a submodule differs by mode — see "Submodule Workspaces" below.
3. Use the final feature name resolved by intake — `<issue_id>-<short_title>` in `--issue` mode,
   `<NNN>-<slug>` in manual mode (see [intake.md](intake.md) → "Artifact Identity"). The branch
   name and the `specs/` artifact folder are always the same string. There is no provisional name
   and no rename step.
4. Resolve `workspace_strategy` and create the workspace (see below).
5. Run the git command(s) now — do not describe the plan — and confirm the branch is checked out
   before proceeding. Set `branch_created: true`, `branch_name`, `workspace_strategy`, and
   `workspace_root` in run state.

## Strategy Selection

`workspace_strategy` defaults to `branch`. The `--worktree` flag selects `worktree`. Repo shape
then decides how `worktree` is realized — detection is the presence of `.gitmodules`:

| Repo shape | `branch` (default) | `worktree` (`--worktree`) |
|---|---|---|
| Has `.gitmodules` | umbrella branch in-place; modified submodules branch in-place | **umbrella branch in-place**; modified submodules get worktrees |
| Single repo | branch in-place | repo worktree at `.worktrees/<feature>/` |

In a repo with `.gitmodules`, `--worktree` means exactly this:

- keep the umbrella repo in-place on a feature branch
- do not create an umbrella worktree
- isolate only modified submodules using submodule worktrees
- never run recursive submodule init/update

This is intentional. The umbrella repo is small and changes rarely. Creating an umbrella worktree
either loses ignored runtime state (`.env`, `.speckit/`, which git does not carry into a linked
worktree) or pushes the agent toward recursive submodule initialization, which costs minutes in
multi-team repos with 8-10 submodules. The strategy optimizes for the actual change surface: branch
the umbrella pointer, worktree only the submodules being edited.

For a single repo under `--worktree`, `workspace_root` is the worktree and artifact paths resolve
natively — no path map is needed. The ignored paths the run depends on (`.env` in `--issue` mode,
`.speckit/`) are **read from the repo root**, not from the worktree, and `.speckit/` output is
written back there. They are resolved by falling back to the repo root rather than copied, so
credentials are never duplicated onto disk.

## Ignoring `.worktrees/`

Use `.git/info/exclude` in all modes, unless `.gitignore` already contains `.worktrees/`, in which
case write nothing. `info/exclude` is local and untracked, so it dirties no tracked file and needs
no commit — which matters for single-repo `--worktree`, where a `.gitignore` edit would land in the
base checkout rather than in the feature worktree it is meant to describe.

## Rerun Reuse Validation

An existing branch or linked worktree for the resolved name is reused rather than recreated, but
only after validating all of:

- the branch name matches the final feature name
- the registered worktree path exists and is a git worktree
- an existing `.worktrees/<feature>/apps/<submodule>` path is associated with the expected
  submodule repo
- the mapped submodule worktree is on the expected branch, or detached at the expected base
- the branch is not checked out in an incompatible location

If any check fails, stop and report the exact reason. Never silently reuse stale state.

## Risk-Triggered Confirmation

Dirtiness is evaluated per level, and the two levels have different available remedies. A clean
tree at both levels asks nothing, preserving Stage 01's no-interview-gate property (global rule 5).

**Umbrella dirty** — tracked files modified or staged in the umbrella itself:

- If dirty before the branch switch: ask `Continue` / `Stop`.
- In a `.gitmodules` repo, worktree is **not** an available safety option for umbrella dirtiness.
  An umbrella worktree would lose the ignored runtime files above and/or push the agent toward
  recursive submodule hydration, whose cost this strategy exists to avoid.
- In a single repo, worktree **is** available, so the ask is `Worktree` / `Continue` / `Stop`.

**Submodule dirty** — tracked files modified or staged inside a submodule:

- If the selected mode is `branch`: ask `Worktree` / `Continue` / `Stop`.
- If the selected mode is `worktree`: do not ask. Proceed by creating submodule worktrees; the
  original submodule checkout is left untouched, so its dirty state is already safe.

**`--yolo` resolution.** No question is asked; the mode is chosen from the same condition:

| Condition | `--yolo` behaviour |
|---|---|
| Clean at both levels | `branch` (the normal default) |
| Submodule dirty only | `worktree` — isolation leaves the dirty checkout untouched |
| Umbrella dirty, single repo | `worktree` |
| Umbrella dirty, `.gitmodules` repo | **stop and report** — no safe automatic answer exists |

The last row is a deliberate stop: with no isolation available and no human to confirm, continuing
would commit the user's unrelated in-flight umbrella changes into the feature branch. Halting is
the lesser harm, and the condition is rare.

## Submodule Workspaces

Apply only when the repo uses git submodules. Detect submodules from `.gitmodules` and track their
paths.

### Branch mode (unchanged behaviour)

The first time code changes are about to occur inside a submodule path — lazily, only for
submodules actually modified:

- base branch priority inside the submodule: `develop` → `main` → `master` (local first, then
  remote-tracking)
- sync that base inside the original submodule checkout: `git fetch origin <base-branch>` →
  `git checkout <base-branch>` → `git pull origin <base-branch>` (fast-forward only); on
  fetch/pull failure, log a warning and continue with the local copy — not a hard stop
- create/switch to a working branch off the now-synced base, before editing any file there
- the branch name is deterministic and aligned with the parent pipeline branch context

Checkout and pull are correct here because the original submodule checkout is where the work
happens.

### Worktree mode (graft pass at Stage 03 entry)

`workspace_root` stays at the repo root; only modified submodules are isolated. The pass runs at
**Stage 03 entry**, not at this gate:

1. Parse `plan.md` for `apps/<name>/` prefixes. Only those submodules are touched.
2. For each submodule in that set, operating on the original checkout at `<repo-root>/apps/<name>`:
   if uninitialized, run `git submodule update --init apps/<name>` — that one submodule, never
   `--recursive` — then **fetch only**: `git -C <repo-root>/apps/<name> fetch origin`.
   **Checkout, pull, reset, or any other command that changes the original submodule's working
   tree or HEAD is forbidden in worktree mode.** Resolve the base to a concrete commit or ref
   (`develop` → `main` → `master`, local first, then remote-tracking). A fetch failure logs a
   warning and resolution continues against the local copy; it is never a stop.
3. Snapshot `git -C <repo-root>/apps/<name> status --porcelain` into run state
   `submodule_baseline_status{}`, keyed by submodule path. This happens **before** the worktree is
   created, and is what makes the leak guard safe on an already-dirty checkout.
4. `git -C <repo-root>/apps/<name> worktree add <repo-root>/.worktrees/<feature>/apps/<name> -b <branch> <resolved-base>`
5. Record the mapping in run state `submodule_workspaces{}`.

Scope is enforced structurally, not predicted: a submodule that is never named is never
initialized, so it cannot be pulled in. No `repo_map` lookup or heuristic is involved.

**Path map.** The worktree layout mirrors the umbrella, so resolution is a single prefix insertion:

```
apps/<name>/…   →   .worktrees/<feature>/apps/<name>/…
```

Resolve **every** artifact path beginning `apps/<name>/` through `submodule_workspaces{}` before any
read or write, whenever `<name>` has an entry. Paths for submodules with no entry, and all
non-`apps/` paths, resolve against the repo root unchanged.

**Fallback.** If a write targets a submodule with no entry — the plan missed it — graft it at that
moment, add the mapping, and continue. This is never a stop.

**Leak guard (required).** The failure mode this design defends against is silent: an agent writes
to `<repo-root>/apps/<name>/…` out of habit, landing changes on the original checkout while it sits
on the base branch, with no error raised.

Before the Stage 04/05 commit, for every entry in `submodule_workspaces{}`, re-run
`git -C <repo-root>/apps/<name> status --porcelain` and compare it against the baseline captured in
step 3. Stop and report the exact paths **only** when entries are new or changed relative to the
baseline. Entries identical to the baseline are the user's own pre-existing work and are left alone.
When the baseline is empty the guard degenerates to a plain "must be clean" check.

## Commit Ordering With Submodules

Commit submodule changes first, then the parent repo pointer updates. Never commit the parent
pointer before the submodule commit it points at exists.

In worktree mode, commit inside each mapped workspace from `submodule_workspaces{}`, not inside
`<repo-root>/apps/<name>`. The umbrella still observes the pointer change as `M apps/<name>` and
commits it normally. The leak guard runs before this step.
