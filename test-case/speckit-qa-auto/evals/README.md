# speckit-qa-auto evals

Six end-to-end evals over the capabilities restored after commit `4f0ca73` deleted them: impact
analysis, Manual-test conversion, `--related` coverage, and deferred automation.

These are behaviour evals, not unit tests. `tools/test_speckit_qa_auto_scripts.py` proves the
validator rejects malformed state; these prove a run *produces* the right state and artifacts from
a realistic starting point.

## Layout

```text
evals/
  evals.json        6 prompts, 29 assertions
  grade.py          grades the mechanical assertions against a produced run folder
  fixtures/
    related-coverage-dedup/       MOM-12500 — sibling coverage reachable only through --related
    manual-conversion-fidelity/   MOM-12550 — one Manual test carrying all three conversion failures
```

Evals 1-3 reuse the existing `../fixtures/out-scope-constraint/` and
`../fixtures/constraint-under-notes/`, which were captured from the real run that motivated the
impact design. Eval 6 needs no fixture; it starts from a bare issue.

## Running one

Copy the fixture into a scratch repository as `docs/qa/<issue>/`, run the skill with the eval's
prompt, then grade what it produced:

```bash
python3 test-case/speckit-qa-auto/evals/grade.py 4 /path/to/scratch/docs/qa/MOM-12500
```

`grade.py` writes `grading.json` beside the run and prints a summary.

## What grade.py will and will not decide

It grades the assertions a script can decide — enum values in `run.json`, a missing file, a tag in a
feature file, a filename cited in `test-design.md`.

It prints the rest as a reviewer checklist instead of guessing. Assertions like *"resume_when names
something a person can check later"* or *"the vague verification step never becomes an invented
assertion"* are judgements, and a keyword match that approximated them would report a pass on
exactly the failure these evals exist to catch. An abstention is information; a fabricated pass is
not.

## Baseline

For a before/after comparison, run the same prompts against the skill as it stood at `4f0ca73`:

```bash
git show 4f0ca73:speckit-qa-auto > /dev/null   # confirm the ref
git worktree add /tmp/qa-baseline 4f0ca73
```

Evals 3-6 are expected to fail there outright — impact analysis, manual conversion, `--related`
wiring, and the deferred state did not exist at that commit. Evals 1-2 are the interesting ones:
they test whether the run reads the whole ticket, which is the behaviour the deleted adversarial
review used to enforce.
