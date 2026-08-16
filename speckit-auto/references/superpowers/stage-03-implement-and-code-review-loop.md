# Stage 03 (superpowers): Implement + Verify + Auto Code Review Loop

Load this only when running implementation and review.
Discard review-interview.md from context at this point — Stage 03 is a NO-STOP ZONE.

## Repository-Aware Implementation

Before invoking the implementation skill, inject into its input:

- the `summary` from the Project Context loaded in Stage 01
- the `repo_map`, so each file lands in the correct workspace
- any relevant guideline from `loaded_guidelines` matching the task topic (match by stem key in
  `linked_guidelines`; if matched and not yet cached, load it now and add it to `loaded_guidelines`)
- the plan path `specs/<feature_folder>/plan.md`

## Invocation Method (Critical)

Invoke every superpowers step and `speckit-code-review` through the `skill` tool, per
[provider-rules.md](provider-rules.md) (name resolution + Task Tool section). The skills these steps
dispatch subagents from — `subagent-driven-development`, `requesting-code-review` — are required
here; never suppress them.

| Step | Skill |
|------|-------|
| Implementation (subagents available) | `subagent-driven-development` |
| Implementation (no subagents) | `executing-plans` |
| Per-step TDD | `test-driven-development` |
| Root-cause debugging | `systematic-debugging` |
| Native review pass | `requesting-code-review` |
| Review response discipline | `receiving-code-review` |
| Completion evidence gate | `verification-before-completion` |

`speckit-code-review` must run **inline** (never as a background agent/task) and must always be
given the spec path explicitly: `specs/<feature_folder>/spec.md` — an ambiguous match makes it ask
the user, a turn-ending stop inside this NO-STOP ZONE. On retry iterations, also pass the previous
review's `state_file` path so the review runs in its selective area-loading mode. That spec is a
`brainstorming` design document with no `FR-*`/`NFR-*` IDs; the review skill synthesizes the
checklist itself, so never pre-convert the spec to add IDs.

Never stop with a generic runtime/capability disclaimer before attempting the real call.

## Execution Style Selection

Choose once, at Stage 03 entry, and keep it for the whole run:

- Prefer `subagent-driven-development` (fresh implementer per task, two-stage review).
- Fall back to `executing-plans` if subagent dispatch is unavailable or fails.

State the choice in the skill input. `writing-plans` may have printed its own "two execution
options" handoff at the end of Stage 02 — that was suppressed there and does not decide anything
here.

## Implementation Skill Boundaries (Both Styles)

Pass these into the implementation skill as explicit constraints. Each one overrides a step the
skill would otherwise take on its own:

1. **Workspace** — the current Stage 01 linked worktree is the isolated workspace.
   `subagent-driven-development` opens by requiring an isolated workspace, "created or verified";
   the verify arm is satisfied. Do not create or enter a second git worktree, and do not stop to
   ask which workspace to use.
2. **No branch finish** — the skill's terminal step ("final review clean → delete this plan's
   workspace → use `finishing-a-development-branch`") is **suspended**. Returning means "continue
   Stage 03", never "the branch is done". No PR, no merge, no branch deletion, no workspace
   deletion here. Stage 04/05 owns all of that.
3. **Commits are expected** — the implementer subagents commit per task. That is normal and must
   not be suppressed; Stage 04/05 handles an already-clean tree (see those stages). Record the SHA
   of the branch point before the first dispatch (below) so the review range stays correct.
4. **No completion claim ends the stage** — the skill reporting "all tasks complete" is input to
   PHASE 1 step C2, not an exit.

## Review Range (`BASE_SHA` / `HEAD_SHA`)

Record once, at Stage 03 entry, before any implementation dispatch:

```bash
BASE_SHA=$(git merge-base HEAD <base-branch>)   # base-branch from shared/branching.md
```

`HEAD_SHA=$(git rev-parse HEAD)` is re-read fresh at each R0.

