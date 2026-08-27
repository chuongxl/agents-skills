# Resume

Resume is the first action on every invocation.

## Find State

If `--issue` is present, normalize it to a Jira key and look for `specs/qa/<issue>*/run.json`.
If `--issue` is absent, search `specs/qa/**/run.json`.

Validate state with `scripts/validate-run-state.py`.

## Route

Use `resume_target` first:

| `resume_target` | Route |
|---|---|
| `intake` | read `references/pipeline/stage-01-intake.md` |
| `brainstorm` | read `references/pipeline/stage-02-qa-design.md` |
| `design` | read `references/pipeline/stage-02-qa-design.md` |
| `review` | read `references/pipeline/stage-02-qa-design.md` |
| `automation` | read `references/pipeline/stage-03-automation-review.md` |
| `automation-review` | read `references/pipeline/stage-03-automation-review.md` |
| `finish` | read `references/pipeline/stage-04-finish.md` |
| `done` or `null` | report current artifacts and stop unless user requests new action |
