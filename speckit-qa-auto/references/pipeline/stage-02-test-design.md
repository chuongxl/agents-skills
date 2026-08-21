# Stage 02: Test Design

Loads: [run-state.md](../shared/run-state.md), [operating-rules.md](../shared/operating-rules.md),
[selector-verification.md](../shared/selector-verification.md),
[gherkin-conventions.md](../shared/gherkin-conventions.md), and — only when this run converts
existing Manual tests — [manual-conversion.md](../shared/manual-conversion.md), and — only when a
review finding raises `run.design_depth` — [impact-analysis.md](../shared/impact-analysis.md). Four
leaves always, two more conditionally, so the reader knows the cost before paying it (design spec
§11.2 rule 1). The conditional loads are the point: a story with no existing manual coverage never
pays for the file that governs converting it, and a run whose depth is never raised never pays for
the sweep specification. `impact-analysis.md` is loaded to **re-run** the sweep at a wider breadth,
never to run it for the first time — Stage 01 owns the first run, and this stage reads its result
from run state. Every leaf this file cites by rule or condition
number is declared here: the `Loads:` line is the disclosure §11.2 rule 1 rests on, and a cited
file that goes undeclared is read from memory instead of from the file. It links to no other file
under `references/pipeline/` — its predecessor is not linked back to, and its successor is named,
never linked: **enter Stage 03** at the end of this stage, same turn.

This is the pipeline's main human gate (design spec §5, marked ◀ HUMAN GATE). Everything Stage 03
automates and Stage 04 reports on treats this stage's output as settled. It turns the acceptance
criteria Stage 01 captured in `ticket.md` into approved Gherkin, deduplicated against whatever
Xray already covers, with every UI element resolved to real evidence before approval.

## What This Stage Receives

Per `run-state.md`, read only from `execution-report.md` and the artifact folder — never from
`stage-01-intake.md`: `run.jira_key`, `run.artifact_dir`, `profile.*`, `xray.query`,
`xray.cucumber_tests`, `xray.manual_tests`, and, on disk inside `run.artifact_dir`, `ticket.md`,
`existing-tests.feature`, and `existing-tests-manual.md`. `existing-tests.feature` is empty and
`existing-tests-manual.md` absent when Xray was unavailable at Stage 01 — that absence is itself
an input to step 2.2.

Also `run.design_depth` with the reason Stage 01 recorded for it, `impact.*`, and
`impact-candidates.md` on disk. This stage does not run the impact sweep; it reads what Stage 01
left behind. `impact-analysis.md` is therefore declared as a **conditional** load, and only for the
one case that needs it: a review finding that raises `design_depth`, which re-runs the sweep at the
new breadth.

## Execution Order

The steps below run in the order design spec §5 fixes. They are numbered 2.1 through 2.8, with
2.4b inserted between 2.4 and 2.5 — the numbering marks position, not a count.

### 2.1 Requirement analysis

Turn the **whole ticket** into a list of testable behaviours — every section, at every depth, not
the acceptance-criteria table alone. A blocking ambiguity — one that would make a behaviour
impossible to write correctly either way — is asked **once**. A non-blocking one is recorded under
Open Questions in `test-design.md` and the run continues; not every open question earns a stop.

**No rule attaches to any heading name.** Headings are how a writer organized their thoughts, not a
schema. A rule keyed to `Out-Scope` patches one ticket layout and misses the next one that files its
constraint under `Notes`, and a section titled for exclusions routinely mixes *we are not building
this* with *the system must not do this* — the first is out of scope, the second is a behaviour to
test. Judge each sentence by what it says.

Which lines are testable constraints is a judgement, and it is the judgement this step has already
got wrong once: a story whose exclusions section carried "do not allow user/system modify any
candidate has attached to APM's invoice" produced eight scenarios, none of them that one, and a
coverage matrix reporting that no criterion was uncovered. The answer is not a stricter rule here —
a stricter rule would have the same author and the same blind spot. It is the second question asked
at 2.7b, whose scope this step does not set.

### 2.2 Dedup against Xray

Every behaviour from 2.1 is labelled `NEW`, `UPDATE <TEST-key>`, `SKIP (covered by <TEST-key>)`,
or `REVIEW <TEST-key>`. This is a mechanical rule, not a judgement call — see "Dedup Is A Rule, Not
A Judgement" below. The stage records its own `xray.dedup: ran | not-run` here; Stage 01
deliberately left that field unset, since it only records that the Xray fetch happened, not
whether dedup ran against the result.

**Dedup is a rule, not a position in the order.** The normalized-key match is applied wherever a
scenario comes into existence — including the impact scenarios designed at 2.4b, which is after this
point, and including scenarios added when 2.7b sends the design back for another round. A
step-shaped reading would leave both unlabelled while 2.7 requires every behaviour to carry a label.