Never use `HEAD~1` as `BASE_SHA` — `requesting-code-review` suggests it as a default, but it
silently drops every commit but the last, and with `executing-plans` (which may not commit per
task) it can produce an **empty diff**, yielding a "clean" review that reviewed nothing.
If `BASE_SHA` and `HEAD_SHA` resolve to the same commit at R0, nothing is committed yet. Check
`git status --porcelain`:
- **Dirty tree** (the `executing-plans` case — it may not commit per task): the work exists but is
  uncommitted. Commit it as `chore(<feature>): checkpoint implementation` so the diff is reviewable,
  re-read `HEAD_SHA`, and continue with R0. Never return to PHASE 1 over this.
- **Clean tree**: nothing was implemented — return to PHASE 1 step C1 once. If PHASE 1 completes
  again and the range is still empty with a clean tree, that is a stalled implementation: apply the
  global rule 20 circuit breaker rather than looping C1 → R0 indefinitely.

## Mandatory TDD

Every implementation step runs `test-driven-development`:
RED (write the failing test and watch it fail) → GREEN (minimal code, watch it pass) → REFACTOR.
Code written before its test must be deleted and redone. This applies to fix iterations too.

When a test fails unexpectedly or a bug appears, run `systematic-debugging` — never
apply a fix without an identified root cause.

## Git Submodule Branch Handling

See [../shared/branching.md](../shared/branching.md) — "Git Submodule Branch Handling". No
superpowers-specific deviation.

## Heavy Payload Prevention + Implementation Partitioning

When implementation scope is large, load [../shared/partitioning.md](../shared/partitioning.md) and
apply it, building `implementation_packages[]` from the plan's tasks grouped by `workspace` +
bounded capability, and invoking the implementation skill once per package until the queue is empty.
Use `dispatching-parallel-agents` when parallelizing.

## NO-STOP ZONE (canonical: global rules 11–12, 20)

Stage 03 runs autonomously in both modes — no human gates, no interviews, no pauses, no
report-and-stop on a failed result. The only success exit is `status = pass` from
`speckit-code-review`; the only other permitted exit is the global rule 20 circuit breaker. A
`failed` result is the input for the next fix iteration.

Superpowers' own gates are subordinated here:
- `verification-before-completion` is a check to run, not a place to stop.
- `requesting-code-review` produces advisory findings; its verdict never exits Stage 03.
- `receiving-code-review` governs how findings are evaluated, but never authorizes
  ending the turn.
- `subagent-driven-development` reporting all tasks complete, and its terminal
  "finish the branch" handoff, are neither an exit nor a completion — see Implementation Skill
  Boundaries above.

## Mandatory Exit Routing from Stage 03

After the loop exits with `status = pass`:

- `--yolo` mode enabled → jump to **Stage 05**.
- default mode → jump to **Stage 04** (mandatory, never skipped).

## Loop Algorithm (speckit-auto executes this — do not exit until DONE)

