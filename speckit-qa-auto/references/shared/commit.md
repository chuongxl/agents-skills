# Shared: Commit + Push Procedure

Needs at load time: nothing. This file is a leaf — it links to no other file, and reads none.

## Overview

Stage 04 is the only place this pipeline **pushes**, and the only place it makes a commit whose
message is human-approved. Stage 03 makes local, unpushed commits as scenarios resolve, so that
every recorded result names a real, committed tree rather than an uncommitted working state — see
`run-state.md` rule 4: `status: green` is only ever written next to the commit sha the run was
produced on. This procedure governs both: the incremental commits a stage makes as it goes, and
Stage 04's own commit-then-push. Stage 04 runs after both baselines have been re-verified clean, so
the push half of this procedure assumes that check already passed — a baseline violation stops the
run before any commit step.

## Conditional Commit

Check `git status --porcelain` in the worktree first. **Empty output is a success path, not a
failure** — it means the run's changes were already committed earlier (for example, incrementally
during Stage 03), and there is nothing left to commit here. In that case, skip the commit and
report the existing commits on the branch instead of treating the empty status as an error.

Non-empty output → `git add -A` → `git commit`. `.worktrees/` is git-ignored from Stage 01
onward, so `git add -A` inside the worktree cannot sweep the pipeline's own scratch state into the
feature commit.

## Fast-Forward-Only Push

No `pull --rebase`. Fetch, then branch on the relationship between local and remote:

```bash
git -C "$W" fetch origin "$BRANCH"
# remote absent      -> git -C "$W" push -u origin "$BRANCH"
# remote is ancestor -> git -C "$W" push origin "$BRANCH"
# diverged           -> STOP and report; do not rebase
```

`$W` is the worktree path; every command in this procedure carries an explicit `-C "$W"`. Determine
which of the three cases applies by comparing `git -C "$W" rev-parse origin/"$BRANCH"` against the
local branch tip (for example, `git -C "$W" merge-base --is-ancestor origin/"$BRANCH" HEAD`) before
choosing which push form to run.

## Why No `pull --rebase` Here

A rebase pulls in commits the test suite was never run against. If Stage 04 rebased and then
reported Stage 03's result, that result would describe a tree that never existed at the moment the
tests ran — the commit history would claim a green run for code the suite never saw.

This branch belongs to this pipeline. A diverged remote means something outside the pipeline wrote
to it — another run, a human, a rebase elsewhere. That is a human decision, not something to
resolve silently by pulling and rebasing over it. Stop and report; let the human decide how to
reconcile.

## Every Result Names Its Commit

Every reported test result — passing, blocked, or otherwise — names the commit sha it was produced
on. A result with no commit attached can never be trusted to describe the tree it claims to
describe, and it becomes untraceable the moment another commit lands on the branch.

## Reporting

Report the resulting commit(s) — hash and subject — and the branch that was pushed. If nothing
needed committing, report the prior commits on the branch instead of reporting "no commit" as if
it were a failure. A failed commit that was genuinely needed, a failed push, or a diverged remote
is a failure for the stage; a skipped commit on an already-clean tree is not.

## Red Flags — thoughts that mean STOP, not push through

| Thought | Reality |
|---|---|
| "I'll just `pull --rebase` so the push goes through" | That is exactly the case this procedure forbids. A diverged remote stops the run; it does not get resolved by rebasing |
| "The tree is empty, so there's nothing to report" | Empty status is a success path. Report the existing commits instead of reporting nothing |
| "Close enough, I'll push with `--force` to make it fast-forward" | Force-pushing discards commits that were not produced by this run. This procedure only ever pushes fast-forward or stops |
| "The result was green a minute ago, the commit sha doesn't matter now" | It matters the moment anything else lands on the branch. Every result names the commit it was produced on, with no exception |
