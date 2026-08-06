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

- `speckit.implement` and `speckit.converge` use Stage 01 `stage_invocation_mode`:
  - `task-agent`: invoke via `task` with matching Speckit `agent_type`
  - `slash-agent`: invoke via repo-installed slash commands (`/speckit.implement`, `/speckit.converge`)
- `speckit-code-review` uses the skill invocation mapping in `SKILL.md`
  (GitHub Copilot CLI: `skill` tool with name `speckit-code-review`).

Do not stop with a generic runtime/capability disclaimer unless a concrete tool call fails.

## Heavy Payload Prevention + Implementation Partitioning

Treat `speckit.implementation` as `speckit.implement` (repo-installed agent name is `speckit.implement`).

When implementation scope is large, split and execute in batches:

1. Build `implementation_packages[]` from `tasks.md` grouped by `workspace` + bounded capability.
2. Keep each package prompt minimal: package-specific tasks + relevant plan/spec excerpts only.
3. Invoke `speckit.implement` multiple times (one invocation per package) until queue is empty.
4. Parallelize only independent packages (no dependency edges, no shared file ownership risk).
5. Run dependency-linked packages sequentially in topological order.
6. After each batch, keep only compact progress state (remaining packages, changed files, known blockers).

## Git Submodule Branch Handling (Implementation Stage)

Apply this only when the repo uses git submodules.

1. Detect submodules from `.gitmodules` and track their paths.
2. During implementation/fix steps, if code changes occur inside a submodule path:
   - ensure that submodule has a working branch before committing there
   - branch base priority inside submodule: `develop` → `main` → `master` (local first, then remote-tracking)
   - branch name should be deterministic and aligned with the parent pipeline branch context
3. Create/switch submodule branch lazily (only when that submodule is actually modified).
4. If no submodule exists, or no submodule files are modified, keep current behavior unchanged.

## CRITICAL: speckit-auto Owns This Loop — NO STOPS, NO GATES

**This stage is a NO-STOP ZONE. The following are SUSPENDED for the entire duration of Stage 03, regardless of mode (default or --yolo):**
- Human approval gates
- Post-stage interview questions
- "Do you approve?" prompts
- Any pause waiting for human input
- Any report-and-stop on failed result

**The only valid exit from Stage 03 is `status = pass` from `speckit-code-review`.**
A `failed` result is NOT a stop condition in any mode. It is the input for the next fix iteration.
The agent MUST continue the loop autonomously until pass is received.

## Mandatory Exit Routing from Stage 03

After the loop exits with `status = pass`, stage transition is deterministic:

- If `--yolo` mode is enabled: jump to **Stage 05**.
- If `--yolo` mode is NOT enabled (default mode): jump to **Stage 04**.

In default mode, Stage 04 is mandatory and must never be skipped.

## How to Invoke speckit-code-review

Use the invocation for your environment from the Compatibility table in SKILL.md.
Never launch as a background agent or task process — it must run inline and return JSON directly.

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
  R1 — Invoke speckit-code-review; receive JSON result
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
  R6 — Apply fixes DIRECTLY using file-editing tools (this turn, right now):
    For EACH item in corrective action list:
      1. Open the specific file listed in suggested_fix_area / file field
      2. Read the relevant method/lines
      3. Write the fix inline using edit/create file tools
      4. Move to next item
    Rules for R6:
      - DO NOT delegate to speckit.implement for code-only or test-coverage issues
      - DO NOT produce a prose response to the user — just make the edits
      - DO NOT end the turn after making edits — continue Stage 03 flow immediately
      - If a fix requires a new file, create it with the create file tool
      - If you don't have enough context to fix an item, read the file first, then fix
  R7 — Run speckit.implement to apply broader changes if needed, then return to R1
```

## Loop Invariants

- speckit-auto NEVER exits this stage with `status = failed`
- speckit-auto MUST run `speckit.converge` until it reports converged before entering the code-review loop
- speckit-auto NEVER asks the user for help during this loop
- speckit-auto NEVER produces a prose summary of the review result — the review result is data to act on, not a message to report
- speckit-auto NEVER ends a turn after receiving a failed review — the next action after a failed review is always file edits, not a response
- speckit-auto NEVER retains full failed-review text across retries; keep only `state_file`, the top `fixes[]`, and the one category file needed for the current fix
- speckit-auto NEVER delegates to speckit.implement for code-only or test-coverage failures — use file-editing tools directly
- speckit-auto NEVER stops and reports unless:
  - The same failure repeats for **5 consecutive iterations** with no file changes
  - A git or filesystem error prevents code from being written
- On iteration 3+ with the same failure, escalate fix depth (rewrite the method, not patch a line)
- Log each iteration: `[Review loop #N] status=failed, scope=<code|tasks|plan>, fixing: <summary>`
