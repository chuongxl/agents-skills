# Shared: Large Scope Partitioning (Provider-Agnostic)

Load only when the requirement is large, task volume is high, or many workspaces are involved.
Implements global rules 9 and 10.

## Package Strategy

1. Build `work_packages[]` by capability and `workspace` from `repo_map`.
2. For each package, include only: package goal, relevant spec/plan excerpts, target workspace,
   constraints. Never forward full prior-stage prose (global rule 8).
3. Invoke the stage's step once per package until the queue is empty.
4. After each batch, keep only compact progress state (remaining packages, changed files, blockers).

## Parallel vs Sequential

- **Parallel**: packages with no dependency edges and no shared file ownership.
- **Sequential**: packages with dependency/order constraints, in topological order.

## Merging

Per-package outputs must be merged into the **single** target artifact for that stage (one
`plan.md`, one `tasks.md`, one checklist), with explicit cross-package ordering and dependencies —
never leave parallel per-package files behind.
