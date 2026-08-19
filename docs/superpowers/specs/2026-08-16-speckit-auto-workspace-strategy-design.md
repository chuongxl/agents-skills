# speckit-auto — Workspace Strategy Design

Date: 2026-08-16
Status: approved (design), not yet implemented
Scope: `speckit-auto/references/shared/*`, both provider stage files

## Problem

The Stage 01 workspace gate is hard-coded to git worktree and runs before intake. Four defects
follow from that.

1. **The gate runs too early.** It executes before intake, so the final feature name is not known
   yet. It creates a provisional branch (`mom-8692`), then after intake renames with
   `git branch -m` and relocates with `git worktree move`. In the reference repo the rename
   succeeded but the move did not: the branch is `mom-8692-view-remaining-average-rates` while the
   worktree still sits at `.worktrees/mom-8692`.

2. **Worktree plus submodules is undefined.** No reference file tells Stage 01 what to do about
   submodules in a fresh worktree. A new worktree leaves every submodule directory empty, so the
   agent improvises `git submodule update --init --recursive`. In the reference umbrella repo
   (`om-mom-speckit-auto`, 7 submodules) that ran past 1 minute and blocked the pipeline.

3. **Scope is ignored.** A frontend-only ticket initializes all 7 apps.

4. **Worktree is mandatory and umbrella-wide.** There is no way to ask for a plain branch, and no
   way to scope isolation to the part of the repo that actually changes.

## Constraint 1: Artifact Paths Are Umbrella-Root-Relative

`plan.md` and `spec.md` reference source files relative to the umbrella repo root. Example from
`specs/mom-10860-create-and-save-customized-filter/plan.md` (26 such references):

```
apps/om-mom-frontend/src/containers/WorkOrderCandidate/utils/wo-candidate-saved-filter.ts
```

Any workspace that is not the repo root must therefore carry an explicit path map. See section 4.

## Constraint 2: Untracked Files Do Not Propagate To A Worktree

A linked worktree receives tracked content only. Anything gitignored stays behind in the base
checkout. The pipeline depends on three such paths, all ignored in the reference repo
(`.env`, `.speckit/`, `.superpowers/`):

| Missing in an umbrella worktree | Consequence |
|---|---|
| `.env` | `--issue` mode needs `JIRA_URL` / `JIRA_USERNAME` / `JIRA_API_TOKEN` at the root (`SKILL.md:124-125`); Jira fetch fails |
| `.speckit/integration.json` | provider resolution falls through to global, then to the first-run ask, on every run |
| `.speckit/review-*/` | review output is split across two locations |

Verified: `.worktrees/mom-8692/` contains no `.env`.

## Validated Mechanism: Submodule Worktree At An Umbrella-Shaped Path

A worktree of a submodule can be created at an arbitrary path, including one that mirrors the
umbrella layout, at the cost of two `git worktree add` calls and no clone:

```bash
git -C <repo-root>/apps/<sub> worktree add \
    <repo-root>/.worktrees/<feature>/apps/<sub> -b <branch> <base>
```

Verified on a synthetic umbrella + submodule repo:

| Check | Result |
|---|---|
| Edit + commit inside the submodule worktree on its own branch | pass |
| Umbrella reports `M apps/<sub>`; pointer commit succeeds | pass |
| Untouched submodules | never initialized |
| Original checkout | unaffected, still on base branch |
| Cost | no clone, no `submodule update --init --recursive` |
| Teardown | `git worktree remove --force` required |

The premise "worktree implies re-initializing every submodule" is false. It only holds when all
submodules are initialized unconditionally.

## Design

### 1. Stage 01 ordering

Before:

```
workspace gate → framework check → install recovery → guidelines → intake → Stage 02
```

After:

```
framework check → install recovery → guidelines → intake → workspace gate → Stage 02
```

Intake resolves the final feature name, so the gate creates the branch or worktree exactly once
with that name. All provisional-name machinery is deleted: `branching.md` step 4's provisional
bullets, its rename bullet, and step 8 (rename alignment plus `git worktree move`).

Two consequences must be stated explicitly in the rewritten rules.

