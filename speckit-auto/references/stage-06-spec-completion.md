# Stage 06: Mark Spec Completed + Follow-up Commit

Load this only after successful implementation commit (default or YOLO mode).

## Spec Completion

1. Update active feature `spec.md`:
   - if status field exists -> set `completed`
   - else add `Status: completed`

2. Commit this status update:
   - `git add <active-spec-path>/spec.md`
   - `git commit -m "chore(spec): mark <spec-id> completed"`

## Wait for Graphify Post-Commit Hook

After committing, graphify may run as a post-commit hook and generate or update files (typically under `graphify-out/` or similar).

3. Wait for graphify to complete:
   - Wait up to **15 seconds** after the commit.
   - Check for new or modified files using: `git status --porcelain`
   - If untracked or modified files exist that look like graphify output (e.g. `graphify-out/`, `*.graph.json`, `*.knowledge-graph.*`), proceed to step 4.
   - If nothing appears after 15 seconds, skip step 4 silently and finish.

4. Commit graphify output changes:
   - `git add -A` (stage all new/modified graphify-generated files)
   - `git commit -m "chore(graphify): update knowledge graph for <spec-id>"`

## Failure Handling

- If spec status update fails, stop and report.
- If the spec completion commit fails, stop and report.
- If the graphify commit fails, log a warning but do **not** fail the pipeline — the feature implementation is already committed.
- Do not claim pipeline success unless the spec completion commit (step 2) succeeds.
