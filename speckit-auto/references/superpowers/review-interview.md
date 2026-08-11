# Review Interview Guide (superpowers)

Use this guide during Stage 02, after `writing-plans`.

> ⚠️ **Stage 03 is a NO-STOP ZONE.** Do NOT run any interview flow during Stage 03 in any mode.

> **Mode note**: every section here is **default mode only**. In `--yolo` mode, human interactions
> are replaced by autonomous self-review (see the YOLO behavior in stage-02-spec-design-flow.md).

## Clarification Is Owned by `brainstorming`

Unlike the github-speckit provider, do **not** run a separate specify-clarification interview.
`brainstorming` already asks clarifying questions one at a time and takes
section-by-section approval — that *is* the clarification interview.

- **Default mode**: let it run interactively; do not duplicate its questions.
- **`--yolo` mode**: instruct it to auto-answer from the intake brief and skip approvals.

Only if `brainstorming` finishes and the design spec is still unclear (missing acceptance detail,
ambiguous scope, undefined constraints) do you run the Interview Flow below against the spec, then
re-run `brainstorming` with the captured answers.

## Interview Flow

**Default mode only. Applies to: the design spec (post-`brainstorming`) and the plan
(post-`writing-plans`).**

1. Approval gate
   - Ask: "Do you approve the `<design spec | plan>` result?"
   - Choices: `Approve`, `Request changes`

2. Change request capture (only if not approved)
   - Ask: "What must be changed in `<design spec | plan>`?"
   - Capture the exact edits or concerns.

3. Forward constraints
   - Ask: "Any constraints to enforce in the next step?"
   - Choices: `None`, `Add constraints`

4. Constraint detail (only if constraints exist)
   - Ask: "List the constraints to enforce."

Ask one question at a time via `ask_user`.

## Decision Logic

- **Approve + no constraints**: proceed immediately.
- **Approve + constraints**: proceed and append the constraints to the next step's skill input.
- **Request changes**: re-run the same superpowers skill with the feedback, then repeat the interview.
- **Code review failed after implement**: Stage 03 owns that loop autonomously — no stops, no prompts.
- **Human manual review requests changes** (default mode): Stage 04 collects feedback and routes the restart.
- **YOLO mode — self-review fail**: self-correct and retry (max 2). On the 3rd failure, stop and report.

## Prompt Addendum Template

When the user gives feedback or constraints, append to the next skill input:

```text
User review feedback for this step:
- <feedback item 1>
- <feedback item 2>

Constraints for downstream steps:
- <constraint 1>
- <constraint 2>
```
