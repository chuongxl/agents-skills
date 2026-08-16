# speckit-auto worktree support test cases

Scope: validate Stage 01 worktree-based isolation, branch/worktree alignment, and rerun behavior for both `github-speckit` and `superpowers`.

| ID | Scenario | Preconditions | Steps | Expected result | Provider coverage |
|---|---|---|---|---|---|
| WT01 | Stage 01 creates linked worktree | Inside git repo; no existing feature branch/worktree | Run `/speckit-auto "<requirement>"` | Creates branch and linked worktree at `<repo-root>/.worktrees/<branch-name>` before any provider preflight/intake | Both |
| WT02 | Stage 01 reuses existing branch + worktree on rerun | Branch and canonical worktree already exist | Re-run same feature command | Reuses existing linked worktree, does not create suffix branch, continues pipeline | Both |
| WT03 | Existing branch without linked worktree | Feature branch exists; no linked worktree for it | Run same feature command | Adds linked worktree at canonical path and continues on it | Both |
| WT04 | Canonical worktree path ignore enforcement | `.gitignore` exists and misses `.worktrees/` | Run Stage 01 | Appends `.worktrees/` to `.gitignore` (no separate commit step) | Both |
| WT05 | `.gitignore` bootstrap for worktree root | `.gitignore` absent | Run Stage 01 | Creates `.gitignore` containing `.worktrees/` and proceeds | Both |
| WT06 | Base branch resolution priority | Multiple base branches available | Run Stage 01 | Selects base in order: `develop` → `main` → `master` | Both |
| WT07 | Base sync fallback | Fetch/pull fails (offline/no remote/conflict) | Run Stage 01 | Logs warning and continues from local base copy (not a hard stop) | Both |
| WT08 | Missing base branch hard failure | None of `develop/main/master` exist | Run Stage 01 | Stops with explicit missing base branch error | Both |
| WT09 | Stage order gate | Normal invocation | Run `/speckit-auto ...` | No provider source/availability check, install recovery, or intake occurs before worktree+branch setup finishes | Both |
| WT10 | Provisional naming in Jira mode | `--issue` mode; full slug not yet resolved at gate | Run Stage 01 | Uses provisional `<issue_id>` branch/worktree, then renames/moves after intake resolves `<issue_id>-<short_title>` | Both |
| WT11 | Provisional naming in manual mode | Manual requirement; final numbered slug unresolved at gate | Run Stage 01 | Uses provisional requirement-slug branch/worktree, then aligns to final `<NNN>-<slug>` after intake | Both |
| WT12 | Artifact rerun stability mapping | Existing artifact folder for issue | Re-run same issue with changed Jira title | Reuses prior `<issue_id>-<short_title>` identity; branch/worktree align to existing artifact identity | Both |
| WT13 | Rename alignment (branch) | Provisional branch differs from final name | Continue through intake resolution | Executes `git branch -m <final-name>` inside linked worktree and updates run state | Both |
| WT14 | Rename alignment (worktree path move success) | Worktree path differs from canonical final path | Continue through intake resolution | Moves linked worktree to `<repo-root>/.worktrees/<final-name>` and updates `worktree_path` | Both |
| WT15 | Rename alignment (worktree path move failure) | Worktree move blocked (filesystem/lock) | Continue through intake resolution | Logs warning, continues on current path, keeps pipeline running | Both |
| WT16 | Run-state bootstrap includes worktree path | No persisted run state | Start pipeline | Initializes `worktree_path` in in-memory state and sets it after setup | Both |
| WT17 | Global rule enforcement: no base checkout implementation | Stage 03 begins | Run implementation stage | Implementation executes from Stage 01 linked worktree, never from base checkout path | Both |
| WT18 | superpowers Stage 01 avoids nested worktree creation | `superpowers` selected | Run Stage 01 and Stage 03 entry | Uses shared Stage 01 worktree; does not invoke another worktree setup in provider stages | superpowers |
| WT19 | github-speckit Stage 01 uses shared worktree gate | `github-speckit` selected | Run Stage 01 | Uses shared worktree+branch gate before Speckit source check and intake | github-speckit |
| WT20 | Parallel-session isolation | Two features started from same repo | Run two pipeline invocations with different requirements | Each run gets separate linked worktree path under `.worktrees/`; no workspace collision | Both |
| WT21 | speckit-code-review runs on worktree change set | Stage 03 loop reaches review step | Invoke `speckit-code-review` per Stage 03 rules | Runs inline (never a background task) with cwd inside the Stage 01 linked worktree; its `git status`/`git diff HEAD` scope and the explicitly passed `specs/<feature>/spec.md` resolve against the worktree branch, never the base checkout | Both |

## Minimum pass criteria

- All Stage 01 invocations establish or reuse linked worktree isolation before provider-specific actions.
- Branch name, worktree path, and artifact folder identity converge to the same final feature key after intake resolution.
- Reruns remain stable (reuse branch/worktree/artifact identity) and never create duplicate suffix branches for the same feature.
- Both providers follow the same shared worktree contract, differing only in provider-specific preflight checks.
