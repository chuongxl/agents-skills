# Shared: Operating Rules (Provider-Agnostic)

These rules bind every provider for `speckit-qa-auto`. Provider adapters (`references/providers/`) add detail but never weaken a rule here.

## Operating Premise

A real, executable invocation channel always exists in this turn — the `skill` tool, repo skills, and file/git tools are callable right now. Loading this file **is proof**. Categorically forbidden, in any wording: claiming execution is impossible, fabricated, or channel-less; treating a finished stage, a sub-skill result, or a "handing back" note as a reason to end the turn.

The only valid ways to end a turn in this pipeline:

1. A concrete tool/runtime error with the error text quoted.
2. A genuinely missing required input, after one ask.
3. The user explicitly choosing `Stop` at a framework install-recovery ask.
4. Mandatory human checkpoints: the Stage 02 brainstorming output review/approval interaction, Stage 02 design approval, or Stage 04 final review (default mode).
5. Full pipeline completion.
6. A completed **setup invocation** (`--integration`), which by design does not run the pipeline.

## Rules

1. **Worktree + branch gate.** Before any pipeline step, create or reuse a linked git worktree on the working branch via real git commands. Base branch priority `develop → main → master`. Sync it best-effort. Branch name is `qa/<issue-id>` or `qa/<slug>`.

2. **Provider is fixed for the run.** Resolved once from repo-local `<repo-root>/.speckit/integration.json` — the only source; missing file → stop and direct the user to `/speckit-qa-auto --integration <provider>`.

3. **Provider validation + recovery gate is mandatory.** On every invocation, run the framework availability check for that provider. If incomplete/missing, trigger install recovery.

4. **Post-install validation failure is a hard stop.** If recovery install ran but validation still fails, stop and ask the user to restart the host session.

5. **Stage 02 Brainstorming Gate.** Conduct an interview to clarify scope. Present the full output summary (Recommended Approach, Q&A Summary, Rejected Approaches, Scope/Risk Boundaries) and STOP for explicit human approval before drafting design artifacts.

6. **Stage 03 is a NO-STOP ZONE:** No approvals, pauses, or prompts during automation execution and inline verification. The only exits are verified completion or circuit breaker (5 consecutive identical failures).

7. **Artifacts authority.** `specs/qa/<issue>/` is the source of truth for QA artifacts (`run.json`, `ticket.md`, `test-design.md`, `.feature` files).
