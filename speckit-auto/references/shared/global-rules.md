# Shared: Global Rules (Provider-Agnostic)

These rules bind every provider. Provider-specific rules live in that provider's stage files and
may add detail, but may never weaken a rule here.

## Absolute Operating Premise (Overrides Everything Below)

A real, executable invocation channel always exists in this session: `skill`, `task`, repo
slash-agents (for providers that have them), and file-editing/bash tools are genuinely callable
right now, in this turn. Loading this skill file **is proof** the channel is present.

**Categorically forbidden**, in any wording: claiming execution is impossible, fabricated, or lacks
a channel; claiming a stage/sub-skill result requires stopping and waiting for the user; claiming
missing persisted state/history blocks execution. None of these are valid conclusions — if such a
thought forms, it means a required tool call hasn't been made yet. Make it now.

The only valid ways to end a turn anywhere in this pipeline are:
- a concrete tool/runtime error with quoted error text
- a genuinely missing required input, after one ask
- the user explicitly choosing `Stop` at the framework install-recovery ask (rule 7)
- the user explicitly choosing `Stop` at the workspace risk-confirmation ask (rule 1a)
- `--yolo` meeting a dirty umbrella in a `.gitmodules` repo, or any dirtiness under an explicit
  `--no-worktree`, where no isolation is available and no human can confirm (rule 1a)
- a workspace rerun-reuse validation failure (rule 1b)
- a submodule leak-guard failure before commit (rule 23a)
- a mandatory human checkpoint in default mode: any Stage 02 approval interaction (a provider
  post-stage interview, `brainstorming`'s own approval and its delegation fallback, and the
  Stage 02 → Stage 03 start-implementation confirmation), or Stage 04
- Stage 02 retry exhaustion: the same self-review or stage check fails 3 consecutive times
- the Stage 03 circuit breaker in rule 20 (identical failure 5× with no file change)
- full pipeline completion
- a completed **setup invocation** (`--integration`), which by design does not run the pipeline

This list is exhaustive. Finishing one stage, one sub-skill call (including `jira-to-speckit`), or
seeing a "next action"/"handing back" note in output is never itself a stop condition — treat it as
data and immediately invoke the next required step, in the same turn.

## Non-Negotiable Rules

