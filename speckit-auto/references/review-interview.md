# Review Interview Guide

Use this guide during Stage 02 after each stage (`specify`, `clarify`, `plan`, `tasks`, `analyze`, `converge`).

> ⚠️ **Stage 03 is a NO-STOP ZONE.** Do NOT run any interview flow during Stage 03 in any mode.

> **Mode note**: All interview sections apply to **default mode only**. In `--yolo` mode, human interactions are replaced by autonomous self-review (see Stage 02 YOLO behavior in stage-02-spec-design-flow.md).

## Intake Interview for Jira Issue Mode

**Default mode only.**

When run as `/speckit-auto --issue {jira link}`:

1. `jira-to-speckit` (or the fallback direct fetch) returns a compact brief.
2. Present the compact brief summary to the user.
3. Ask: "Does this summary correctly reflect the Jira requirement?"
   - Choices: `Yes`, `No`
4. If `No`, ask: "What should be corrected or clarified before we start specify?"
5. Resolve concerns, then proceed to `speckit.specify` with the (corrected) compact brief.

**YOLO mode**: skip all interview steps; accept the compact brief autonomously. Log any open questions as assumptions in the pipeline log.

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
