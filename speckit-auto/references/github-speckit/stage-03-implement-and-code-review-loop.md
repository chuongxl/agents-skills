# Stage 03: Implement + Converge + Auto Code Review Loop

Load this only when running `speckit.implement`, `speckit.converge`, and `speckit-code-review`.
Discard review-interview.md from context at this point — Stage 03 is a NO-STOP ZONE.

## Repository-Aware Implementation

Before invoking `speckit.implement`, inject into the prompt:

- The artifact digest (≤500 tokens, see [../shared/artifact-digest.md](../shared/artifact-digest.md)):
  summary, ACs, architecture, task status — in place of the full spec/plan.
- The `repo_map` so the skill knows which workspace each file should be created in.
- Any relevant guideline from `loaded_guidelines` that applies to the current task —
  match by checking whether the task topic appears in any stem key of `linked_guidelines`.
  If a match exists and is not yet cached, load it now and add to `loaded_guidelines`.

When routing fixes in R5 (scoped plan/tasks rerun), pass the same artifact digest fields
to those sub-skills so workspace assignment and architecture compliance are preserved.

## Invocation Method (Critical)

- `speckit.implement` and `speckit.converge`: call directly via the resolved host channel (see
  [../shared/host-adaptation.md](../shared/host-adaptation.md)) — repo slash commands
  (`/speckit.implement`, `/speckit.converge`) on Copilot and Claude Code
  (`stage_invocation_mode` is `slash-agent`), or the `skill` tool by each stage's resolved skill name
  on OpenCode. Never attempt `task` with a `speckit.*` agent_type on any host.
- `speckit-code-review`: dispatch as a sub-agent (background task) and block on its JSON verdict —
  see "How to Invoke speckit-code-review" below. Never run it inline in this orchestrator's context.

Never stop with a generic runtime/capability disclaimer before attempting the real call. Only stop
if a concrete tool call fails with a quoted error message.

## Heavy Payload Prevention + Implementation Partitioning

Treat `speckit.implementation` as `speckit.implement` (the repo-installed agent name).

When implementation scope is large, load [../shared/partitioning.md](../shared/partitioning.md) and
apply it, building `implementation_packages[]` from `tasks.md` grouped by `workspace` + bounded
capability, and invoking `speckit.implement` once per package until the queue is empty.

## Git Submodule Branch Handling (Implementation Stage)

See [../shared/branching.md](../shared/branching.md) — "Git Submodule Branch Handling". No
Speckit-specific deviation.
## NO-STOP ZONE (canonical: global rules 11–12, 20)

Stage 03 runs autonomously in both modes — no human gates, no interviews, no pauses, no
report-and-stop on a failed result. The only success exit is `status = pass` from
`speckit-code-review`; the only other permitted exit is the global rule 20 circuit breaker
(identical failure 5× with no file change, or a git/filesystem write error). A `failed` result is
the input for the next fix iteration.

## Mandatory Exit Routing from Stage 03

**Persist run-state** before exiting: save to `<worktree_path>/.speckit/run-state.json` with
`current_stage: "stage-04"` (default) or `"stage-05"` (yolo), `stage_03_completed_at` to now.
Format: see [../shared/run-state.md](../shared/run-state.md).

After the loop exits with `status = pass`, stage transition is deterministic:

- If `--yolo` mode is enabled: jump to **Stage 05**.
- If `--yolo` mode is NOT enabled (default mode): jump to **Stage 04**.

In default mode, Stage 04 is mandatory and must never be skipped.

## How to Invoke speckit-code-review

Dispatch `speckit-code-review` as a **sub-agent** (background task) — never inline in this
orchestrator's own context — and **block until it returns its JSON verdict**. Use the `task` tool
with a `general-purpose` agent type whose prompt instructs it to load and run the
`speckit-code-review` skill (from its on-disk `SKILL.md`) and return only the JSON object. The
returned JSON's `status` field is the review result this loop waits on.

