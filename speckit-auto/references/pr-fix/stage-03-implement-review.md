# PR fix: Stage 03 implementation and review

Emit the normal stage start. Implement the requested fix and regression tests in the validated
worktree, using the selected provider where applicable and without requiring a new spec or tasks
file. Use the fetched PR base SHA to find the merge base and review the **full** PR change set
plus this run's staged and unstaged changes; exclude and preserve unrelated initial dirty changes.

When no matching spec or tasks exist, give the implementer the PR/request basis, intended changes
and relevant project context instead of a nonexistent plan path. Identify touched workspaces from
the requested fix and changed paths rather than a tasks artifact, and apply the shared workspace
pre-flight and safe submodule rules to those workspaces.

When Stage 02 identified a relevant spec, invoke `speckit-code-review` inline with that spec and
the merge-base `base_ref`, passing the initial dirty paths as `exclude_worktree_paths`. When there
are initial dirty paths, confirm that the installed reviewer supports that input; if not, stop
with an actionable diagnostic to update `speckit-code-review`, rather than treating an unscoped
review as passing. Also check that the fix request is addressed. With no matching spec,
perform a direct line-by-line review against the PR description, request and existing behavior,
including correctness, security and regression tests. Record `review: direct` and its actual
findings; never claim `speckit-code-review` passed. Fix blocking findings and repeat the same
review and checks until clear or the existing circuit breaker fires. Do not treat an unchanged
fix as successful without evidence that the requested behavior already works.

Run the existing R2c project checks and changed-file formatting checks for the fix. A full
repository check failure is `pre-existing` only when the same command reproduces the same
unrelated failure against the baseline in an isolated checkout; record the evidence. A failure
introduced by this run remains blocking. Preserve and report unavailable checks honestly.
Emit the normal stage finish only after the applicable review and checks pass, and enter Stage 04.
