# Stage 03: Implement + Converge + Auto Code Review Loop

Load this only when running `speckit.implement`, `speckit.converge`, and `speckit-code-review`.
Discard review-interview.md from context at this point — Stage 03 is a NO-STOP ZONE.

## Repository-Aware Implementation

Before invoking `speckit.implement`, inject into the prompt:

- The `summary` from the Project Context loaded in Stage 01.
- The `repo_map` so the skill knows which workspace each file should be created in.
- Any relevant guideline from `loaded_guidelines` that applies to the current task —
  match by checking whether the task topic appears in any stem key of `linked_guidelines`.
  If a match exists and is not yet cached, load it now and add to `loaded_guidelines`.

When routing fixes in R5 (plan/checklist/tasks/analyze reruns), pass the same Project Context
fields to those sub-skills so workspace assignment and architecture compliance are preserved.

## Invocation Method (Critical)

- `speckit.implement` and `speckit.converge`: call directly via the resolved host channel (see
  [../shared/host-adaptation.md](../shared/host-adaptation.md)) — repo slash commands
  (`/speckit.implement`, `/speckit.converge`) on Copilot and Claude Code
  (`stage_invocation_mode` is `slash-agent`), or the `skill` tool by each stage's resolved skill name
  on OpenCode. Never attempt `task` with a `speckit.*` agent_type on any host.
- `speckit-code-review`: invoke via the `skill` tool with name `speckit-code-review` (all hosts).

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

Invoke via the `skill` tool with name `speckit-code-review`.
Never launch as a background agent or task process — it must run inline and return JSON directly.

Always pass the spec path explicitly: `specs/<issue_id>-<short_title>/spec.md` (or the manual-mode
folder resolved in Stage 01). Never let the skill guess — an ambiguous match makes it ask the user,
which is a turn-ending stop inside this NO-STOP ZONE. On retry iterations, also pass the previous
review's `state_file` path so the review runs in its selective area-loading mode.

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
  R1 — Invoke speckit-code-review with spec path specs/<issue_id>-<short_title>/spec.md;
       receive JSON result
   R2 — Read result.status
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
  R5 — Classify and route:
    - All fixes are FR-*/NFR-*/ARCH-*  → re-run repo `speckit.plan` then repo `speckit.checklist` then repo `speckit.tasks` → repo `speckit.analyze` → R6
    - Mix of FR-*/ARCH-* + SEC-*/CODE-*/TEST-* → re-run repo `speckit.checklist` then repo `speckit.tasks` → repo `speckit.analyze` → R6
    - Only SEC-*/CODE-*/TEST-* fixes → go directly to R6
    - Whenever a Stage 02 artifact was regenerated above, re-run the Stage 02 Mandatory
      Self-Review Gate (read-only, no interview) before R6 — global rule 10a
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
  R7 — Run speckit.implement to apply broader changes if needed, then return to R1
```

## Loop Invariants

- Never exit this stage with `status = failed`; the review result is data to act on (rules 11–12).
- Never ask the user for help during this loop; the only stop is the global rule 20 circuit breaker.
- Run `speckit.converge` until it reports converged before entering the code-review loop.
- Retain only `state_file`, the top `fixes[]`, and the one category file needed for the current fix.
- Never delegate to `speckit.implement` for code-only or test-coverage failures — edit files directly.
- On iteration 3+ with the same failure, escalate fix depth (rewrite the method, not patch a line).
- Log each iteration: `[Review loop #N] status=failed, scope=<code|tasks|plan>, fixing: <summary>`
