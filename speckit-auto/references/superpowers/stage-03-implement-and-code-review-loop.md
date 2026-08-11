# Stage 03 (superpowers): Implement + Verify + Auto Code Review Loop

Load this only when running implementation and review.
Discard review-interview.md from context at this point — Stage 03 is a NO-STOP ZONE.

## Repository-Aware Implementation

Before invoking the implementation skill, inject into its input:

- the `summary` from the Project Context loaded in Stage 01
- the `repo_map`, so each file lands in the correct workspace
- any relevant guideline from `loaded_guidelines` matching the task topic (match by stem key in
  `linked_guidelines`; if matched and not yet cached, load it now and add it to `loaded_guidelines`)
- the plan path `docs/superpowers/plans/<issue_id>-<short_title>.md`

## Invocation Method (Critical)

All superpowers steps are invoked via the `skill` tool — no slash commands, no agents, and never
the `task` tool with a `superpowers:*` agent_type. Resolve each skill name using the precedence in
[provider-rules.md](provider-rules.md) (session skill list → `superpowers:<name>` → bare `<name>`
→ file-read fallback).

| Step | Skill |
|------|-------|
| Implementation (subagents available) | `subagent-driven-development` |
| Implementation (no subagents) | `executing-plans` |
| Per-step TDD | `test-driven-development` |
| Root-cause debugging | `systematic-debugging` |
| Native review pass | `requesting-code-review` |
| Review response discipline | `receiving-code-review` |
| Completion evidence gate | `verification-before-completion` |

`speckit-code-review` is invoked via the `skill` tool with name `speckit-code-review`.
Never launch it as a background agent or task process — it must run inline and return JSON directly.

Never stop with a generic runtime/capability disclaimer before attempting the real call. Only stop
if a concrete tool call fails with a quoted error message.

## Execution Style Selection

Choose once, at Stage 03 entry, and keep it for the whole run:

- Prefer `subagent-driven-development` (fresh implementer per task, two-stage review).
- Fall back to `executing-plans` if subagent dispatch is unavailable or fails.

## Mandatory TDD

Every implementation step runs `test-driven-development`:
RED (write the failing test and watch it fail) → GREEN (minimal code, watch it pass) → REFACTOR.
Code written before its test must be deleted and redone. This applies to fix iterations too.

When a test fails unexpectedly or a bug appears, run `systematic-debugging` — never
apply a fix without an identified root cause.

## Worktrees Are Skipped

Stay on the branch created in Stage 01; ignore any superpowers instruction to create or enter a
worktree. See global rule 3 and [../shared/branching.md](../shared/branching.md).

## Git Submodule Branch Handling

See [../shared/branching.md](../shared/branching.md) — "Git Submodule Branch Handling". No
superpowers-specific deviation.

## Heavy Payload Prevention + Implementation Partitioning

When implementation scope is large, split and execute in batches:

1. Build `implementation_packages[]` from the plan's tasks, grouped by `workspace` + bounded capability.
2. Keep each package input minimal: package-specific tasks + relevant plan/spec excerpts only.
3. Invoke the implementation skill once per package until the queue is empty.
4. Parallelize only independent packages (no dependency edges, no shared file ownership risk).
   Use `dispatching-parallel-agents` when parallelizing.
5. Run dependency-linked packages sequentially in topological order.
6. After each batch, keep only compact progress state (remaining packages, changed files, blockers).

## CRITICAL: speckit-auto Owns This Loop — NO STOPS, NO GATES

**This stage is a NO-STOP ZONE. The following are SUSPENDED for the entire duration of Stage 03,
regardless of mode (default or `--yolo`):**
- Human approval gates
- Post-step interview questions
- "Do you approve?" prompts
- Any pause waiting for human input
- Any report-and-stop on a failed result

**The only valid success exit from Stage 03 is `status = pass` from `speckit-code-review`.**
The only other permitted exit is the circuit breaker in global rule 20 (identical failure 5×
with no file change in between, or a git/filesystem write error).
A `failed` result is NOT a stop condition in any mode — it is the input for the next fix iteration.

Superpowers' own gates are subordinated here:
- `verification-before-completion` is a check to run, not a place to stop.
- `requesting-code-review` produces advisory findings; its verdict never exits Stage 03.
- `receiving-code-review` governs how findings are evaluated, but never authorizes
  ending the turn.

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
  R0 — Run requesting-code-review (native pass, advisory)
       - inputs: description, plan excerpt, BASE_SHA, HEAD_SHA
       - apply Critical and Important findings immediately via file edits
         (evaluate them through receiving-code-review discipline)
       - log Minor findings; do not stop for any of them
  R1 — Invoke speckit-code-review; receive the JSON result (AUTHORITATIVE GATE)
  R2 — Read result.status
    IF status = "pass"  → EXIT STAGE 03
                           IF --yolo = true  → jump to Stage 05
                           IF --yolo = false → jump to Stage 04 (mandatory)
    IF status = "failed" → IMMEDIATELY go to R3
                           DO NOT produce a prose summary to the user
                           DO NOT end the turn
                           DO NOT ask the user what to do
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
      - DO NOT produce a prose response to the user — just make the edits
      - DO NOT end the turn after making edits — continue the Stage 03 flow immediately
      - If a fix needs a new file, create it
      - If context is insufficient, read the file first, then fix
  R7 — Run the implementation skill for broader changes if needed.
       Then re-run the full gate sequence before the next authoritative review:
       verification-before-completion → R0 (requesting-code-review) → R1.
       Never jump straight from a fix back to R1 — every authoritative review iteration must be
       preceded by fresh verification evidence and a native review pass.
```

## Loop Invariants

- speckit-auto NEVER exits this stage with `status = failed`
- speckit-auto MUST reach clean `verification-before-completion` evidence before entering the code-review loop
- speckit-auto NEVER asks the user for help during this loop
- speckit-auto NEVER produces a prose summary of the review result — it is data to act on
- speckit-auto NEVER ends a turn after a failed review — the next action is always file edits
- speckit-auto NEVER retains full failed-review text across retries; keep only `state_file`, the top
  `fixes[]`, and the one category file needed for the current fix
- speckit-auto NEVER delegates to the implementation skill for code-only or test-coverage failures
- speckit-auto NEVER treats a superpowers gate skill as an exit point
- speckit-auto NEVER stops and reports except via the global rule 20 circuit breaker (identical failure 5× with no file change in between, or a git/filesystem write error)
- On iteration 3+ with the same failure, escalate fix depth (rewrite the method, not patch a line)
- Log each iteration: `[Review loop #N] status=failed, scope=<code|tasks|plan>, fixing: <summary>`
