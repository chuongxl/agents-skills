# Shared: Workspace Guard

Needs at load time: nothing. This file is a leaf — it links to no other file, and reads none.

## Prevention Is Primary

Every git command carries an explicit `git -C <workspace_path>`, and every file path is resolved
against `workspace_path`. A bare `git` invocation or a repo-relative path that resolves against the
process working directory is a defect, not a style preference.

`workspace_path` is the source checkout root under `isolation: branch` — the default — and
`<repo-root>/.worktrees/<branch>` under `isolation: worktree` (`run-state.md` rule 1). The
discipline is identical in both modes and matters *more* in the default one: there, a path that
resolves somewhere unintended lands in the developer's own checkout rather than in a tree the
pipeline owns and can throw away.

## Why `git status --porcelain` Is Not Sufficient

Detection is the backstop for when prevention fails silently. `git status --porcelain` output is a
status letter plus a path, so it is blind to any change that does not alter the letter:

| Baseline state | Agent action | `status` output | Detected? |
|---|---|---|---|
| `src/foo.ts` already modified | adds 50 more lines | unchanged: ` M src/foo.ts` | **no** |
| `notes.txt` already untracked | rewrites its contents | unchanged: `?? notes.txt` | **no** |
| `src/bar.ts` clean | modifies it | `""` → ` M src/bar.ts` | yes |
| no such file | creates it | `""` → `?? new.txt` | yes |

The blind spot is exactly the case worth protecting: paths that were already dirty before the run,
which is the normal state of a developer's checkout mid-task.

## The Two Baseline Schemas

The baseline is therefore content-addressed. Field name `workspace_baseline` — not
`*_baseline_status`, since it no longer holds status strings.

`workspace_baseline`, over the source checkout:

```
workspace_baseline:
  path:                  <source checkout root>
  head_sha:              git -C <path> rev-parse HEAD
  worktree_diff_sha256:  sha256( git -C <path> diff --binary HEAD )
  index_diff_sha256:     sha256( git -C <path> diff --cached --binary HEAD )
  untracked:             [ {path, size, sha256}, ... ]   # git ls-files --others --exclude-standard
```

`frontend_baseline`, over the frontend working tree:

```
frontend_baseline:
  path:                  <workspace_path>/<frontend_source_root>
  head_sha:              git -C <path> rev-parse HEAD
  worktree_diff_sha256:  sha256( git -C <path> diff --binary HEAD )
  index_diff_sha256:     sha256( git -C <path> diff --cached --binary HEAD )
  untracked:             [ {path, size, sha256}, ... ]
```

- `diff --binary HEAD` captures every tracked change, staged or not, byte for byte.
- `diff --cached --binary HEAD` is kept separately so a pure staging change — `git add` with no
  content edit, which leaves `diff HEAD` identical — is still detected.
- `untracked` needs its own fingerprint because no `git diff` form covers untracked files.
  `--exclude-standard` keeps ignored trees such as `node_modules/` out.

## Why Two And Not One

A parent repository's `git diff HEAD` sees a submodule only as a gitlink — a commit pointer — so
edits to files inside it are invisible to it. Under `isolation: worktree` the frontend is also
initialized inside the *worktree*, not the source checkout, so the source-checkout baseline cannot
cover it even in principle. Either fact alone forces the same fix, and the first one holds in both
isolation modes: a second, independent content-addressed baseline scoped to the frontend working
tree, captured immediately after frontend source initialization and re-computed at Stage 04.

## What `workspace_baseline` Checks, Per Mode

Both baselines are *captured* identically in either isolation mode. What Stage 04 is entitled to
conclude from `workspace_baseline` is not identical, and one rule stated for both would claim a
guarantee the default mode cannot make.

**`isolation: worktree` — the whole-tree check.** The run happens at
`<repo-root>/.worktrees/<branch>` and the source checkout is never written to, so any difference
between the captured baseline and a fresh capture at Stage 04 is a leak, whatever it contains.

**`isolation: branch` — the scoped pair.** The run happens *inside* the source checkout, so the
pipeline's own output changes that tree by design and a whole-tree comparison would flag the
deliverable itself as a violation. Two narrower checks replace it, and **both** must pass:

