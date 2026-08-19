# Shared: Workspace Guard

Needs at load time: nothing. This file is a leaf — it links to no other file, and reads none.

## Prevention Is Primary

Every git command carries an explicit `git -C <worktree_path>`, and every file path is resolved
against `worktree_path`. A bare `git` invocation or a repo-relative path that resolves against the
process working directory is a defect, not a style preference.

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
  path:                  <worktree>/<frontend_source_root>
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
edits to files inside it are invisible to it. The frontend is also initialized inside the
*worktree*, not the source checkout, so the source-checkout baseline cannot cover it even in
principle. Both facts point to the same fix: a second, independent content-addressed baseline
scoped to the frontend working tree, captured immediately after frontend source initialization and
re-computed at Stage 04.

## Capture Commands

```bash
git -C "$P" rev-parse HEAD
git -C "$P" diff --binary HEAD | shasum -a 256
git -C "$P" diff --cached --binary HEAD | shasum -a 256
git -C "$P" ls-files --others --exclude-standard
```

## Untracked Cap

If the untracked set exceeds 2000 files or 50 MB, fingerprint paths and sizes only, and record
`baselines.untracked_fingerprint: degraded` in `execution-report.md`'s run-state block — a stated
limitation beats an unbounded hashing pass, and a limitation recorded in the run-state contract is
one Stage 04 can still read when it re-verifies.

## On Violation

Any difference at Stage 04 stops the run **before committing**, and reports the differing paths
with both the baseline and current hashes. **Never revert the source checkout** — undoing a
developer's working tree without asking is worse than the leak.

A `frontend_baseline` difference is a violation **unless** `frontend_edits_approved: true`, in
which case the diff is reported for review instead of stopping the run. This is what makes "the
frontend is read-only" a checked property rather than an intention.

## Known Limits, Stated Not Hidden

Gitignored files — `.env` above all — appear in neither `git diff` nor
`ls-files --others --exclude-standard`, so a write to one is not detected. Detection also runs only
at Stage 04, so it reports a leak rather than preventing it; prevention is the `-C <worktree_path>`
discipline above.