Always pass the spec path explicitly: `specs/<issue_id>-<short_title>/spec.md` (or the manual-mode
folder resolved in Stage 01). Never let the skill guess — an ambiguous match makes it ask the user,
which is a turn-ending stop inside this NO-STOP ZONE. On retry iterations, also pass the previous
review's `state_file` path so the review runs in its selective area-loading mode, **and** pass an
explicit `scope` (the files changed since that review) so it re-reads only those files.

## Incremental Review Scope (Avoid Re-reading Unchanged Code)

The dominant Stage 03 cost is the review re-reading the whole feature diff + spec on every
iteration, when one fix iteration usually touches 1–3 files. Bound it:

1. At Stage 03 entry, set `last_reviewed_sha = <BASE_SHA>` (the base branch merge-base) in
   run-state (see [../shared/run-state.md](../shared/run-state.md)).
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

| Artifact regenerated | `invalidate` token | Re-implement scope (before re-review) |
|---|---|---|
| `spec.md` (requirement changed — Stage 02/04 restart routing) | `spec` → re-derive checklist + all areas | full plan → tasks → implement cascade (restart routing) |
| `plan.md` (+ checklist/tasks) | `plan` → architecture + business-gap | affected package/slice via `speckit.implement` |
| `tasks.md` only | `tasks` → business-gap + code-quality + unit-tests | affected tasks via `speckit.implement` |

**Mandatory re-implementation invariant:** after R5 regenerates `plan.md` or `tasks.md` (or restart
routing changes `spec.md`), R7 is no longer "if needed" — invoke `speckit.implement` for the
affected scope (the delta tasks, computed below) **before** returning to R1. Record the regenerated
artifact + affected scope in run-state (`review_invalidate`, see
[../shared/run-state.md](../shared/run-state.md)) so the next R1 passes the matching `invalidate`
token and `scope`. Only re-review after the code reflects the regenerated artifacts.

### Task Delta Detection (Re-implement Only What Changed)

Regeneration rewrites `tasks.md` and resets its checkboxes to unchecked, so "unchecked" is **not**
the delta — diffing by checkbox would re-implement everything. Compute the delta by task *content*:

1. **Before** R5 runs any regeneration step, snapshot the current task list to
   `.speckit/pre-regen-tasks.md` (`git show HEAD:specs/<id>/tasks.md`, or the uncommitted file if it
   exists). `.speckit/` is gitignored (scratch-hygiene), so this never leaks into a commit.
2. Run the regeneration (plan/checklist/tasks).
3. Extract the ordered task statements from the regenerated `tasks.md` and diff against the
   snapshot:
   - **new** task (absent before) or **edited** task (statement text changed) → re-implement.
   - **unchanged** task (identical text, even if its checkbox was reset) → already implemented;
     skip it.
4. R7 passes **only the delta tasks** to `speckit.implement` (a scoped task list, never the whole
   `tasks.md`).

## Loop Algorithm (speckit-auto executes this — do not exit until DONE)