1. Always create the workspace and check out the working branch — a hard gate via real git commands (not merely described) — **after** intake resolves the final feature name and **before** any business-code write or the provider's Stage 02 entry step. Only the framework source check, install recovery, guidelines load, and intake may precede it; all four are read-only with respect to business code. The workspace is created once, with the final feature name: there is no provisional branch name, no `git branch -m`, and no `git worktree move`. See [branching.md](branching.md).
1a. `workspace_strategy` defaults to `worktree`; `--no-worktree` selects `branch` (branch in-place). No strategy ever worktrees the umbrella of a `.gitmodules` repo — the umbrella stays on an in-place feature branch in both, and the default isolates only the submodules named by the plan, never running recursive submodule init/update. Because the umbrella is always in-place there, an uncommitted umbrella change is a live risk on the default path. When the working tree is dirty, the confirmation ask and its `--yolo` resolution follow the per-level tables in [branching.md](branching.md); `--yolo` never overrides an explicit `--no-worktree`.
1b. Reusing an existing branch or worktree on a rerun requires passing the rerun-reuse validation checklist in [branching.md](branching.md). Stale or mismatched state stops with the exact reason; it is never silently reused.
2. Base branch priority is `develop → main → master` (local first, then remote-tracking). Sync that base to latest before branching off it — for the main repo, and for any modified submodule in `branch` mode. The sync is best-effort: a fetch/pull failure logs a warning and continues from the local copy, and is never a stop. In `worktree` mode a submodule's original checkout is **fetch-only**: checkout, pull, reset, or any command that changes its working tree or HEAD is forbidden. See [branching.md](branching.md).
3. Root-level artifact and umbrella commands run in `workspace_root`. Any command targeting a mapped submodule path must run in that submodule's mapped workspace from `submodule_workspaces{}` — this covers reads, writes, tests, lint, `status`, `diff`, and `commit`, not just file edits. Never run implementation stages from a path that is neither.
4. In `--issue` mode, the lowercase Jira issue key is the artifact id prefix and must stay stable across reruns. See [intake.md](intake.md).
4a. **In `--issue` mode the ticket must be persisted as `ticket.md` in the feature's artifact folder** and committed with the other artifacts, so spec/plan decisions can be traced back to the original request. Spec and plan remain the source of truth for *what gets built*; `ticket.md` is the record of *what was asked*. It is written by `jira-to-speckit` to a staging path and relocated once the artifact folder exists; it is never read back into run context wholesale. See [intake.md](intake.md).
5. Stage 01 intake has **no interview gate**. After input is collected, continue immediately to the provider's Stage 02 entry step.
6. Never stop with a capability/no-channel disclaimer, an intent-only acknowledgement, a "please re-run the command" block, or a prose report of a stage/sub-skill's own "next action" note — see the Absolute Operating Premise above.
7. If the selected provider's framework is not installed, that provider's Stage 01 preflight must run install recovery — fetch the install guide, ask the user once to `Install` or `Stop`, and on `Install` perform installation and continue in the same turn. A missing framework is never a reason to switch provider, and the ask is a required-input ask, not a capability disclaimer.
8. **Heavy payload prevention is mandatory.** For each stage, pass only the minimum required slices (current stage input + relevant excerpts + compact project context). Never forward full prior stage prose when not needed.
9. For large scope (large requirement, many tasks, or many workspaces), split work into small packages and invoke the provider's implementation step multiple times per package until complete.
10. For split work, run packages in parallel only when dependency-independent; otherwise run sequentially in dependency order.
10a. Before leaving Stage 02, the provider's **Mandatory Self-Review Gate** must pass in **both** modes (spec coverage, placeholder scan, consistency, workspace assignment). A failing gate is fixed at the source and re-verified. Re-run it after **any** Stage 02 artifact regeneration, including regenerations triggered from Stage 03 or Stage 04. The gate is read-only and never fires an interview, so it does not violate rule 11. Retry exhaustion is provider-independent: the same check failing 3 consecutive times stops and reports.
10b. Entering Stage 03 is a **mandatory handoff**, never a stop. In default mode, ask the single Stage 02 → Stage 03 start-implementation confirmation, then enter Stage 03 in the same turn on approval. In `--yolo` mode, skip that confirmation and enter Stage 03 directly. Finishing Stage 02 is never by itself a reason to end the turn. See the provider's Stage 03 Entry Step.
11. **Stage 03 is a NO-STOP ZONE in BOTH default and `--yolo` modes.** No human approval gates, no pauses, no prompts fire inside Stage 03. This overrides all interview-flow and mode-based gate rules. The only *success* exit is `status = pass` from `speckit-code-review`; the only other permitted exit is the rule 20 circuit breaker. This is the canonical statement of the no-stop rule — stage files reference it rather than restating exceptions.
12. **A `failed` result from `speckit-code-review` is NEVER a stop condition in any mode.** Do NOT produce a prose summary of the result. Do NOT end the turn. Immediately apply fixes and loop again.
13. For code-only or test-coverage failures, directly edit the specific files named in the review result (`suggested_fix_area`, `file`, `method/function`) using file-editing tools, in the same turn. Do NOT delegate to the provider's implementation step.
14. Apply fixes, re-run `speckit-code-review`, and repeat until `status = pass`.
15. After Stage 03 exits with `pass`, routing is mandatory: default mode → Stage 04; `--yolo` mode → Stage 05.
16. In default mode, Stage 04 is mandatory and must never be skipped.
17. In `--yolo` mode, skip all human review interactions including Stage 04.
18. After a successful implementation commit, mark the active spec/design artifact as `completed` and create a follow-up commit for that status change.
19. If any stage, status update, or required commit fails, stop and report the exact failure.
20. Circuit breaker — the only non-`pass` exit from Stage 03: abort only if the **exact same failure repeats for 5 consecutive iterations** with no file change between them, or a git/filesystem error prevents code from being written. Report the stuck state and stop. A failure that differs, or that was followed by any file edit, does not count toward the 5.
21. On every failed review retry, rebuild the loop context from `state_file` plus the current `fixes[]` only; do not retain the full prior review body or earlier category detail files unless needed for the next fix.
22. Failure ordering is strict: first run framework install/source checks; only after those pass may runtime stage-invocation errors be reported.
23. If implementation modifies git submodule repositories, isolate each modified submodule per `workspace_strategy` — an in-place branch in `branch` mode, a grafted worktree under `.worktrees/<feature>/apps/<name>` in `worktree` mode — and commit submodule changes first, then commit parent repo pointer updates. See [branching.md](branching.md).
23a. In `worktree` mode, before the Stage 04/05 commit, compare each original submodule checkout's `git status --porcelain` against the baseline captured at graft time. Entries that are new or changed relative to that baseline mean writes leaked to the wrong checkout: stop and report the exact paths. Entries identical to the baseline are the user's pre-existing work and are left alone. See [branching.md](branching.md).
24. The provider is resolved once per run from `integration.json` and never changes mid-run. See [../integration-mode.md](../integration-mode.md).