Two labels are forbidden in the impact file, and nowhere else: `UPDATE` and `SKIP`. A key match
there is labelled `REVIEW-OVERLAP <TEST-key>` — a distinct label, not a reuse of `REVIEW`, which
this stage defines as *an existing test matching nothing in the new design*, the opposite direction.
One field carrying both directions under one name leaves the gate and the Stage 04 report unable to
tell them apart. See `gherkin-conventions.md` for why the other two are refused: either would
decide, with no human involved, that another story's Test issue now belongs to this one.

### 2.3 Scenario design

**When `run.anchor_type` is `test`, or discovery returned Manual tests the human elected to
convert, load `manual-conversion.md` and follow it for those scenarios.** Conversion is a different
job from design: the source is an approved test that has been executing for years, so the gate at
2.8 asks whether the translation is faithful, not whether the test is a good idea. Converted
scenarios carry `design.scenarios[].source_manual_test`, carry no `@TEST_` tag, and are imported as
new Cucumber tests linked to the manual originals — never as overwrites of them.

Gherkin, one behaviour per scenario (`gherkin-conventions.md`, "Scenario Granularity"). Negative
and boundary cases are their own scenarios, not extra `And` steps folded onto the happy path. Every
scenario is assigned a `surface` — `ui`, `api`, or `manual` — matching `design.scenarios[].surface`
in the run-state contract. Build the coverage matrix: acceptance criterion → the scenario(s) that
cover it. A criterion with no row is not yet designed.

### 2.4 Element intent map

Applies to `surface: ui` scenarios only — an `api` scenario names its endpoint and fixture instead,
and a `manual` scenario carries its one-line reason; neither has elements to name.

Per `selector-verification.md`, "Two Artifacts, Two Stages", this stage writes the **element intent
map**: every element each `ui` scenario touches, named in the language of the product, together with
where it appears and what the scenario does with it. It does **not** resolve those elements to
selectors. That is the selector gate, and it runs at the head of Stage 03.

The map is required in full. A `ui` scenario that does not name what it touches fails self-review at
2.7 exactly as an unresolved selector used to — what changed is that naming an element no longer
requires the element to exist in code yet.

**When the code has not landed**, set `run.code_state: pending` and
`design.selector_evidence: deferred`. This is the ordinary case for a feature whose test cases are
written ahead of implementation, and it is not a risk to be acknowledged — `deferred` records that
there was nothing to resolve against, which is a different fact from a fallback and is kept separate
for the reason `selector-verification.md`, "Deferred Is Not Fallback" gives. A `pending` run ends
after 2.8 rather than entering Stage 03; see "Design Can Complete Before The Code Does" below.

### 2.4b Impact design

Design at least one scenario for every entry in `impact.candidates[]`, and for every entry in
`impact.declared[]` the sweep did not find. This is provisional — the human keeps or drops each
scenario at 2.8, and `impact.approved_scenarios[]` records what survived.

**Designing before approval, rather than after it, is the whole point of this step's position.** In
an earlier draft impact scenarios were authored after the gate: they passed none of 2.7's checks,
were never seen by the reviewer at 2.7b, were approved by nobody, and were still automated by Stage
03 and shipped by Stage 04. It also left 2.7b's second attack task with nowhere to put a finding — a
reviewer naming an uncovered invariant had no step to hand it to, so the one mechanism aimed at
cross-feature impact terminated in a report nothing consumed.

Each scenario states the **invariant**, not the new feature — what must remain true of behaviour
that already existed once this story ships:

```gherkin
@REQ_MOM-12194 @IMPACT @Regression_Test
Feature: Existing flows respect the APM invoice attachment

  Scenario: Refreshing candidates does not remove a candidate attached to an APM invoice
    Given a work order candidate is attached to an APM invoice
    When the user changes the work order setting and candidates are refreshed
    Then the attached candidate remains and its invoice information is unchanged
```

`@REQ_` sits at Feature level and `@IMPACT` beside it, per `gherkin-conventions.md`. The file is
`<domain>-<aspect>-impact.feature` — the main file's name plus `-impact`, derived and never
separately chosen, because the artifact folder's name is the identity everything else indexes on.

**A candidate is satisfied by a scenario or by a recorded drop.** Read `impact.dropped_scenarios[]`
before designing: a candidate a human rejected on an earlier run is not re-designed, so a resumed
run does not regenerate what that run's gate threw out. This is also what keeps 2.7 from
deadlocking — see `run-state.md` rule 15.

