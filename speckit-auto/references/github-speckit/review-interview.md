# Review Interview Guide

Use this guide during Stage 02 after each stage (`specify`, `clarify`, `plan`, `checklist`, `tasks`).
`analyze` is excluded — its approval is subsumed by the Stage 03 Entry Step confirmation in
[stage-02-spec-design-flow.md](stage-02-spec-design-flow.md). Never ask both back-to-back.

> ⚠️ **Stage 03 is a NO-STOP ZONE.** Do NOT run any interview flow during Stage 03 in any mode.

> **Mode note**: All interview sections apply to **default mode only**. In `--yolo` mode, human interactions are replaced by autonomous self-review (see Stage 02 YOLO behavior in stage-02-spec-design-flow.md).

## Specify Clarification Interview (When Spec Is Unclear)

Stage 01 never asks intake interview questions. If requirement clarity is insufficient during
`speckit.specify`, run this interview with the engineer, then rerun `speckit.specify`.

**Default mode only.**

1. Detect unclear areas in `speckit.specify` output (missing acceptance details, ambiguous scope,
   undefined constraints, unclear non-functional expectations).
2. Ask clarification questions as popups (`ask_user`) — one question at a time.
3. Capture answers and append them as requirement clarifications.
4. Rerun `speckit.specify` using the clarifications.
5. Repeat until spec is clear enough to proceed, then continue to `speckit.clarify`.

**YOLO mode**: do not interview; infer best-effort assumptions and continue.

## Interview Flow

**Default mode only. Applies to stages: `specify`, `clarify`, `plan`, `checklist`, `tasks`.**

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