```
PHASE 1 — Implementation + verification loop
  C1 — Run the implementation skill for the next package/batch
       (subagent-driven-development, or executing-plans as fallback)
       - each step internally uses test-driven-development
       - bugs/test failures route through systematic-debugging
  C2 — Run verification-before-completion against the plan
       - it must produce fresh evidence: tests run, output observed
  C3 — Read the verification result
       IF unmet plan tasks, failing tests, or missing evidence:
         - record them as remaining work items
         - immediately return to C1 and implement them
       IF all plan tasks are implemented and evidence is clean:
         - proceed to PHASE 2

PHASE 2 — Code review loop
  R0 — Run requesting-code-review (native pass, advisory) — FIRST PHASE-2 ENTRY ONLY
       Set `r0_completed = true` only after the review actually returns findings. While
       `r0_completed` is false (e.g. R0 was deferred for an empty range), R0 still runs on the
       next PHASE-2 entry. Once true, skip R0 on every re-entry from R7 — speckit-code-review is
       the authoritative gate and repeating a full-diff advisory review duplicates it at high cost.
       - inputs: description, plan excerpt, BASE_SHA, HEAD_SHA
         (BASE_SHA = the merge-base recorded at stage entry, never HEAD~1 — see Review Range;
          if BASE_SHA == HEAD_SHA, nothing is committed yet → return to C1)
       - apply Critical and Important findings immediately via file edits
         (evaluate them through receiving-code-review discipline)
       - log Minor findings; do not stop for any of them
  R1 — Invoke speckit-code-review with spec path specs/<feature_folder>/spec.md;
       receive the JSON result (AUTHORITATIVE GATE)
   R2 — Read result.status
     IF status = "pass"  → EXIT STAGE 03
                            IF --yolo = true  → jump to Stage 05
                            IF --yolo = false → jump to Stage 04 (mandatory)
     IF status = "failed" → IMMEDIATELY go to R3 (rule 12: no prose summary, no stop, no ask)
  R3 — Read compact result fields:
    - `status` — already checked in R2
    - `Business cover` — business coverage %
    - `unit-test-coverage` — if < "80%" → all TEST-* fixes apply
    - `state_file` — resumable state; resume from this without reloading the full review body
    - `detail_files` — map of category → file path (load only the category you need)
    - `fixes[]` — flat list of actionable fix targets; THIS drives R4
    - after reading these, drop the rest of the failed review body and rebuild the next attempt
      from `state_file`
  R4 — Build the corrective action list directly from `fixes[]`:
    - Each entry has: id, file, method, lines, action
    - Group by ID prefix to classify scope:
      - FR-*/NFR-* → business gap (may need spec/plan restart)
      - ARCH-*     → architecture issue (may need plan restart)
      - SEC-*/CODE-* → code-level fix (direct file edit)
      - TEST-*     → missing test (direct file edit, via TDD)
    - If `action` is unclear, load ONLY the matching category file from `detail_files`:
      FR-*/NFR-* → "business-gap", ARCH-* → "architecture", SEC-* → "security",
      CODE-* → "code-quality", TEST-* → "unit-tests"
      Never load a category file you do not need for that specific fix.
  R5 — Classify and route:
    - All fixes are FR-*/NFR-*/ARCH-* → re-run writing-plans for the affected slice,
      re-run the Stage 02 self-review gate (spec coverage / placeholders / consistency), then R6
    - Mix of FR-*/ARCH-* + SEC-*/CODE-*/TEST-* → re-run writing-plans for the task
      breakdown only, re-run the self-review gate, then R6
    - Only SEC-*/CODE-*/TEST-* fixes → go directly to R6
  R6 — Apply fixes DIRECTLY using file-editing tools (this turn, right now):
    For EACH item in the corrective action list:
      1. Open the file named in suggested_fix_area / file
      2. Read the relevant method/lines
      3. Write the fix inline using edit/create file tools, following the TDD cycle for
         behavior changes (failing test first, then the fix)
      4. Move to the next item
     Rules for R6:
      - DO NOT delegate to the implementation skill for code-only or test-coverage issues
      - Just make the edits, then continue the Stage 03 flow immediately (rule 12)
      - If a fix needs a new file, create it
      - If context is insufficient, read the file first, then fix
  R7 — Run the implementation skill for broader changes if needed.
       Then re-run verification-before-completion, scoped to the tasks and tests touched by this
       iteration's fixes (not the whole plan), and go DIRECTLY to R1 (never to R0/R2 — R0 is
       first-entry only and is skipped whenever `r0_completed` is true).
       Never jump straight from a fix back to R1 without that fresh verification evidence.
```

## Loop Invariants

- Never exit this stage with `status = failed`; the review result is data to act on (rules 11–12).
- Never ask the user for help during this loop; the only stop is the global rule 20 circuit breaker.
- Never treat a superpowers gate skill as an exit point.
- Reach clean `verification-before-completion` evidence before first entering PHASE 2.
- Retain only `state_file`, the top `fixes[]`, and the one category file needed for the current fix.
- Never delegate to the implementation skill for code-only or test-coverage failures.
- On iteration 3+ with the same failure, escalate fix depth (rewrite the method, not patch a line).
- Log each iteration: `[Review loop #N] status=failed, scope=<code|tasks|plan>, fixing: <summary>`
