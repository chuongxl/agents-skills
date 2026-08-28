# Manual Test Conversion

Turning an existing Xray Manual or Generic test into Gherkin. Load this from design when it applies;
it changes what the design gate asks and what QA review checks.

## When This Runs

A team that has been shipping for years has its test suite in Xray as Manual test cases, written by
people, reviewed by people, and run by people. Automating that feature does not start from a story —
it starts from those test cases.

Load this file when both hold:

- intake wrote `existing-tests-manual.md` (or an `existing-tests-<KEY>-manual.md` from `--related`)
  with at least one test in it;
- the human elected, at brainstorming or the design gate, to convert one or more of them.

Do not load it for a story with no existing manual coverage. That is ordinary design.

Conversion is opt-in per test. Surfacing manual coverage as dedup evidence is intake's job and
happens on every run; converting it is a decision, and a decision needs a person.

## Link, Never Overwrite

A converted scenario is imported as a **new** Cucumber test that links back to the Manual test it
came from. The Manual test is left exactly as it was.

Concretely: the scenario carries **no** `@TEST_` tag, so import creates a new Test issue, and
`run.json.conversion.converted[].manual_test` records the provenance. That field is what the finish
report reads to tell a human which manual case each new scenario came from.

The alternative — tagging the scenario `@TEST_<MANUAL-TEST-KEY>` so import updates the existing test
in place — is refused as a default. It very likely converts the issue's type from Manual to Cucumber
and replaces its hand-written steps with the Gherkin. One issue instead of two is genuinely tidier,
and the execution history stays on one issue, which is a real advantage. But the cost of being wrong
is asymmetric and that decides it: two tests covering one behaviour is untidy and reversible at any
time, while overwritten manual steps are the team's own work, gone, with a bad translation as the
thing that replaced them.

Overwrite is available, and it is a decision a human makes explicitly at the design gate, per
converted test, having seen the Gherkin. It is never the path taken by default or in bulk.

### Verify The Import Behaviour Before The First Real Run

Xray's exact behaviour when a Cucumber feature is imported over a Manual test differs by instance
and version. **Confirm it against a throwaway test in the target project before the first production
import**, and record what was observed. Do not discover it on a batch of two hundred.

This skill performs no Xray write, so the confirmation and the import both belong to whoever owns
that step — see the Xray boundary in `protocol.md`.

## The Gate Is Fidelity, Not Design Quality

An ordinary design gate asks: are these the right tests? A conversion gate asks something narrower
and stricter: **is this the same test?**

The manual case was already reviewed and has been executing for years. The scenario replacing it is
not an improvement opportunity. Present the two side by side — original steps against Gherkin — and
let the human check the translation.

Improvements are not forbidden; they are just not silent. A conversion that adds a boundary case the
manual test never had, splits one manual case into three scenarios, or drops a step as redundant is
**reported as a deviation**, itemized, and approved separately. Unreported, it is indistinguishable
from a mistranslation, and a reviewer comparing two documents will not catch what was quietly added.

## Granularity Is Not Preserved Automatically

A manual test case is frequently one long procedure asserting five things, because a human executing
it reads top to bottom once. Scenario granularity says one behaviour per scenario, with negative and
boundary cases standing alone.

These conflict, and the conventions win: one manual case may become several scenarios. Every one of
them records the same `manual_test` key, and the split is reported at the gate as the deviation it
is.

The reverse never happens. Several manual cases are never merged into one scenario — that loses the
one-to-one trace back to what the team already runs, and the trace is most of the value of doing
this at all.

## Steps That Do Not Translate

Manual test steps are written for a reader who can improvise. "Verify the layout looks correct",
"check the report is reasonable", "log in as any user with approval rights" — none has a mechanical
assertion behind it.

Three outcomes, and the choice is asked, never assumed:

| The step | Outcome |
|---|---|
| Has a mechanical assertion hiding in it | Write it, and report the interpretation as a deviation |
| Genuinely needs human judgement | The scenario is recorded with surface `manual`, with that step quoted as its one-line reason |
| Cannot be understood at all | Ask, once. An unanswerable step blocks that scenario, not the run |

Never invent an assertion to make a step automatable. A scenario that passes while asserting
something the manual test never asserted is worse than the manual test — it reports coverage that
does not exist.

## Requirement Linkage

Every scenario needs a `@REQ_` tag, and a Manual test does not necessarily have a requirement.

- Take the requirement from the manual test's own requirement links when intake captured them.
- Otherwise take the issue this run is anchored on, when the manual test covers its behaviour.
- Neither resolves — ask, once, for the issue that owns the behaviour. A scenario with no
  requirement traces to nothing, and traceability is the reason these tags exist.

## QA Review Asks Fidelity In Both Directions

A run containing conversions adds a fidelity task set to QA review, asked **both ways**:

- What does the source Manual test assert that the Gherkin does not — a dropped step, a lost
  precondition, an assertion softened into a navigation?
- What does the Gherkin assert that the source does not — an added boundary case, an invented
  assertion, one case silently split into three?

Both, because this file already treats the two as equivalent: a silent addition is *indistinguishable
from a mistranslation*. A review asking only what was dropped audits one of the two ways a
conversion goes wrong and reports clean on the other.

## Batches Are Bounded By The Gate, Not By The Loop

Converting a backlog is a real workload — hundreds of cases. The gate is one human reading everything
the run produced, not one review per scenario.

A single run producing more scenarios than a human will actually read at one sitting has not saved
anybody anything; it has moved the bottleneck from writing to reviewing and hidden it behind an
approval nobody could give properly. Split by component or by functional area, and say so when the
batch was split.

## State

```json
"conversion": {
  "status": "approved",
  "converted": [
    {
      "manual_test": "MOM-2001",
      "scenarios": ["Attach invoice to candidate"],
      "deviations": ["split one manual case into two scenarios"],
      "mode": "link"
    }
  ]
}
```

`conversion.status` is one of `not-run`, `pending`, or `approved`. `mode` is `link` or `overwrite`,
and `overwrite` is written only after a human approved that specific test for it. A run with no
conversion keeps `{"status": "not-run", "converted": []}`.

## Red Flags — thoughts that lose the team's existing work

| Thought | Reality |
|---|---|
| "Tagging it `@TEST_` keeps Xray tidy — one issue instead of two" | That very likely overwrites the manual steps. Tidy is reversible; overwritten work is not. Link by default; overwrite only per-test, explicitly, after a human has seen the Gherkin |
| "The manual test's step 4 is redundant, I'll drop it" | Report it as a deviation and let the human drop it. Silent removal is indistinguishable from mistranslation |
| "This step is vague, I'll write a reasonable assertion" | Never invent an assertion. Either the scenario's surface is `manual` with the step as its reason, or it is asked |
| "The manual case is one procedure, so it becomes one scenario" | Granularity conventions win. One case may become several scenarios, all recording the same `manual_test`, and the split is reported |
| "Three manual cases overlap, I'll merge them into one clean scenario" | Never merge. The one-to-one trace back to what the team runs today is most of the value here |
| "Two hundred cases in this area, convert them all in one run" | The gate is one human reading the output. Split by component and say the batch was split |

---

Provenance: restored from `references/shared/manual-conversion.md`, deleted in commit `4f0ca73`, and
adapted to the flat reference layout and JSON run state.
