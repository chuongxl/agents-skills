# Stage 03 (superpowers): Implement + Verify + Auto Code Review Loop

Load this only when running implementation and review.
Discard review-interview.md from context at this point — Stage 03 is a NO-STOP ZONE.

## Repository-Aware Implementation

Before invoking the implementation skill, inject into its input:

- the artifact digest (≤500 tokens, see [../shared/artifact-digest.md](../shared/artifact-digest.md)):
  summary, ACs, architecture, task status — in place of the full spec/plan
- the `repo_map`, so each file lands in the correct workspace
- any relevant guideline from `loaded_guidelines` matching the task topic (match by stem key in
  `linked_guidelines`; if matched and not yet cached, load it now and add it to `loaded_guidelines`)
- the plan path `specs/<feature_folder>/plan.md`

## Invocation Method (Critical)

Invoke every superpowers step through the `skill` tool, per
[provider-rules.md](provider-rules.md) (name resolution + Task Tool section). The skills these steps
dispatch subagents from — `subagent-driven-development`, `requesting-code-review` — are required
here; never suppress them. `speckit-code-review` is the one exception: dispatch it as a sub-agent
(see below), never through the `skill` tool inline.

| Step | Skill |
|------|-------|
| Implementation (subagents available) | `subagent-driven-development` |
| Implementation (no subagents) | `executing-plans` |
| Per-step TDD | `test-driven-development` |
| Root-cause debugging | `systematic-debugging` |
| Native review pass | `requesting-code-review` |
| Review response discipline | `receiving-code-review` |
| Completion evidence gate | `verification-before-completion` |

