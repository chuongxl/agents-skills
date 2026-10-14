# Shared: Run Contract (Provider-Agnostic)

The always-loaded invariants — the only file loaded eagerly at entry besides `SKILL.md`. Stage
files own their own procedures; this file never repeats them. Provider adapters add detail but
never weaken a rule here.

## Operating Premise

A real, executable invocation channel always exists in this turn — the `skill` tool and the
file/git tools are callable right now. Loading this file **is proof**. Categorically forbidden, in
any wording: claiming execution is impossible, fabricated, or channel-less; treating a finished
stage, a sub-skill result, or a "handing back" note as a reason to end the turn; claiming missing
persisted state blocks execution. If such a thought forms, the required tool call simply hasn't
been made yet — make it now.

## Turn-End Whitelist (exhaustive)

1. a concrete tool/runtime error, with the error text quoted
2. a genuinely missing required input, after one ask
3. the user explicitly choosing `Stop` at an install-recovery ask
4. a mandatory default-mode human checkpoint: a Stage 02 approval interaction, the Stage 02 →
   Stage 03 start-implementation confirmation, or Stage 04
5. Stage 02 self-review failing the same check 3 consecutive times
6. the Stage 03 circuit breaker (identical failure 5× with no file change, or a git/filesystem
   write error)
7. full pipeline completion
8. a completed setup invocation (`--integration`), which by design does not run the pipeline

## Rules

1. **Worktree first.** No pipeline step (framework check, install, intake, provider call) runs
   before the Stage 01 worktree + branch gate completes. All execution happens inside the
   worktree, never the base checkout.

2. **Provider is fixed for the run.** Resolved once from `<repo-root>/.speckit/integration.json`
   — the only source; no global state, no first-run prompt. Never re-read or change it mid-run,
   and never infer it from repo contents: a missing framework installation is handled by install
   recovery, never by switching provider.

3. **Provider validation is mandatory** at startup and before each later provider invocation. If
   the provider's skills are missing/unresolvable at any point, trigger the adapter's install
   recovery immediately and continue in the same turn once it passes.

4. **Post-install validation failure is a hard stop.** If recovery ran but validation still
   fails, stop and ask the user to restart the host session, then re-run `speckit-auto`.

5. **Heavy payload prevention (context + prompts).** Pass only the minimum slices a step needs
   (current input + relevant excerpts + compact project context); never forward full prior-stage
   prose. Load a reference file only when the current step actually needs it, never load the
   unselected provider's files, and never re-load a file already in context. For large scope,
   partition into small packages and invoke per package — parallel only when
   dependency-independent.

6. **Stage 02 never exits with a failing self-review gate**, and that gate re-runs after **any**
   Stage 02 artifact regeneration, including ones triggered from Stage 03 or Stage 04.

7. **The Stage 02 → 03 handoff is never a stop.** Finishing Stage 02 is not by itself a reason to
   end the turn.

8. **Stage 03 is a NO-STOP ZONE** in both modes. The only success exit is `status = pass` from
   `speckit-code-review`; the only other exit is the circuit breaker. A `failed` review is the
   input for the next fix iteration, never a stop.

9. **Every commit is conditional**: check `git status --porcelain` first; an already-clean tree is
   a success path, not a failure. Sync before push, and push the feature branch to origin.

10. **Failure ordering.** Provider validation runs before any runtime stage error is reported. Any
    stage failure, failed required commit, or failed push stops the run with the exact error
    quoted.

11. **`--issue` record keeping.** The lowercase Jira key is the artifact id prefix and stays
    stable across reruns. The ticket snapshot lives at `<artifact_folder>/ticket.md`, is committed
    with the other artifacts, and is never read back into context wholesale. Stage 01 intake has
    **no interview gate** — continue to Stage 02 immediately after input is collected.

## Event ordering, questions, and exits

After Stage 01 initializes the producer, every instruction to emit uses the exact Node builtin
JSON stdin invocation in `run-events.md`, with the retained helper path, worktree, and UUID.
An event is a real tool call, never a prose claim. Keep the source repo, actual worktree,
run ID, issue key, and helper path across stage/context transitions. Resume validates `init`
and recorded history without replaying already-recorded boundaries or answers. A fresh retry
gets a new ID and append-only history; a terminal run cannot resume under its old ID.

For every pipeline-owned question, including install-recovery choices, Jira missing-input
questions, clarification interviews, change details, constraints, commit-message asks, and
optional branch-lifecycle choices: emit `question_waiting` immediately before the actual ask,
then `stage_started` for the active stage immediately after the response and before continuing.
Named approvals instead use `gate_waiting` and `gate_answered`. Never double-wrap an ask with
both types. Use deliberately composed questions and bounded option labels, never raw answers,
feedback, credentials, tool output, file contents, or arbitrary prompts. Do not emit waiting
while a provider is still generating an artifact. Pass the same bracketing rule to an invoked
provider/sub-skill for the actual questions it asks on behalf of the pipeline.

YOLO emits no waiting events for skipped human gates and stays non-interactive in Stage 02/04.
Existing install-recovery or genuinely missing-required-input asks, if needed, are still
instrumented when initialized; instrumentation does not bypass an existing hard prerequisite.
Stage 03 remains a no-question zone. Waiting for input/approval is not a failed run.

Before an explicit terminal exit after init, emit exactly one `run_failed` with a composed,
single-line reason after applying required provider recovery. Use `git_error` for required
git/commit/push errors; `review_loop_stuck` for exhausted refinement or stalled reviews;
`tests_failing` for a terminal test blocker; `policy_blocked` for unrecoverable prerequisites,
permission denials, or an install Stop choice; `budget_exceeded` only for an actual reported
budget stop; `crashed` for other unrecoverable tool/runtime/filesystem failures. This adds no
budget enforcement or new review-loop exits. An uncatchable host crash cannot emit and is
diagnosed by the client session lifecycle. Pre-init errors have no event file.

Failed event validation/write is itself a hard instrumentation error: report it and stop.
Never recurse trying to emit failure on the same broken writer, fall back to prose, or claim
completion after a write error. A warning, recoverable failure, clean-tree commit skip, or
Request changes is not `run_failed`. Only successful Stage 04 may emit `run_completed`, after
required commits/push and spec completion; do not emit any event after a terminal record.

## Invocation Channel (canonical)

All skills — including `speckit-*` — are invoked via the `skill` tool by name, on every host
(on Hermes Agent this is the `skill_view` tool — see references/shared/host-adaptation.md). The
`skill` tool is **synchronous**: it returns inline in the same turn, so a skill call is never a
turn boundary. Never use the `task` tool with a skill name; never shell out to a `copilot` /
`claude` / `opencode` / `hermes` CLI subprocess; never emit `@speckit.*` or `/speckit.*`. If the
skill tool cannot resolve a provider skill, that is a provider validation failure (rule 3), not a
stop.
