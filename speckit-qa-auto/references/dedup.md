# Dedup

Dedup is a mechanical coverage labeling pass. It should be repeatable over the same inputs.

## Inputs

Use all available existing coverage:

- `existing-tests.feature` from Xray Cucumber tests;
- repository `.feature` files outside the active artifact folder;
- manually converted coverage summarized in `existing-tests-manual.md`, when useful to the design.

For Gherkin-to-Gherkin comparison, run:

```bash
python3 speckit-qa-auto/scripts/dedup-gherkin.py \
  --existing docs/qa/<issue>/existing-tests.feature \
  --existing path/to/repo-existing.feature \
  --candidate docs/qa/<issue>/<domain>.feature
```

## Labels

Use these labels in `test-design.md`:

| Label | Meaning |
|---|---|
| `NEW` | no normalized scenario match exists |
| `SKIP` | same normalized scenario and steps already exist |
| `REVIEW` | similar title exists, but steps differ or manual coverage needs judgement |

Dedup does not decide automation scope. It tells the human and any automation workflow what already
exists.

After labels are recorded in `test-design.md`, keep `review.status: pending` and route to
`resume_target: review`.