**The batch is bounded by the gate, not by the candidate count.** The ceiling is what one human will
actually read at one sitting, the same rule `manual-conversion.md` states for a conversion batch and
for the same reason: a run producing more scenarios than anyone reads has not saved anybody
anything, it has moved the bottleneck from writing to reviewing and hidden it behind an approval
nobody could give properly. When the list exceeds that, design the batch, **say the batch was
split**, and carry the remainder into the run that follows.

**When both lists are empty** — whether the sweep found nothing or could not run — no impact
`.feature` file is written. An empty feature file would be materialized by Stage 03 and imported by
CI as a file containing no tests. The gate's impact section still runs; its content is the sweep's
`ran` and `reason`, and the answer a human still has to give.

### 2.5 Write `.feature`

Into `<artifact_dir>/<domain>-<aspect>.feature`, and — when 2.4b designed any — into
`<artifact_dir>/<domain>-<aspect>-impact.feature`. Both go in the artifact folder Stage 01 left
behind, never the repo's test tree. Materializing into the test tree is Stage 03's job, and only for scenarios
that survive design here. Tag per `gherkin-conventions.md`: `@REQ_<STORY-KEY>` at Feature level,
`@TEST_<TEST-KEY>` at Scenario level only on `UPDATE` rows, plus the profile's `existing_tags`
carried through unchanged.

### 2.6 Write `test-design.md`

Into the same artifact folder: the scenarios, the coverage matrix, the element intent map (per
`selector-verification.md`, "The Two Map Shapes"), page objects to create or modify, the test
data and mock plan, the dedup decisions from 2.2 (including `dedup: not-run` when it applies), and
Open Questions from 2.1.

Two further sections. **§2b — impact coverage**: each candidate, the scenario or scenarios designed
for it, its evidence path, and whether it came from the sweep, the human, or both. **§9 — review
findings**, written at 2.7b and kept afterwards, *including findings that were rejected*. A review
whose findings vanish once fixed leaves the next reader unable to tell a design that was never
challenged from one that was challenged and held.

### 2.7 Self-review gate

Every one of these must hold, checked mechanically, not asked about:

- Every acceptance criterion from `ticket.md` is covered by at least one scenario
- No `TODO`, `TBD`, or other placeholder anywhere in the `.feature` file or `test-design.md`
- Every `surface: ui` scenario names every element it touches in the element intent map
- Every `surface: api` scenario names its endpoint and its request/response fixture
- Every `surface: manual` scenario carries its one-line reason
- Every behaviour carries a dedup label from step 2.2

A failing check is fixed at its source — in the scenario, the element intent map, or the design,
not by loosening the check — then re-verified. **The same check failing 3 consecutive times stops the
run** (`operating-rules.md`, Turn-Ending Condition 4).

### 2.8 Human gate

Present the summary: the coverage matrix, the dedup labels, the element intent map, and Open
Questions. Take approval or revisions — a revision returns to whichever of 2.1–2.7 it affects and
re-runs self-review before returning here. On approval, commit the design artifacts.

Where the run goes from there depends on two fields and nothing else:

| `run.code_state` | `run.design_only` | Next |
|---|---|---|
| `landed` | `false` | Take the single start-automation confirmation and **enter Stage 03 in the same turn** — no second prompt between approval and automation starting |
| `landed` | `true` | End the run here; `run.resume_from: 03` |
| `pending` | either | End the run here; `run.resume_from: 02.4` — the selector gate re-runs when the code lands |

A `pending` run resumes at 02.4 rather than at 03 because the intent map has to be checked against
what was actually built before anything generates against it. The design was approved without the
code; the code may not match it.

## Design Can Complete Before The Code Does

Writing test cases ahead of implementation is normal QA practice, not an edge case, and this stage
supports it directly: `run.code_state: pending` lets the design finish, be reviewed, be approved,
and be committed with no frontend to read. Nothing is loosened to allow it — the intent map is still
required in full, self-review still runs every check, and the human gate still gates.

What a `pending` run cannot do is enter Stage 03. Selectors resolve against code, and there is no
code; a run that automated anyway would generate against selectors nobody could verify. So the run
ends after this stage and resumes at 02.4 once the feature exists.

`--design-only` ends the run in the same place for a different reason: the team wants approved
Gherkin now and automation later. It is a scheduling choice, not a fact about the world, and it is
recorded separately (`run.design_only`) so the two never get confused. A run can be design-only with
the code fully landed — a team converting a backlog of existing manual test cases has every reason
to want exactly that.

Neither field skips a gate. There is no mode in this pipeline that skips a gate.

## Dedup Is A Rule, Not A Judgement (design spec §5.1, D13)

Two runs over the same story, with Xray unchanged, must produce an identical set of labels — so
matching is defined mechanically, never left to a model deciding whether two scenarios "look like"
the same test.

