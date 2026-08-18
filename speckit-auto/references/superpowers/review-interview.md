# Review Interview Guide (superpowers)

Use this guide during Stage 02: as the question set for the Stage 03 Entry Step confirmation
(the plan's approval gate), and after `brainstorming` in the two design-spec cases listed under
Scope below.

> ⚠️ **Stage 03 is a NO-STOP ZONE.** Do NOT run any interview flow during Stage 03 in any mode.

> **Mode note**: every section here is **default mode only**. In `--yolo` mode, human interactions
> are replaced by autonomous self-review (see the YOLO behavior in stage-02-spec-design-flow.md).

## Scope: There Is No Separate Design-Spec Approval Interview

`brainstorming` already runs its own interactive clarification and section-by-section approval —
that **is** the design-spec review gate. Do not run the Interview Flow below against the design
spec as a routine step, and do not repeat questions `brainstorming` already asked.

- **Default mode**: let `brainstorming` run interactively.
- **`--yolo` mode**: instruct it to auto-answer from the intake brief and skip approvals; run no
  interview at all.

The Interview Flow below applies to:
1. the **plan** — not as a standalone step: its approval gate is the Stage 03 Entry Step
   confirmation in [stage-02-spec-design-flow.md](stage-02-spec-design-flow.md), which uses the
   questions below. Never run a separate post-`writing-plans` interview on top of it,
2. the **design spec**, *only* as an exception — when `brainstorming` has finished and the spec
   still has a concrete clarity defect (missing acceptance detail, ambiguous scope, undefined
   constraint). Capture the answers, re-run `brainstorming`, and continue, and
3. the **design spec**, as the delegation fallback — when `brainstorming` never actually ran its
   interactive approval in default mode (see the Fallback note in
   [stage-02-spec-design-flow.md](stage-02-spec-design-flow.md) Step 1). A design spec must never
   reach Stage 03 unapproved in default mode.

## Interview Flow

**Default mode only. Routine use: as the question set for the Stage 03 Entry Step confirmation
(the plan's approval gate). Exception use: the design spec, only per the Scope section above.**

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

Ask one question at a time via the host's ask tool (`ask_user` on Copilot, `question` on OpenCode,
`AskUser` on Claude Code).

## Clarify + Checklist Concern Gates

In superpowers Stage 02, clarify/checklist map to:
- **Clarify equivalent**: `brainstorming` clarification loop
- **Checklist equivalent**: `writing-plans` mandatory self-review gate

Behavior:
- **Default mode**: if either equivalent stage has a gap/concern, run this interview flow to
  collect answers, rerun the source step, and require explicit human approval before advancing.
- **`--yolo` mode**: no human interview; AI resolves concerns autonomously, reruns the source step,
  and only advances after autonomous approval.

## Decision Logic

- **Approve + no constraints**: proceed immediately.
- **Approve + constraints**: proceed and append the constraints to the next step's skill input.
- **Request changes**: re-run the same superpowers skill with the feedback, then repeat the interview.
- **Code review failed after implement**: Stage 03 owns that loop autonomously — no stops, no prompts.
- **Human manual review requests changes** (default mode): Stage 04 collects feedback and routes the restart.
- **YOLO mode — self-review fail**: self-correct and retry (max 2). On the 3rd failure, stop and report.
- **YOLO mode — clarify/checklist concern**: resolve concern autonomously, rerun the source step,
  then approve before continuing.

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
