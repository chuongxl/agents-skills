# Finish

Finish validates artifacts, writes a concise report, and performs optional git/PR work.

## Validate

Run:

```bash
python3 speckit-qa-auto/scripts/validate-run-state.py docs/qa/<issue>/run.json
```

Confirm every feature file named by `run.json` exists. If automation ran, confirm
`automation-result.json` exists and summarize passed, failed, blocked, and not-run scenarios.
Confirm `review.status: passed` before reporting the run as ready for automation, finish, commit, or
PR.

## Report

Report:

- artifact folder path;
- feature files created or changed;
- dedup status;
- QA review status and any unresolved Minor notes;
- Xray availability;
- adapter used or reason automation was skipped;
- blocked scenarios and why they remain in the source feature file.

## Git and PR

Commit only reviewed artifact and adapter output paths. Do not use `git add -A` when unrelated
working-tree changes exist.

If `--pr` was requested and the host can create a PR, prepare it after validation. The PR summary
should make clear that Xray writes are not performed by this skill.