**Normalized scenario key** — lowercase; strip tags, the leading `Scenario:` / `Scenario Outline:`
prefix, punctuation, and collapsed whitespace; strip quoted literals and numbers so parameter
values do not split otherwise-identical scenarios.

| Condition | Label |
|---|---|
| Key matches an exported Cucumber scenario, step sequence identical | `SKIP (covered by <TEST-key>)` |
| Key matches, step sequence differs | `UPDATE <TEST-key>` — carries `@TEST_<TEST-KEY>`, import updates in place |
| No key match anywhere | `NEW` |
| An existing test's key matches nothing in the new design | `REVIEW <TEST-key>` — reported at the human gate, never deleted or modified by the pipeline |

Matching runs only against `existing-tests.feature` — the Cucumber export, which is Gherkin and
therefore has a normalized key to compare. `REVIEW` never triggers a delete or an edit of the
existing test; it is a report line for the human at 2.8, nothing more.

### Non-Cucumber Tests Are Advisory (D14)

`existing-tests-manual.md` is a markdown table — key, summary, labels, and steps when available —
not Gherkin, so no normalized key can be computed against it and no key match is possible. Manual
and Generic Xray tests from that file are presented at the 2.8 human gate as *possible overlap,
decide yourself*. **They never produce an automatic `SKIP`.** Silently treating a Manual test as
uncovered creates a duplicate test; silently treating it as covered drops real coverage. Neither
error is acceptable from an automated read of a summary line, so a human decides — the pipeline
does not.

### When Xray Was Unavailable

If Stage 01 recorded that the Xray fetch did not happen, `existing-tests.feature` is empty and
`existing-tests-manual.md` is absent. Every behaviour from 2.1 is labelled `NEW`, and
`test-design.md` records `dedup: not-run` with the reason Stage 01 gave for the unavailability. An
unrun dedup must never be indistinguishable from one that ran and found nothing — `not-run` and "ran,
zero matches" are different facts, and collapsing them would let a credentials outage silently
report full coverage.

## What This Stage Produces

Written into run state:

- `run.stage: 02`, written on entering this stage, so a run interrupted inside it resumes here
- `design.selector_evidence` — `deferred` when `run.code_state` is `pending`; otherwise left unset
  here, since the value that records how elements actually resolved is written by the Stage 03 entry
  gate, not by this stage
- `run.code_state` — `landed | pending`, resolved at 2.4
- `design.scenarios[]` — one entry per scenario, each carrying `name`, `surface`, `dedup`, and
  `status: pending` (Stage 03 is what moves a scenario off `pending`)
- `xray.dedup` — `ran | not-run`, from step 2.2

And, on disk inside `run.artifact_dir`: the `.feature` file(s) from 2.5 and `test-design.md` from
2.6.

## Enter Stage 03

Once the human gate is passed and the design artifacts are committed, enter Stage 03 in the same
turn — unless 2.8's table sent the run elsewhere. A `pending` or `--design-only` run ends here
instead, with `resume_from` set, and that ending is a success path: the artifacts are written,
approved, and committed, and the run has produced exactly what it was asked for.

## Red Flags — thoughts that mean a gate is being bent

| Thought | Reality |
|---|---|
| "These two scenarios are basically the same test, I'll call it a SKIP" | Dedup is a normalized-key match, not a similarity judgement. Compute the key and the step sequence; do not eyeball it |
| "The Manual test's summary clearly covers this, mark it SKIP" | Manual tests are advisory only. No automatic SKIP is possible against them — surface the overlap at 2.8 and let the human decide |
| "Xray was unavailable, so there's nothing to dedup against — just leave the field blank" | Blank looks like it ran and found nothing. Record `dedup: not-run` with the reason, every time |
| "The code isn't written yet, so I'll leave the elements vague and let Stage 03 work them out" | The intent map is required in full here. `code_state: pending` defers *resolving* elements to selectors, never *naming* them |
| "This is `--design-only`, so self-review can be lighter" | `--design-only` changes where the run stops, not what it checks. Every 2.7 check runs in full |
| "One element is unnamed, but the rest of the map is done — good enough to pass 2.7" | Self-review checks every element of every `ui` scenario. One missing row fails the gate. Name it, or reclassify the scenario's `surface` with a reason — marking the scenario blocked is not an exit here, since this stage leaves every scenario `pending` and `blocked` is a Stage 03 verdict |
| "This failed self-review before, I'll just approve it at 2.8 and fix it in Stage 03" | Stage 03's fix loop cannot edit `.feature` files at all (`operating-rules.md`). A design defect that reaches 2.8 unfixed stays a defect through automation |