```
PHASE 1 — Convergence loop
  C1 — Run speckit.implement for next package/batch
       - Small scope: single invocation
       - Large scope: multiple invocations, parallel only for independent packages
  C2 — Run speckit.converge (checks codebase vs spec.md/plan.md/tasks.md)
  C3 — Read converge result
       IF gaps found:
         - converge appends new tasks to tasks.md
         - immediately return to C1 and implement appended tasks
       IF converged:
         - proceed to PHASE 2

PHASE 2 — Code review loop
  R1 — Dispatch speckit-code-review as a sub-agent via the `task` tool (`general-purpose` agent
       type) with spec path specs/<issue_id>-<short_title>/spec.md and, on retries, the incremental
       `scope` (files changed since last review) + `state_file`. BLOCK on the dispatch: take no
       other action (no file reads, edits, run-state writes, or loop advance) until the sub-agent
       returns its JSON verdict. That JSON — with its `status` field — is the review's return value.
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
    - `state_file` — resumable state; use this to resume without reloading the full review body
    - `detail_files` — map of category → file path (load only the category you need)
    - `fixes[]` — flat list of actionable fix targets; THIS is what drives R4
    - after reading these fields, drop the rest of the failed review body from memory and rebuild the next attempt from `state_file`
  R4 — Build corrective action list directly from `fixes[]`:
    - Each fix entry has: id, file, method, lines, action
    - Group by ID prefix to classify scope:
      - FR-*/NFR-* → business gap (may need plan/tasks restart)
      - ARCH-* → architecture issue (may need plan restart)
      - SEC-*/CODE-* → code-level fix (direct file edit)
      - TEST-* → missing test (direct file edit)
    - If `action` is unclear for an entry, load ONLY the matching category file from `detail_files`:
      - FR-*/NFR-* entry → load `detail_files["business-gap"]`
      - ARCH-* entry → load `detail_files["architecture"]`
      - SEC-* entry → load `detail_files["security"]`
      - CODE-* entry → load `detail_files["code-quality"]`
      - TEST-* entry → load `detail_files["unit-tests"]`
      Do NOT load a category file unless you actually need it for that specific fix.
    - If the current retry loop is already holding too much context, discard prior review prose and rely on `state_file` + the one category file you need for the next fix.
  R5 — Classify and route (scoped regeneration — load [../shared/partitioning.md](../shared/partitioning.md) first):
    - Identify the affected `workspace` + `capability` scope from the fix entries' file paths
      (match against `implementation_packages[]` from the original task breakdown).
    - All fixes are FR-*/NFR-*/ARCH-* → re-run only `speckit.plan` for the affected
      package/slice, then `speckit.checklist` + `speckit.tasks` + `speckit.analyze` scoped to
      that slice; merge updated slice back into the full artifacts. Do NOT regenerate unaffected
      packages.
    - Mix of FR-*/ARCH-* + SEC-*/CODE-*/TEST-* → re-run `speckit.checklist` + `speckit.tasks`
      scoped to the affected workspace only; `speckit.analyze` once globally.
    - Only SEC-*/CODE-*/TEST-* fixes → go directly to R6 (no artifact regeneration).
    - Whenever a Stage 02 artifact was regenerated above, re-run the Stage 02 Mandatory
      Self-Review Gate (read-only, no interview) before R6 — global rule 10a
    - Snapshot the pre-regen task list first (`.speckit/pre-regen-tasks.md`), then record the
      regenerated artifact + affected scope in run-state (`review_invalidate = plan` or `tasks`) so
      R7 re-implements only the delta and the next R1 passes the matching `invalidate` token
      (see "Regeneration → Re-implementation → Re-review" above).
  R6 — Apply fixes DIRECTLY using file-editing tools (this turn, right now):
    For EACH item in corrective action list:
      1. Open the specific file listed in suggested_fix_area / file field
      2. Read the relevant method/lines
      3. Write the fix inline using edit/create file tools
      4. Move to next item
     Rules for R6:
      - DO NOT delegate to speckit.implement for code-only or test-coverage issues
      - Just make the edits, then continue the Stage 03 flow immediately (rule 12)
      - If a fix requires a new file, create it with the create file tool
      - If you don't have enough context to fix an item, read the file first, then fix
  R7 — If R5 regenerated plan/tasks (or restart routing changed spec), run speckit.implement for
       the delta tasks computed in "Task Delta Detection" FIRST (mandatory) so the code reflects the
       new artifacts; otherwise run speckit.implement only for broader changes if needed. Clear
       `review_invalidate` in run-state and delete the `.speckit/pre-regen-tasks.md` snapshot after
       the re-implementation completes. Then return to R1.
```

## Loop Invariants

- Never exit this stage with `status = failed`; the review result is data to act on (rules 11–12).
- Never ask the user for help during this loop; the only stop is the global rule 20 circuit breaker.
- Run `speckit.converge` until it reports converged before entering the code-review loop.
- Retain only `state_file`, the top `fixes[]`, and the one category file needed for the current fix.
- Never delegate to `speckit.implement` for code-only or test-coverage failures — edit files directly.
- On iteration 3+ with the same failure, escalate fix depth (rewrite the method, not patch a line).
- Log each iteration: `[Review loop #N] status=failed, scope=<code|tasks|plan>, fixing: <summary>`
