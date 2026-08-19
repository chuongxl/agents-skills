# Shared: Operating Rules (Provider-Agnostic)

These rules bind every provider. Provider adapters (`references/providers/`) add detail but never
weaken a rule here.

## Operating Premise

A real, executable invocation channel always exists in this turn — the `skill` tool, repo
slash-agents (for providers that have them), and file/git tools are callable right now. Loading
this file **is proof**. Categorically forbidden, in any wording: claiming execution is impossible,
fabricated, or channel-less; treating a finished stage, a sub-skill result, or a "handing back"
note as a reason to end the turn; claiming missing persisted state blocks execution. If such a
thought forms, the required tool call simply hasn't been made yet — make it now.

The only valid ways to end a turn anywhere in this pipeline:

1. a concrete tool/runtime error with the error text quoted
2. a genuinely missing required input, after one ask
3. the user explicitly choosing `Stop` at a framework install-recovery ask
4. a mandatory default-mode human checkpoint: any Stage 02 approval interaction, the Stage 02 →
   Stage 03 start-implementation confirmation, or Stage 04
5. Stage 02 self-review failing the same check 3 consecutive times
6. the Stage 03 circuit breaker (identical failure 5× with no file change, or a git/filesystem
   write error)
7. full pipeline completion
8. a completed **setup invocation** (`--integration`), which by design does not run the pipeline

This list is exhaustive.

## Rules

1. **Worktree + branch gate.** Before any pipeline step (framework check, install, intake,
   provider call), create or reuse a linked git worktree on the working branch via real git
   commands. Base branch priority `develop → main → master` (local first, then remote-tracking);
   sync it best-effort (fetch/checkout/pull fast-forward; failure logs a warning and continues
   from the local copy — never a stop). Branch name and artifact folder are the same deterministic
   string once intake resolves it; rename the branch in place (`git branch -m`) when a provisional
   name was used, before any push. All pipeline execution happens inside the worktree, never the
   base checkout. Submodules: branch inside each modified submodule off a synced base, commit
   submodule changes first, then the parent pointer update.

2. **Provider is fixed for the run.** Resolved once from repo-local
   `<repo-root>/.speckit/integration.json` — the only source; there is no global state and no
   first-run prompt (missing file → stop and direct the user to
   `/speckit-auto --integration <provider>`). Never re-read or change it mid-run. Never infer the
   provider from repo contents — a missing framework installation is handled by install recovery,
   never by switching provider.

3. **Provider validation + recovery gate is mandatory at start and at any step.** On every
   pipeline invocation, immediately after provider resolution and before any provider stage work,
   run the framework availability check for that provider (github-speckit agents or superpowers
   skills). Repeat this validation before each later provider invocation in Stage 02/03/04. If
   incomplete/missing at any point, trigger install recovery immediately: fetch the install guide,
   ask the user once (`Install` / `Stop`), and on `Install` perform the install, run the
   provider's mandatory success gates (e.g. `specify init`, the constitution/bootstrap check), run
   post-install validation, re-check, and continue in the same turn. `Stop` halts with a report
   that installation is required.

4. **Post-install validation failure is a hard stop.** If recovery install ran but validation
   still fails (missing provider files/skills, invocation channel/tool resolution failure, or host
   session not ready), do not continue the pipeline. **Stop and ask the user to restart the host
   session (Copilot / Claude Code / OpenCode), then re-run `speckit-auto`.**

5. **Heavy payload prevention.** Pass only the minimum slices each stage needs (current input +
   relevant excerpts + compact project context). Never forward full prior-stage prose. For large
   scope, partition into small packages (see Stage 02/03 partitions) and invoke per package;
   parallel only when dependency-independent, else sequentially in dependency order.

6. **Stage 02 mandatory self-review gate.** Before leaving Stage 02, in both modes: spec coverage,
   placeholder scan (`TODO`/`TBD`/`...`/stubs), consistency, and workspace assignment for every
   task. Fix failures at the source and re-verify; re-run the gate after **any** Stage 02 artifact
   regeneration (including regenerations triggered from Stage 03/04). Same check failing 3
   consecutive times stops and reports. Read-only — never fires an interview.

7. **Stage 02 → 03 handoff is mandatory, never a stop.** Default mode: ask the single
   start-implementation confirmation, then enter Stage 03 in the same turn on approval. `--yolo`:
   skip the confirmation and enter Stage 03 directly. Before entering, commit + push the approved
   Stage 02 artifacts (see Stage 02). Finishing Stage 02 is never by itself a reason to end the
   turn.

8. **Stage 03 is a NO-STOP ZONE** in both modes: no approvals, pauses, interviews, or prompts.
   The only success exit is `status = pass` from `speckit-code-review`; the only other exit is the
   circuit breaker (rule 10). A `failed` review is never a stop condition — it is the input for the
   next fix iteration; apply fixes and loop immediately, never writing a prose summary of a failed
   result. On each retry, rebuild loop context from `state_file` + current `fixes[]` only.

9. **Routing and commits.** Stage 03 pass routes to Stage 04 (default mode; mandatory, never
   skipped) or the YOLO auto-commit (Stage 04 YOLO path). After the implementation commit, mark
   the active spec/design artifact `completed` and make a follow-up commit for that status change.
   Every commit is conditional: check `git status --porcelain` first; an already-clean tree
   ("already committed during Stage 03") is a success path. Sync before push (`pull --rebase`,
   resolve conflicts, continue) and push the feature branch to origin.

10. **Circuit breaker.** Abort Stage 03 only if the exact same failure repeats 5 consecutive
   iterations with no file change between them, or a git/filesystem error prevents writing code.
   Report the stuck state and stop. A differing failure, or one followed by any file edit, does
   not count toward the 5.

11. **Failure ordering and reporting.** Provider validation checks run first (startup and
    pre-invocation at any step); only after they pass may runtime stage-invocation errors be
    reported. Any stage failure, failed required commit, or failed push stops the run with the
    exact error quoted. A skipped commit on an already-clean tree is not a failure.

12. **`--issue` mode record keeping.** The lowercase Jira key is the artifact id prefix and must
    stay stable across reruns (reuse an existing artifact whose name starts with `<issue_id>-`
    rather than deriving a new slug). The ticket snapshot is persisted as `ticket.md` in the
    feature's artifact folder and committed with the other artifacts; it is the record of *what
    was asked* (spec/plan remain the source of truth for *what gets built*) and is never read back
    into run context wholesale. Stage 01 intake has no interview gate — continue to Stage 02
    immediately after input is collected.