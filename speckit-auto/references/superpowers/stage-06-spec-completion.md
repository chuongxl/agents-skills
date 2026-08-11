# Stage 06 (superpowers): Mark Design Spec Completed + Follow-up Commit

Load this only after a successful implementation commit (default or YOLO mode).

## Design Spec Completion

1. Update the active design spec
   `docs/superpowers/specs/<issue_id>-<short_title>-design.md`:
   - if a status field exists → set `completed`
   - else add `Status: completed`

2. Commit this status update:
   - `git add docs/superpowers/specs/<issue_id>-<short_title>-design.md`
   - `git commit -m "chore(spec): mark <issue_id> completed"`

## Wait for Graphify Post-Commit Hook

After committing, graphify may run as a post-commit hook and generate or update files (typically
under `graphify-out/` or similar).

3. Wait for graphify to complete:
   - Wait up to **15 seconds** after the commit.
   - Check for new or modified files using `git status --porcelain`.
   - If untracked or modified files look like graphify output (`graphify-out/`, `*.graph.json`,
     `*.knowledge-graph.*`), proceed to step 4.
   - If nothing appears after 15 seconds, skip step 4 silently and finish.

4. Commit graphify output changes:
   - `git add -A`
   - `git commit -m "chore(graphify): update knowledge graph for <issue_id>"`

## Failure Handling

- If the status update fails, stop and report.
- If the completion commit fails, stop and report.
- If the graphify commit fails, log a warning but do **not** fail the pipeline — the implementation
  is already committed.
- Do not claim pipeline success unless the completion commit (step 2) succeeds.
