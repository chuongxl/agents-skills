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
- a mandatory human checkpoint in default mode (Stage 04)
- the Stage 03 circuit breaker in rule 20 (identical failure 5× with no file change)
- full pipeline completion
- a completed **setup invocation** (`--integration`), which by design does not run the pipeline

This list is exhaustive. Finishing one stage, one sub-skill call (including `jira-to-speckit`), or
seeing a "next action"/"handing back" note in output is never itself a stop condition — treat it as
data and immediately invoke the next required step, in the same turn.

## Non-Negotiable Rules

1. Always create/switch a new branch before the first pipeline step — a hard gate via real git commands (not merely described); no framework source check, install, intake, or provider stage call may run first. See [branching.md](branching.md).
2. Base branch priority is `develop → main → master` (local first, then remote-tracking). Sync that base to latest before branching off it — for the main repo and for any modified submodule. The sync is best-effort: a fetch/pull failure logs a warning and continues from the local copy, and is never a stop. See [branching.md](branching.md).
3. Git worktrees are never used, in any provider. This is the canonical statement of that rule.
4. In `--issue` mode, the lowercase Jira issue key is the artifact id prefix and must stay stable across reruns. See [intake.md](intake.md).
5. Stage 01 intake has **no interview gate**. After input is collected, continue immediately to the provider's Stage 02 entry step.
6. Never stop with a capability/no-channel disclaimer, an intent-only acknowledgement, a "please re-run the command" block, or a prose report of a stage/sub-skill's own "next action" note — see the Absolute Operating Premise above.
7. If the selected provider's framework is not installed, that provider's Stage 01 preflight must run install recovery — fetch the install guide, ask the user once to `Install` or `Stop`, and on `Install` perform installation and continue in the same turn. A missing framework is never a reason to switch provider, and the ask is a required-input ask, not a capability disclaimer.
8. **Heavy payload prevention is mandatory.** For each stage, pass only the minimum required slices (current stage input + relevant excerpts + compact project context). Never forward full prior stage prose when not needed.
9. For large scope (large requirement, many tasks, or many workspaces), split work into small packages and invoke the provider's implementation step multiple times per package until complete.
10. For split work, run packages in parallel only when dependency-independent; otherwise run sequentially in dependency order.
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
23. If implementation modifies git submodule repositories, branch inside each modified submodule and commit submodule changes first, then commit parent repo pointer updates. See [branching.md](branching.md).
24. The provider is resolved once per run from `integration.json` and never changes mid-run. See [../integration-mode.md](../integration-mode.md).
