# Dedup

Dedup is a mechanical coverage labeling pass. It should be repeatable over the same inputs.

## Inputs

Use all available existing coverage:

- `existing-tests.feature` — Cucumber tests covering this issue;
- `existing-tests-<KEY>.feature` — Cucumber tests covering each `--related` key;
- repository `.feature` files outside the active artifact folder;
- `existing-tests-manual.md` and `existing-tests-<KEY>-manual.md` — Manual and Generic coverage.

Pass every Gherkin source to the script. Missing one silently shrinks the corpus the labels are
computed against, and a `NEW` label computed against a partial corpus is indistinguishable from a
correct one.

`$SKILL_DIR` below is wherever this skill is installed — the path is not relative to the target
repository, which is where the run's working directory is.

```bash
python3 "$SKILL_DIR/scripts/dedup-gherkin.py" \
  --existing docs/qa/<issue>/existing-tests.feature \
  --existing docs/qa/<issue>/existing-tests-<KEY>.feature \
  --existing path/to/repo-existing.feature \
  --candidate docs/qa/<issue>/<domain>.feature
```

The script takes one `--candidate` per invocation. Run it once per authored `.feature` file and
record all results in `test-design.md`.

## Manual Coverage Is Not Machine-Comparable

`existing-tests-manual.md` is a markdown table of verbatim Xray steps. The script parses Gherkin
only, so manual coverage never reaches it.

This matters most on exactly the projects where it hurts most: where automation trails the manual
suite, the manual file is the majority of real coverage and the script sees none of it. Do not read
an all-`NEW` script result as evidence that nothing is covered. Read the manual tables and label by
judgement, marking those `REVIEW` with the manual test key in the rationale.

A manual test that was converted to Gherkin under `manual-conversion.md` becomes comparable, and its
converted scenarios go through the script like any other.

## Labels

Use these labels in `test-design.md`:

| Label | Meaning |
|---|---|
| `NEW` | no normalized scenario match exists |
| `SKIP` | same normalized scenario and steps already exist |
| `REVIEW` | similar title exists, but steps differ or manual coverage needs judgement |

Record which file each `SKIP` and `REVIEW` matched against. A label without its provenance cannot be
re-checked by a reviewer, and the whole point of separate per-key export files is that the match
reports the right source.

Dedup does not decide automation scope. It tells the human and any automation workflow what already
exists.

After labels are recorded in `test-design.md`, keep `review.status: pending` and route to
`resume_target: review`.
