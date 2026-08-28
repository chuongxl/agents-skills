# Finish

Finish validates artifacts, writes a concise report, and performs optional git/PR work.

## Validate

Run:

```bash
python3 "$SKILL_DIR/scripts/validate-run-state.py" docs/qa/<issue>/run.json
```

`$SKILL_DIR` is wherever this skill is installed. The path is not relative to the target repository,
which is where the run's working directory is.

Confirm every feature file named by `run.json` exists. When automation is `deferred`, confirm there
is no `automation-result.json` and that `deferred.reason` and `deferred.resume_when` are both
recorded. If automation ran, confirm `automation-result.json` exists, `automation.review.status: passed` when automation code changed,
and summarize passed, failed, blocked, and not-run scenarios.
Confirm `review.status: passed` before reporting the run as ready for automation, finish, commit, or
PR.

## Report

Report:

- artifact folder path;
- feature files created or changed;
- dedup status, and which coverage sources it was computed against;
- impact: whether the sweep ran and why not if it did not, how many candidates it returned, which
  became scenarios, and which were dropped with what reason;
- **regression recommendation** — the existing tests Branch B inventoried for the same entity or
  screen, as file paths and scenario names for a human to re-run. This is a recommendation, never a
  prediction that any of them fails, and never automation scope for this run;
- converted manual tests, each with its source key, its resulting scenarios, its declared
  deviations, and whether it was linked or overwritten;
- QA review status and any unresolved Minor notes;
- Xray availability;
- automation tool/skill used, or — when automation is `deferred` — the deferral reason and the
  `resume_when` condition, stated as the next action rather than as a gap;
- blocked scenarios and why they remain in the source feature file.

## Git and PR

Commit only reviewed artifact and automation output paths. Do not use `git add -A` when unrelated
working-tree changes exist.

If `--pr` was requested and the host can create a PR, prepare it after validation. The PR summary
should make clear that Xray writes are not performed by this skill.
