# Review Interview Guide

Use this guide after each stage (`specify`, `clarify`, `plan`, `tasks`, `analyze`, `converge`).

> ⚠️ **EXCEPTION — Stage 03 (Implement + Code Review Loop) is a NO-STOP ZONE.**
> Do NOT run any interview flow, approval gate, or human prompt during Stage 03,
> regardless of mode (default or --yolo). The loop runs fully autonomously until
> `speckit-code-review` returns `status = pass`. This applies to every `implement`
> call inside the loop, including restarts from plan/tasks/implement.

> **Mode note**: Outside Stage 03, all interview sections apply to **default mode only**. In `--yolo` mode every human interaction outside Stage 03 is replaced by autonomous self-review (see "YOLO Mode Self-Review" section below).

## Intake Interview for Jira Issue Mode

**Default mode only.**

When run as `/speckit-auto --issue {jira link}`:

1. Load `JIRA_URL`, `JIRA_USERNAME`, and `JIRA_API_TOKEN` from root `.env`.
2. Fetch the Jira issue and summarize requirement intent.
3. Ask: "Does this summary correctly reflect the Jira requirement?"
   - Choices: `Yes`, `No`
4. If `No`, ask: "What should be corrected or clarified before we start specify?"
5. Resolve concerns before moving to `specify`.

**YOLO mode**: skip all interview steps; parse and accept the Jira issue summary autonomously. Document assumptions in pipeline log before proceeding.

## Branch Creation Before Pipeline Start

Before starting the first pipeline step, automatically create and switch to a new working branch:

1. Pick base branch by priority: `develop` -> `main` -> `master`.
2. Select the first branch that exists (local first, then remote-tracking refs if needed).
3. Create a new branch from that base branch.
4. If none of those base branches exists, stop and report the missing base-branch condition.

## Automatic Code Review After Implement

> ⚠️ **NO-STOP ZONE — both default mode and --yolo mode.**
> No human approval gates. No "do you approve?" prompts. No pausing.
> speckit-auto owns this loop entirely. The loop runs until `status = pass`.
> A `failed` result in any mode means: fix and loop again — never stop and report.

After each `implement` run, execute and maintain the following loop autonomously:

1. Invoke `speckit-code-review` using the correct method for your environment (see compatibility table in SKILL.md).
2. Receive and read the strict JSON result.
3. If `status = pass` → exit loop, proceed to the commit gate.
4. If `status = failed` → parse ALL failure fields from the JSON:
   - `Business missing`
   - `Business missing details`
   - `code issues`
   - `security issue`
   - `architecture`
   - `unit-test-coverage` — if below `"80%"`, treat as code-level failure
   - `unit-test-missings` — each entry is a specific test to write (`file`, `class_or_method`, `lines`, `reason`)
   - any additional issue fields present
   Build a concrete corrective action list, then classify and restart:
   - Plan issue → restart from `plan` → `tasks → analyze → converge → implement`
   - Task issue → restart from `tasks` → `analyze → converge → implement`
   - Code-only or unit test coverage issue → restart from `implement` only
5. Apply fixes, then GOTO step 1.
6. **Never exit this loop with `status = failed`. Never stop to ask the user for help inside this loop.**
7. Only stop (with a report) if the same failure repeats for 5 consecutive iterations unchanged.

## Extra Gate After Code Review Pass (Human Manual Review + Commit)

**Default mode only** — skipped entirely in `--yolo` mode.

After `implement` and code-review pass:

1. AI presents a concise summary of use cases and usage scenarios based on `spec.md` and `plan.md`.
2. AI explicitly recommends the human reviewer:
   - run the app
   - perform manual self-tests for those scenarios to validate requirement coverage
3. Ask for manual review result:
   - Choices: `Approve implementation`, `Request changes`
4. If `Approve implementation`:
   - Ask for commit message.
   - Run `git add -A` then `git commit -m "<commit-message>"`.
   - Mark active `spec.md` status as `completed`.
   - Commit spec status change with follow-up commit:
     - `git add <active-spec-path>/spec.md`
     - `git commit -m "chore(spec): mark <spec-id> completed"`
5. If `Request changes`:
   - Ask for detailed human feedback.
   - Route restart based on feedback:
     - Requirement change -> restart from `specify`
     - Solution change -> restart from `plan`
     - Task/detail change -> restart from `tasks`
     - Code-generation-only change -> restart from `implement`
   - If code changes are made, invoke `speckit-code-review` again and loop until `status = pass`.
   - Return to this manual review gate and repeat until approval.

## Auto Commit (--yolo mode only)

After `speckit-code-review` returns `pass`:

1. Auto-generate commit message:
   - Format: `feat(<spec-id>): <short summary from spec.md title or Jira issue summary>`
   - Example: `feat(FCM-13708): implement password validation and per-user salt generation`
2. Run `git add -A` then `git commit -m "<auto-generated-commit-message>"`.
3. Mark active `spec.md` status as `completed`.
4. Commit spec status change with follow-up commit:
   - `git add <active-spec-path>/spec.md`
   - `git commit -m "chore(spec): mark <spec-id> completed"`
5. Report commit messages and hashes in final summary.

## YOLO Mode Self-Review

Replaces all user interviews in `--yolo` mode.

After each stage output is produced:

1. Assess against:
   - **Completeness**: all required artifacts produced
   - **Consistency**: aligns with `spec.md` and prior stage outputs
   - **Coherence**: no contradictions, ambiguities, or obvious gaps
2. Pass → proceed to next stage immediately.
3. Fail → self-correct and rerun (max 2 retries).
4. Still failing after 2 retries → stop, report stage name + failure reason + suggested action.
5. Log a one-line verdict per stage in the final summary.

## Interview Flow

**Default mode only. Applies to stages: `specify`, `clarify`, `plan`, `tasks`, `analyze`, `converge`.**
**Does NOT apply during Stage 03 (implement + review loop) — see NO-STOP ZONE rule above.**

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
- **Code review failed after implement**: speckit-auto owns the loop — parse ALL review fields, build corrective actions, apply fixes, re-invoke `speckit-code-review`, and continue looping. Do NOT stop or ask the user. Only abort after 5 consecutive identical failures with no code change.
- **Human manual review requests changes** (default mode): collect feedback, classify scope, restart from `specify`/`plan`/`tasks`/`implement`, re-invoke `speckit-code-review` if code changed, then return to manual review gate.
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