- **The boundary changes meaning.** Global rule 1 currently forbids anything from running before
  the gate. It becomes: no business-code write may occur before the gate. The three steps that now
  precede it are safe — framework check and guidelines load are read-only, and intake already
  writes `ticket.md` to a staging path and relocates it once the artifact folder exists
  (global rule 4a).
- **Framework install writes to the base checkout, and that is correct.** `.speckit/` is
  repo-level tooling, not feature-branch content. Previously it landed inside the worktree by
  accident.

### 2. Strategy selection and repo detection

A new flag `--no-worktree` is parsed in `SKILL.md` entry dispatch, alongside `--issue` and
`--yolo`. Nothing is persisted to `integration.json`.

`workspace_strategy` defaults to `worktree`; `--no-worktree` selects `branch`. **Repo shape then
decides how `worktree` is realized** — detection is the presence of `.gitmodules`:

| Repo shape | `worktree` (default) | `branch` (`--no-worktree`) |
|---|---|---|
| Has `.gitmodules` | **umbrella branch in-place**; modified submodules get worktrees (section 4) | umbrella branch in-place; modified submodules branch in-place |
| Single repo | repo worktree at `.worktrees/<feature>/` | branch in-place |

The umbrella is branch in-place under **both** strategies, so an uncommitted umbrella change is a
live risk on the default path, not an edge case. Section 3 turns on this.

In a repo with `.gitmodules`, the default `worktree` strategy means exactly this:

- keep the umbrella repo in-place on a feature branch
- do not create an umbrella worktree
- isolate only modified submodules using submodule worktrees
- never run recursive submodule init/update

For repositories with `.gitmodules`, the `worktree` strategy deliberately does not worktree the
umbrella repository. The umbrella repo is small and changes rarely, so it remains on a
feature branch in-place. Only submodules selected by the plan are isolated with worktrees.

This is intentional: creating an umbrella worktree either loses ignored runtime state
(`.env`, `.speckit/`) or pushes the agent toward recursive submodule initialization, which
costs minutes in multi-team repos with 8-10 submodules. The strategy optimizes for the
actual change surface: branch the umbrella pointer, worktree only the submodules being edited.

At the repo level, in every mode, the base branch is resolved `develop → main → master` and synced
best-effort — a fetch or pull failure logs a warning and continues, never a stop. This is
unchanged. Base handling *inside* a submodule differs by mode and is specified in section 4.

**Ignoring `.worktrees/`.** Use `.git/info/exclude` in all modes, unless `.gitignore` already
contains `.worktrees/`, in which case nothing is written. `info/exclude` is local and untracked, so
it dirties no tracked file and needs no commit — which matters for a single-repo worktree, where
a `.gitignore` edit would land in the base checkout rather than in the feature worktree it is meant
to describe.

**Rerun reuse.** An existing branch or linked worktree for the resolved name is reused rather than
recreated, but only after validation:

- the branch name matches the final feature name
- the registered worktree path exists and is a git worktree
- an existing `.worktrees/<feature>/apps/<submodule>` path is associated with the expected
  submodule repo
- the mapped submodule worktree is on the expected branch, or detached at the expected base
- the branch is not checked out in an incompatible location

If any check fails, stop and report the exact reason. Never silently reuse stale state.

For a single repo under `worktree`, `workspace_root` is the worktree and artifact paths resolve
natively — no path map is needed. Constraint 2 still applies: the ignored paths the run depends on
(`.env` in `--issue` mode, `.speckit/`) are **read from the repo root**, not from the worktree, and
`.speckit/` output is written back there too. They are resolved by falling back to the repo root
rather than copied, so credentials are never duplicated onto disk.

### 3. Risk-triggered confirmation

Dirtiness is evaluated per level, and the two levels have different available remedies. A clean
tree at both levels asks nothing, preserving Stage 01's no-interview-gate property (global rule 5).

Because `worktree` is the default, most dirtiness is already absorbed by isolation and asks
nothing. A confirmation is needed only where isolation is unavailable or was explicitly declined.

**Umbrella dirty** (tracked files modified or staged in the umbrella itself):