1. Every entry of `baselines.preexisting_dirty[]` still hashes to the `sha256` recorded at intake;
   an entry recorded with `sha256: null` must still be absent from disk. This is the developer's
   in-flight work, and it is the thing branch mode is most able to damage.
2. Every path changed since intake falls inside `baselines.owned_paths[]`. A change outside that
   set is a leak in exactly the sense the worktree check means, and stops the run the same way.

Neither is a weaker form of the other and neither substitutes for it. Check 1 catches the run
overwriting work it did not create; check 2 catches it creating work outside its own scope. A run
passing only check 1 has scattered files across the repository; a run passing only check 2 has
clobbered a file the developer was editing inside a directory the pipeline does own.

`frontend_baseline` is unchanged in both modes — the frontend is read-only either way, and its
`path` simply follows `workspace_path`.

### The Two Lists

Both are written in Stage 01 and read at Stage 04. Both are empty and unread under
`isolation: worktree`.

```
preexisting_dirty:   [ {path, sha256}, ... ]   # sha256: null -> path absent from disk at intake
owned_paths:         [ run.artifact_dir,
                       profile.feature_path, profile.steps_path, profile.page_path,
                       profile.selectors_path, profile.testdata_path,
                       ...every path bootstrap created, when it ran ]
```

`preexisting_dirty[]` is the union of three commands, run at intake before the pipeline writes
anything. It is a path list with a hash *per path*, not a whole-tree hash, because the question it
answers is per path — "did the run touch this file the developer was already editing?" The
whole-tree hashes above cannot answer it: they change the moment the pipeline writes its first
intended file.

`owned_paths[]` has two readers, which is why it is a stored list rather than a rule each reader
re-derives: `commit.md` stages exactly these paths, and check 2 verifies nothing outside them
changed. Re-derived in two places the definitions drift, and the drift surfaces as a commit that
staged a path the verifier then calls a leak.

## Capture Commands

```bash
git -C "$P" rev-parse HEAD
git -C "$P" diff --binary HEAD | shasum -a 256
git -C "$P" diff --cached --binary HEAD | shasum -a 256
git -C "$P" ls-files --others --exclude-standard
```

And, under `isolation: branch` only, the three that make up `preexisting_dirty[]` — hash each
resulting path's contents on disk, recording `null` for one that does not exist:

```bash
git -C "$P" diff --name-only HEAD
git -C "$P" diff --cached --name-only
git -C "$P" ls-files --others --exclude-standard
```

## Untracked Cap

If the untracked set exceeds 2000 files or 50 MB, fingerprint paths and sizes only, and record
`baselines.untracked_fingerprint: degraded` in `execution-report.md`'s run-state block — a stated
limitation beats an unbounded hashing pass, and a limitation recorded in the run-state contract is
one Stage 04 can still read when it re-verifies.

## On Violation

A failed check at Stage 04 — the whole-tree comparison under `isolation: worktree`, either half of
the scoped pair under `isolation: branch` — stops the run **before committing**, and reports the
differing paths with both the baseline and current hashes. **Never revert the source checkout** —
undoing a developer's working tree without asking is worse than the leak. That holds with more
force in the default mode, where the checkout that would be reverted is the one the developer is
standing in.

A `frontend_baseline` difference is a violation **unless** `frontend_edits_approved: true`, in
which case the diff is reported for review instead of stopping the run. This is what makes "the
frontend is read-only" a checked property rather than an intention.

## Known Limits, Stated Not Hidden

Gitignored files — `.env` above all — appear in neither `git diff` nor
`ls-files --others --exclude-standard`, so a write to one is not detected. Detection also runs only
at Stage 04, so it reports a leak rather than preventing it; prevention is the `-C <workspace_path>`
discipline above.

Under `isolation: branch`, `preexisting_dirty[]` is fixed at intake, so a file the developer starts
editing *after* the run began is not in it and check 1 cannot speak for it. Check 2 still catches a
write to that file unless it lies inside `owned_paths[]` — and inside `owned_paths[]` is precisely
where the pipeline is entitled to write. Branch mode therefore cannot protect concurrent edits to
the artifact folder or the test tree, which is the case `--parallel-worktree` exists for.
