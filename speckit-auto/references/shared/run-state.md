# Shared: Run-State Persistence (Stage-Boundary Compaction)

This reference defines the `.speckit/run-state.json` format and the persist/resume protocol.
The run-state file lives **inside the Stage 01 linked worktree** (at `<worktree_path>/.speckit/run-state.json`),
so it is automatically discarded if the worktree is deleted.

## Run-State Format

```json
{
  "version": 1,
  "worktree_path": "/path/to/.worktrees/<branch>",
  "current_stage": "stage-02",
  "integration": "github-speckit",
  "mode": "default",
  "issue_key": "DDM-1234",
  "artifact_folder": "specs/ddm-1234-create-and-save-customized-filter",
  "project_context": {
    "summary": "...",
    "repo_map": { "backend": "...", "frontend": "..." },
    "linked_guidelines": { "architecture": "path/to/architecture.md" },
    "loaded_guidelines": {}
  },
  "spec_path": "specs/<issue_id>-<short_title>/spec.md",
  "plan_path": "specs/<issue_id>-<short_title>/plan.md",
  "tasks_path": "specs/<issue_id>-<short_title>/tasks.md",
  "ticket_path": "specs/<issue_id>-<short_title>/ticket.md",
  "execution_report_path": "specs/<issue_id>-<short_title>/execution-report.md",
  "stage_01_completed_at": "2026-08-16T07:00:00Z",
  "stage_02_completed_at": null,
  "stage_03_completed_at": null,
  "last_reviewed_sha": null,
  "review_invalidate": null
}
```

All paths are **relative to the worktree root**. `project_context` is the same object built in
Stage 01 from `docs/guidelines/architecture.md` (see
[preflight-guidelines-context.md](preflight-guidelines-context.md)); it is cached here so later
stages can load it without re-reading the guideline file. `last_reviewed_sha` is the git commit the
last `speckit-code-review` pass covered (initialized to the base-branch merge-base at Stage 03
entry and updated to `HEAD` after every review pass, pass or fail); Stage 03 uses it to compute the
incremental `scope` so retries re-read only files changed since the last review. `review_invalidate`
is the granular invalidation token (`spec` | `plan` | `tasks` | `null`) set after a Stage 02
artifact regeneration; the next review pass gets it as `invalidate`, and it is cleared once the
affected scope has been re-implemented and re-reviewed.

Provider note: `github-speckit` produces `spec.md`, `plan.md`, `checklist.md`, and `tasks.md`
(`tasks_path` set); `superpowers` produces only `spec.md` and `plan.md` — the task breakdown lives
inside `plan.md`, so `tasks_path` is `null` and any task-level change is a `plan`-level change.

## Persist Protocol

Save run-state at these points (write the full JSON, never append):

1. **After Stage 01 completes** — worktree exists, intake done, project context built, artifact
   folder created. Set `current_stage: "stage-02"`.
2. **After Stage 02 completes** — spec, plan, tasks, analyze all pass self-review gate.
   Set `current_stage: "stage-03"`, set `stage_02_completed_at`.
3. **After Stage 03 completes** — code review passed, implementation committed.
   Set `current_stage: "stage-04"` (default) or `"stage-05"` (yolo), set `stage_03_completed_at`.

The persist call is a single `bash` invocation:

```bash
mkdir -p <worktree_path>/.speckit && cat > <worktree_path>/.speckit/run-state.json << 'EOF'
{ ... }
EOF
```

Never skip a persist because "the context still has it" — on stateless API hosts the transcript
is cumulative but the model's attention to earlier content degrades; the run-state file is the
authoritative resume point.

## Resume Protocol

On every invocation of `speckit-auto` (entry dispatch step 1, after host detection):

1. Check for a linked worktree via `git worktree list` (same scan as
   [branching.md](branching.md)).
2. If a worktree exists AND `<worktree_path>/.speckit/run-state.json` exists:
   a. Read the run-state file.
   b. Validate `version` is supported (currently 1).
   c. Confirm `worktree_path` matches the discovered worktree (stale state = delete and re-run
      Stage 01).
   d. Load `project_context` from run-state (skip re-reading `architecture.md`).
   e. Set `integration`, `mode`, `issue_key` from run-state.
   f. Jump directly to the stage named in `current_stage` — load that stage's reference file
      and continue. Do NOT re-run Stage 01 or ask the user to re-provide inputs.
3. If no run-state file exists (or validation fails): run Stage 01 from scratch.

## Stage-Transition Save Points (Where Each Stage Persists)

Each stage file must include a "Persist run-state" step as its **last action** before declaring
completion. The step writes the updated JSON with the next `current_stage` value and the
completed-at timestamp for the finishing stage.

Stage files reference this shared document rather than restating the full format:

> **Persist run-state:** save current state to `<worktree_path>/.speckit/run-state.json`
> per [run-state.md](run-state.md); set `current_stage` to the next stage.

## Worktree Path in Run-State

The `worktree_path` field is critical: it tells the resume logic which worktree to `cd` into
before loading any stage file. All stage calls must execute from the worktree — never from the
base checkout path (global rule 3). If `worktree_path` in the run-state does not match a
currently-linked worktree, the state is stale and Stage 01 must re-run.

## Interaction with Global Rules

- **Rule 1** (worktree gate): satisfied by the bootstrap script or manual setup in Stage 01;
  resume skips this because the worktree already exists.
- **Rule 3** (always run from worktree): the resume protocol ensures `worktree_path` is loaded
  from run-state and all subsequent calls execute from it.
- **Rule 8** (heavy payload prevention): run-state replaces re-sending full project context;
  only the current stage's reference files are loaded on top.