- In a `.gitmodules` repo the umbrella is branch in-place under **both** strategies, so this fires
  on the default path: ask `Continue` / `Stop`. Worktree is not an available remedy — an umbrella
  worktree would lose the ignored runtime files of Constraint 2 and/or push the agent toward
  recursive submodule hydration, whose cost section 2 exists to avoid.
- In a single repo under the default `worktree`: do not ask. The repo worktree leaves the dirty
  checkout untouched.
- In a single repo under `--no-worktree`: ask `Worktree` / `Continue` / `Stop`.

**Submodule dirty** (tracked files modified or staged inside a submodule):

- Under the default `worktree`: do not ask. The submodule worktrees leave the original checkout
  untouched, so its dirty state is already safe.
- Under `--no-worktree`: ask `Worktree` / `Continue` / `Stop`.

**`--yolo` resolution.** No question is asked. `--yolo` never silently overrides an explicit
`--no-worktree`, and never proceeds when the only safe remedy is unavailable:

| Condition | `--yolo` behaviour |
|---|---|
| Clean at both levels | proceed on the default `worktree` |
| Submodule dirty, default strategy | proceed — submodule isolation leaves the dirty checkout untouched |
| Single repo dirty, default strategy | proceed — the repo worktree leaves the dirty checkout untouched |
| Umbrella dirty, `.gitmodules` repo | **stop and report** — the umbrella is branch in-place in every strategy, so no isolation exists to fall back on |
| Any dirtiness under explicit `--no-worktree` | **stop and report** — isolation is the only safe remedy and the user explicitly declined it |

Both stops are deliberate. With no human to confirm, continuing would commit the user's unrelated
in-flight changes into the feature branch, and overriding an explicit flag would violate a choice
the user stated on the command line. Halting is the lesser harm, and both conditions are rare.

### 4. Submodule worktrees and the path map

Applies to the `worktree` strategy on a repo with `.gitmodules`. `workspace_root` stays at the repo root; only
modified submodules are isolated.

A graft pass runs at **Stage 03 entry**, not Stage 01:

1. Parse `plan.md` for `apps/<name>/` prefixes. For MOM-10860 this yields exactly
   `om-mom-frontend`.
2. For each submodule in that set, operating on the original checkout at `<repo-root>/apps/<name>`:
   if uninitialized, run `git submodule update --init apps/<name>` (that one submodule, never
   `--recursive`), then **fetch only** — `git -C <repo-root>/apps/<name> fetch origin`.
   Checkout, pull, reset, or any other command that changes the original submodule's working tree
   or HEAD is **forbidden** in worktree mode. Resolve the base to a concrete commit or ref
   (`develop → main → master`, local first, then remote-tracking) and pass that resolved ref to the
   worktree command. A fetch failure logs a warning and resolution continues against the local
   copy; it is never a stop.
3. Snapshot `git -C <repo-root>/apps/<name> status --porcelain` and store it in run state
   `submodule_baseline_status{}`, keyed by submodule path. This runs **before** the worktree is
   created and is what makes the leak guard below safe on an already-dirty checkout.
4. `git -C <repo-root>/apps/<name> worktree add <repo-root>/.worktrees/<feature>/apps/<name> -b <branch> <resolved-base>`.
5. Record the mapping in run state `submodule_workspaces{}`.

Branch mode is unchanged: it still resolves and syncs the base inside the original submodule
checkout (fetch, checkout, pull), because that checkout is where the work happens.

Scope is enforced structurally, not predicted: a submodule that is never named is never
initialized, so it cannot be pulled in. No `repo_map` lookup or heuristic is involved.

**Path map.** The worktree layout mirrors the umbrella, so resolution is a single prefix insertion:

```
apps/<name>/…   →   .worktrees/<feature>/apps/<name>/…
```

Stage 03 must resolve **every** artifact path beginning `apps/<name>/` through
`submodule_workspaces{}` before any read or write, whenever `<name>` has an entry. Paths for
submodules with no entry, and all non-`apps/` paths, resolve against the repo root unchanged.

**Fallback.** If a write targets a submodule with no entry (the plan missed it), graft it at that
moment, add the mapping, and continue. This is never a stop.

