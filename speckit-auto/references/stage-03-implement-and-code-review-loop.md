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
  STEP A — Run speckit.implement (or targeted fix — see routing below)
  STEP B — Invoke speckit-code-review; receive JSON result
  STEP C — Read result.status
    IF status = "pass"  → EXIT LOOP → proceed to Stage 04 or 05
    IF status = "failed" → STEP D
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
  STEP F — Classify failure scope and set restart point:
    - Plan-level issue     → restart STEP A from speckit.plan
                             then: tasks → analyze → converge → implement
    - Task-level issue     → restart STEP A from speckit.tasks
                             then: analyze → converge → implement
    - Code-only issue      → restart STEP A from speckit.implement only
    - Unit test coverage   → restart STEP A from speckit.implement,
                             writing tests targeting unit-test-missings items
  STEP G — Apply fixes from corrective action list
  GOTO LOOP
```

## Loop Invariants

- speckit-auto NEVER exits this stage with `status = failed`
- speckit-auto NEVER asks the user for help during this loop
- speckit-auto NEVER stops and reports unless:
  - The same failure repeats for **5 consecutive iterations** with no change
  - A git or filesystem error prevents code from being written
- On iteration 3+ with the same failure, escalate fix depth (rewrite method, not patch)
- Log each iteration: `[Review loop #N] status=failed, scope=<code|tasks|plan>, fixing: <summary>`
