# Stage 03: Implement + Auto Code Review Loop

Load this only when running `speckit.implement` and `speckit-code-review`.

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

`speckit-code-review` is a sub-skill, not an agent or background task.
Use the invocation appropriate for your environment:

| Environment | Invocation |
|-------------|-----------|
| GitHub Copilot CLI | `skill` tool with name `speckit-code-review` |
| Claude Code | `/speckit-code-review` slash command |
| OpenCode | `/speckit-code-review` or `@speckit-code-review` |

Never launch it as a background agent or task process — it must run inline and return JSON directly.

## Compact Mode

Always keep the review loop on compact payloads:

- retain only `state_file`, the top `fixes[]`, and the one category file needed for the next fix
- never rehydrate verbose failed-review prose into the loop context
- if the current tool supports a compact command or command alias, prefer that form; otherwise use the compact JSON/state-file contract above
- before each retry, rebuild the working context from the latest `state_file` instead of appending prior failed-review output
- if the next action is unclear, load only one matching `detail_files` category and then discard it again after the fix is applied
- never carry more than one failed review payload forward; each retry starts from a fresh minimal context snapshot

## Loop Algorithm (speckit-auto executes this — do not exit until DONE)

```
LOOP:
  STEP A — Run speckit.implement (or apply targeted fixes — see STEP G)
  STEP B — Invoke speckit-code-review; receive JSON result
  STEP C — Read result.status
    IF status = "pass"  → EXIT LOOP
                           IF --yolo = true  → jump to Stage 05
                           IF --yolo = false → jump to Stage 04 (mandatory)
    IF status = "failed" → IMMEDIATELY go to STEP D
                           DO NOT produce a prose summary to the user
                           DO NOT end the turn
                           DO NOT ask the user what to do
  STEP D — Read compact result fields:
    - `status` — already checked in STEP C
    - `Business cover` — business coverage %
    - `unit-test-coverage` — if < "80%" → all TEST-* fixes apply
    - `state_file` — resumable state; use this to resume without reloading the full review body
    - `detail_files` — map of category → file path (load only the category you need)
    - `fixes[]` — flat list of actionable fix targets; THIS is what drives STEP E
    - after reading these fields, drop the rest of the failed review body from memory and rebuild the next attempt from `state_file`
  STEP E — Build corrective action list directly from `fixes[]`:
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
  STEP F — Classify and route:
    - All fixes are FR-*/NFR-*/ARCH-*  → re-run speckit.plan then tasks → analyze → converge → STEP A
    - Mix of FR-*/ARCH-* + SEC-*/CODE-*/TEST-* → re-run speckit.tasks → analyze → converge → STEP A
    - Only SEC-*/CODE-*/TEST-* fixes → go directly to STEP G (no sub-skill needed)
  STEP G — Apply fixes DIRECTLY using file-editing tools (this turn, right now):
    For EACH item in corrective action list:
      1. Open the specific file listed in suggested_fix_area / file field
      2. Read the relevant method/lines
      3. Write the fix inline using edit/create file tools
      4. Move to next item
    Rules for STEP G:
      - DO NOT delegate to speckit.implement for code-only or test-coverage issues
      - DO NOT produce a prose response to the user — just make the edits
      - DO NOT end the turn after making edits — immediately GOTO LOOP
      - If a fix requires a new file, create it with the create file tool
      - If you don't have enough context to fix an item, read the file first, then fix
  GOTO LOOP
```

## Loop Invariants

- speckit-auto NEVER exits this stage with `status = failed`
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
