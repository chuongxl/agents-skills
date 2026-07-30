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

## How to Invoke speckit-code-review

`speckit-code-review` is a sub-skill, not an agent or background task.
Use the invocation appropriate for your environment:

| Environment | Invocation |
|-------------|-----------|
| GitHub Copilot CLI | `skill` tool with name `speckit-code-review` |
| Claude Code | `/speckit-code-review` slash command |
| OpenCode | `/speckit-code-review` or `@speckit-code-review` |

Never launch it as a background agent or task process — it must run inline and return JSON directly.

## Loop Algorithm (speckit-auto executes this — do not exit until DONE)

```
LOOP:
  STEP A — Run speckit.implement (or apply targeted fixes — see STEP G)
  STEP B — Invoke speckit-code-review; receive JSON result
  STEP C — Read result.status
    IF status = "pass"  → EXIT LOOP → proceed to Stage 04 or 05
    IF status = "failed" → IMMEDIATELY go to STEP D
                           DO NOT produce a prose summary to the user
                           DO NOT end the turn
                           DO NOT ask the user what to do
  STEP D — Parse ALL failure fields from JSON:
    - Business missing
    - Business missing details
    - code issues
    - security issue
    - architecture
    - unit-test-coverage  (if < "80%" → treat as code-level failure)
    - unit-test-missings  (list of file/method/lines to add tests for)
    - any other issue fields present
  STEP E — Build corrective action list from parsed details:
    - Use requirement_id, suggested_fix_area, file, method/function, line range
    - For unit-test-missings: each entry = one targeted test to write
  STEP F — Classify failure scope:
    - Plan-level issue     → re-run speckit.plan, then tasks → analyze → converge → STEP A
    - Task-level issue     → re-run speckit.tasks, then analyze → converge → STEP A
    - Code-only issue      → go directly to STEP G (no sub-skill delegation needed)
    - Unit test coverage   → go directly to STEP G, write tests per unit-test-missings
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
- speckit-auto NEVER delegates to speckit.implement for code-only or test-coverage failures — use file-editing tools directly
- speckit-auto NEVER stops and reports unless:
  - The same failure repeats for **5 consecutive iterations** with no file changes
  - A git or filesystem error prevents code from being written
- On iteration 3+ with the same failure, escalate fix depth (rewrite the method, not patch a line)
- Log each iteration: `[Review loop #N] status=failed, scope=<code|tasks|plan>, fixing: <summary>`
