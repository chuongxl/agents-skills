# Resume

Resume is the first action on every invocation.

## Find State

If `--issue` is present, normalize it to a Jira key and look for `docs/qa/<issue>*/run.json`.
If `--issue` is absent, search `docs/qa/**/run.json`.

- No run and no `--issue`: stop and ask for an issue key unless exactly one resumable run exists.
- No run with `--issue`: route to intake.
- Multiple runs: ask which run to resume; do not infer from modified time alone.
- One run: validate it with `scripts/validate-run-state.py`.

If validation fails, stop at the state error and report the invalid field. Do not restart from Jira
to paper over broken state.

## Freshness

When a valid run has `ticket.md`, compare the ticket snapshot timestamp with Jira's current
`updated` timestamp during the next Jira read. If Jira changed after the snapshot, refresh
`ticket.md`, record the delta in `test-design.md`, and route to design review before automation.

If the ticket is unchanged, do not rewrite artifacts just because resume ran.

## Route

Use `resume_target` first:

| `resume_target` | Route |
|---|---|
| `intake` | read `intake.md` |
| `impact` | read `impact.md` |
| `brainstorm` | read `brainstorm.md` |
| `design` | read `design.md` |
| `review` | read `review.md` |
| `automation` | read `automation.md`, or finish if automation is not requested or cannot run |
| `automation-review` | read `automation-review.md` |
| `finish` | read `finish.md` |
| `done` or `null` | report current artifacts and stop unless the user asks for a new action |

## Deferred Automation

`resume_target: done` with `automation.status: deferred` is a finished run waiting for code. It is
the one `done` state that has an expected next action.

When the user resumes such a run with `--automation`, that is the new action: read `automation.md`
and follow its re-entry rules, which require re-reading the ticket before anything is written.

When the user resumes it without asking for anything, report the artifacts, the deferral reason, and
the `resume_when` condition, then stop. Do not start automating because the code now appears to
exist — the deferral was a decision, and resuming it is also a decision.

`stage` is audit context; `resume_target` is the instruction.