`speckit-code-review` must run as a **sub-agent** (background task, never inline in this
orchestrator's context) and must always be given the spec path explicitly:
`specs/<feature_folder>/spec.md` — an ambiguous match makes it ask the user, a turn-ending stop
inside this NO-STOP ZONE. Dispatch it via the `task` tool with a `general-purpose` agent type whose
prompt instructs it to load and run the `speckit-code-review` skill and return only the JSON verdict;
block on that dispatch. On retry iterations, also pass the previous review's `state_file` path so the
review runs in its selective area-loading mode, **and** pass an explicit `scope` (the files changed
since that review) so it re-reads only those files. That spec is a `brainstorming` design document
with no `FR-*`/`NFR-*` IDs; the review skill synthesizes the checklist itself, so never pre-convert
the spec to add IDs.

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

## Incremental Review Scope (Avoid Re-reading Unchanged Code)

The dominant Stage 03 cost is the review re-reading the whole feature diff + spec on every
iteration, when one fix iteration usually touches 1–3 files. Bound it:

1. At Stage 03 entry, set `last_reviewed_sha = BASE_SHA` (the merge-base recorded in Review Range)
   in run-state (see [../shared/run-state.md](../shared/run-state.md)).
2. Before each R1, compute the incremental change map from inside the worktree in one call:
   `git diff --unified=0 <last_reviewed_sha>..HEAD` → parse the `@@` hunk headers into a
   `file → {lines}` map (fall back to `--name-only` when a file has no parseable hunks). The first
   iteration is the full feature diff; every later iteration is only the hunks the fix loop just
   edited.
3. Pass that map to `speckit-code-review` as `scope` (in addition to `state_file` on retries). The
   review then reads only those hunks with open findings and carries everything else forward.
4. After R1 returns, read the review's `scope` digest back from its `state_file` and set
   `last_reviewed_sha = HEAD` in run-state — even when the review `failed`, because that pass is
   the checkpoint for the next, narrower diff.
5. If `last_reviewed_sha..HEAD` is empty (nothing changed since the last review yet `status` was
   `failed`), the fixes touched no reviewed file: re-run the full scope once rather than looping on
   an empty diff, and count it toward the rule 20 circuit breaker.

Do not fold this into the R3 "drop the review body" step — that clears the orchestrator's own
context; this bounds what the *review skill* reads on its next call, which is the larger cost.

## Regeneration → Re-implementation → Re-review (Granular Invalidation)

When the fix loop regenerates a Stage 02 artifact, the code must be re-implemented to match **before**
the next review — otherwise a review can only fail, or worse, pass against stale code. Granular
invalidation tells `speckit-code-review` exactly which cached verdicts are stale; re-implementation
makes the code reflect the new artifacts.

Superpowers has **no `tasks.md`** — the task breakdown lives inside `plan.md` (its `- [ ]`
checkboxes). There are therefore only two invalidation levels:

| Artifact regenerated | `invalidate` token | Re-implement scope (before re-review) |
|---|---|---|
| `spec.md` (design changed — Stage 02/04 restart routing) | `spec` → re-derive checklist + all areas | full plan → implement cascade (restart routing) |
| `plan.md` (via `writing-plans` — architecture **and** task breakdown) | `plan` → architecture + business-gap | affected slice/tasks via `subagent-driven-development`/`executing-plans` |

**Mandatory re-implementation invariant:** after R5 regenerates `plan.md` (or restart routing
changes `spec.md`), R7 is no longer "if needed" — invoke the implementation skill for the affected
scope (the delta tasks, computed below) **before** returning to R1. Record the regenerated artifact
+ affected scope in run-state (`review_invalidate`, see
[../shared/run-state.md](../shared/run-state.md)) so the next R1 passes the matching `invalidate`
token and `scope`. Only re-review after the code reflects the regenerated artifacts.

### Task Delta Detection (Re-implement Only What Changed)

Regeneration rewrites `plan.md` and resets its `- [ ]` checkboxes to unchecked, so "unchecked" is
**not** the delta — diffing by checkbox would re-implement everything. Compute the delta by task
*content*:

1. **Before** R5 runs `writing-plans`, snapshot the current task checklist (the `- [ ]`/`- [x]`
   lines in `plan.md`) to `.speckit/pre-regen-tasks.md`. `.speckit/` is gitignored
   (scratch-hygiene), so this never leaks into a commit.
2. Run `writing-plans`.
3. Extract the task lines from the regenerated `plan.md` and diff against the snapshot:
   - **new** task (absent before) or **edited** task (text changed) → re-implement.
   - **unchanged** task (identical text, even if its checkbox was reset) → already implemented;
     skip it.
4. R7 passes **only the delta tasks** to the implementation skill (a scoped task list, never the
   whole plan).

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

**Persist run-state** before exiting: save to `<worktree_path>/.speckit/run-state.json` with
`current_stage: "stage-04"` (default) or `"stage-05"` (yolo), `stage_03_completed_at` to now.
Format: see [../shared/run-state.md](../shared/run-state.md).

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
  R1 — Dispatch speckit-code-review as a sub-agent via the `task` tool (`general-purpose` agent
       type) with spec path specs/<feature_folder>/spec.md and, on retries, the incremental `scope`
       (files changed since last review) + `state_file`. BLOCK on the dispatch: take no other action
       (no file reads, edits, run-state writes, or loop advance) until the sub-agent returns its JSON
       verdict. That JSON — with its `status` field — is the review's return value
       (AUTHORITATIVE GATE).
   R2 — Read result.status from the JSON returned by R1. This check is the very next action after
       R1 returns; never interleave any step between R1 and R2.
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
  R5 — Classify and route (scoped regeneration — load [../shared/partitioning.md](../shared/partitioning.md) first):
    - Identify the affected `workspace` + `capability` scope from the fix entries' file paths
      (match against the original task/plan structure).
    - All fixes are FR-*/NFR-*/ARCH-* → re-run `writing-plans` for the affected slice only,
      re-run the Stage 02 self-review gate, then R6. Do NOT regenerate unaffected slices.
    - Mix of FR-*/ARCH-* + SEC-*/CODE-*/TEST-* → re-run `writing-plans` (task breakdown only)
      for the affected workspace, re-run the self-review gate, then R6.
    - Only SEC-*/CODE-*/TEST-* fixes → go directly to R6 (no artifact regeneration).
    - Snapshot the pre-regen task checklist first (`.speckit/pre-regen-tasks.md`), then record the
      regenerated artifact + affected scope in run-state (`review_invalidate = plan`) so R7
      re-implements only the delta and the next R1 passes the matching `invalidate` token
      (see "Regeneration → Re-implementation → Re-review" above).
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
  R7 — If R5 regenerated plan.md (or restart routing changed spec), run the implementation
       skill for the delta tasks computed in "Task Delta Detection" FIRST (mandatory) so the code
       reflects the new artifacts; otherwise run it only for broader changes if needed. Clear
       `review_invalidate` in run-state and delete the `.speckit/pre-regen-tasks.md` snapshot after
       the re-implementation completes.
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
