# Stage 02: Spec/Design Flow

Load this only while executing stages:
`speckit.specify -> speckit.clarify -> speckit.plan -> speckit.tasks -> speckit.analyze -> speckit.converge`

## Stage Order (must not skip)

1. `speckit.specify`
2. `speckit.clarify`
3. `speckit.plan`
4. `speckit.tasks`
5. `speckit.analyze`
6. `speckit.converge`

## Prompt Wiring Rules

- `specify`: requirement text (or normalized Jira intake output)
- `clarify`: current `spec.md`
- `plan`: finalized `spec.md`
- `tasks`: spec + plan context
- `analyze`: `spec.md`, `plan.md`, `tasks.md`
- `converge`: artifacts + current codebase, append remaining unbuilt work to `tasks.md`

## Review Behavior Per Stage

- **Default mode**: run post-stage interview and capture feedback/constraints.
- **YOLO mode**: self-review stage output; if failed, rerun stage (max 2 retries).

## Restart Routing from Human Feedback (Default mode)

- Requirement intent change -> restart from `speckit.specify`
- Solution/architecture change -> restart from `speckit.plan`
- Task/detail change -> restart from `speckit.tasks`