**Leak guard (required).** The failure mode this design must defend against is silent: an agent
writes to `<repo-root>/apps/<name>/…` out of habit, landing changes on the original checkout while
it sits on the base branch, with no error raised.

Before the Stage 04/05 commit, for every entry in `submodule_workspaces{}`, re-run
`git -C <repo-root>/apps/<name> status --porcelain` and **compare it against the baseline captured
at graft time**. Stop and report the exact paths only when entries are new or changed relative to
the baseline. Entries identical to the baseline are the user's own pre-existing work and are left
alone.

The comparison is against a baseline rather than against empty because section 3 explicitly permits
starting a `worktree`-strategy run with a dirty submodule — an empty-status assertion would fire on that
pre-existing dirt and stop a run that is behaving correctly. When the baseline is empty the guard
degenerates to the simple "must be clean" check.

### 5. Commit

Ordering is unchanged: commit inside each modified submodule first, then the parent pointer update.
The spike confirmed the umbrella observes `M apps/<name>` and commits the pointer normally, whether
the submodule change was made in-place or in a grafted worktree. `commit.md` needs one change: when
`submodule_workspaces{}` is non-empty, commit inside each mapped worktree rather than inside
`<repo-root>/apps/<name>`.

The leak guard from section 4 runs before this step.

### 6. Run state

Adds:

| Field | Meaning |
|---|---|
| `workspace_strategy` | `branch` or `worktree` |
| `workspace_root` | absolute path the run operates from; replaces `worktree_path` |
| `submodule_workspaces{}` | submodule path → absolute workspace path; empty in `branch` mode and for single repos |
| `submodule_baseline_status{}` | submodule path → `git status --porcelain` output captured at graft time, before the worktree was created; consumed by the leak guard |

**Working-directory semantics.** Global rule 3 is rewritten from "always runs inside the Stage 01
linked git worktree" to:

> Root-level artifact and umbrella commands run in `workspace_root`. Any command targeting a mapped
> submodule path must run in that submodule's mapped workspace from `submodule_workspaces{}`.

This covers every command class, not just file edits: reads, writes, tests, lint, `status`, `diff`,
and `commit` for a mapped submodule all execute in the mapped workspace. Running a submodule's test
or lint command from the repo root would exercise the original checkout — the base branch, without
the change — and report a misleading pass.

## Files Affected

| File | Change |
|---|---|
| `speckit-auto/SKILL.md` | parse `--no-worktree` in entry dispatch; modes section |
| `shared/branching.md` | rewrite the gate; delete provisional/rename/move; strategy table; `.git/info/exclude` instead of `.gitignore`; rerun validation checklist; graft pass with fetch-only submodule handling; path map; baseline snapshot + leak guard |
| `shared/global-rules.md` | rules 1, 2, 3, 23; the `--yolo` risk-condition rule; **add the umbrella-dirty `--yolo` stop to the Absolute Operating Premise's valid-turn-end list**, which declares itself exhaustive |
| `shared/intake.md` | lines 4, 51–52, 150–153: gate now runs after intake; run-state fields |
| `shared/commit.md` | lines 25–36: commit inside mapped submodule workspaces; baseline-aware leak guard before commit |
| `superpowers/stage-01-preflight-intake.md` | lines 7, 12, 82–85: ordering and worktree wording |
| `github-speckit/stage-01-preflight-intake.md` | lines 7, 12: ordering |
| `superpowers/stage-03-implement-and-code-review-loop.md` | graft pass at entry; path map; lines 57–59, 102–104 |
| `github-speckit/stage-03-implement-and-code-review-loop.md` | graft pass at entry; path map; lines 39–41 |
| `superpowers/provider-rules.md` | lines 67–71: workspace wording |
| `superpowers/stage-04-human-review-and-commit.md` | line 28: worktree cleanup wording |

## Out of Scope

- Worktree teardown. `stage-04` already forbids cleanup during the pipeline; removing a submodule
  worktree stays a manual operation, and requires `--force`.
- Persisting the strategy in `integration.json`.
- Detecting that the user is already standing inside a worktree.
- Any change to editor tooling or IDE configuration.
