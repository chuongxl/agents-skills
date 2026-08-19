# Shared: Run-State Contract

Needs at load time: nothing. This file is a leaf — it links to no other file, and reads none.

## Overview

Stages hand off through state written to disk, never through each other's prose. This file is
that state's data shape: the one contract every stage reads and writes, so a stage can be
rewritten without touching its neighbours.

## Where It Lives

`docs/qa/<jira-key>-<slug>/execution-report.md` carries this as a fenced `yaml` block. There is
one run-state block per artifact folder, updated in place as the run progresses.

## Field Reference

```yaml
run:
  jira_key:            MOM-1234
  slug:                agreement-reset-button
  artifact_dir:        docs/qa/mom-1234-agreement-reset-button
  branch:              test/mom-1234-agreement-reset-button
  worktree_path:       .worktrees/test/mom-1234-agreement-reset-button
  mode:                default | yolo
  full_suite:          false
  stage:               01 | 02 | 03 | 04 | completed
  resume_from:         02

profile:
  # every field re-derived each run from the playbook; see repo-profile.md
  source_paths:        [".github/skills/mom-auto-testing/SKILL.md", "package.json"]

baselines:
  workspace_baseline:  {path, head_sha, worktree_diff_sha256, index_diff_sha256, untracked}
  frontend_baseline:   {path, head_sha, worktree_diff_sha256, index_diff_sha256, untracked}
  frontend_edits_approved: false

xray:
  query:               testRequirement | linkedIssues | not-run
  cucumber_tests:      12
  manual_tests:        7
  dedup:               ran | not-run

design:
  selector_evidence:   source | live-dom | fallback
  scenarios:
    - name:            Verify the Reset button is renamed
      surface:         ui | api | manual
      dedup:           NEW | UPDATE MOM-5678 | SKIP MOM-5678 | REVIEW MOM-5678
      status:          pending | green | blocked
      blocked_reason:  needs-design-change
      attempts:        0
      commit:          <sha the result was produced on>
```

## Rules

1. `worktree_path` is always `<repo-root>/.worktrees/<branch>` with the branch name used
   verbatim. A branch name containing `/` therefore nests. Derive it; never re-spell it — the
   example above is an instance of the rule, not the rule itself.
2. A stage reads only this file and the artifact folder. **It never reads another stage's
   reference file.**
3. A field absent from this contract does not travel between stages. Adding one means editing
   this file first.
4. `status: green` is only ever written next to the commit sha the run was produced on. A result
   with no sha is not a result.
