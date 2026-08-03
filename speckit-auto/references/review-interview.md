# Review Interview Guide

Use this guide during Stage 02 after each stage (`specify`, `clarify`, `plan`, `tasks`, `analyze`, `converge`).

> ⚠️ **Stage 03 is a NO-STOP ZONE.** Do NOT run any interview flow during Stage 03 in any mode.

> **Mode note**: All interview sections apply to **default mode only**. In `--yolo` mode, human interactions are replaced by autonomous self-review (see Stage 02 YOLO behavior in stage-02-spec-design-flow.md).

## Intake Interview for Jira Issue Mode

> ⚠️ **INTAKE IS A NO-STOP ZONE.**
> After `jira-to-speckit` (or fallback) produces the compact brief, do NOT end the turn.
> Do NOT output the brief as a final response and wait.
> Immediately run the popup-based interview loop below, collect all answers inline,
> then continue to Stage 02 — all within the same continuous flow.

**Default mode only.** In YOLO mode, skip to the YOLO block below.

### Default Mode — Intake Interview Loop

1. **Confirmation popup** (ask_user, one question at a time):
   - "Does this summary correctly reflect the Jira requirement?"
   - Choices: `Yes — proceed to specify` | `No — I want to correct something`

2. If `No`:
   - Popup: "What should be corrected or clarified?" (freeform)
   - Apply correction to the brief in memory.
   - Return to step 1 with the updated brief.

3. When brief is confirmed and `open_questions` list is non-empty:
   - For **each** open question — one popup at a time:
     - "Open question: `<question>` — your answer?" (freeform)
     - Incorporate answer into brief notes.
   - After the last question:
     - Popup: "Any other clarifications before we start specify?"
     - Choices: `No — start specify now` | `Yes — one more thing`
     - If `Yes`: collect it, loop back to this step.

4. When all answers collected → **immediately continue to Stage 02** without ending the turn.
   Do NOT wait for the user to say "continue" or "proceed".

**YOLO mode**: skip all popups. Accept the compact brief as-is. Log open questions as
assumptions in the pipeline log. Immediately continue to Stage 02.

## Interview Flow

**Default mode only. Applies to stages: `specify`, `clarify`, `plan`, `tasks`, `analyze`, `converge`.**

1. Approval gate
   - Ask: "Do you approve the `<stage>` result?"
   - Choices: `Approve`, `Request changes`

2. Change request capture (only if not approved)
   - Ask: "What must be changed in `<stage>`?"
   - Capture exact edits or concerns from the user.

3. Forward constraints
   - Ask: "Any constraints to enforce in the next stage?"
   - Choices: `None`, `Add constraints`

4. Constraint detail (only if constraints exist)
   - Ask: "List the constraints to enforce."

## Decision Logic

- **Approve + no constraints**: proceed immediately.
- **Approve + constraints**: proceed and append constraints to next stage prompt.
- **Request changes**: rerun the same stage with feedback, then repeat interview.
- **Code review failed after implement**: → Stage 03 owns this loop autonomously (no stops, no user prompts).
- **Human manual review requests changes** (default mode): → Stage 04 collects feedback and routes the restart.
- **YOLO mode — self-review fail**: self-correct and retry (max 2). On 3rd fail, stop and report.

## Prompt Addendum Template

When user gives feedback/constraints, append:

```text
User review feedback for this stage:
- <feedback item 1>
- <feedback item 2>

Constraints for downstream stages:
- <constraint 1>
- <constraint 2>
```
