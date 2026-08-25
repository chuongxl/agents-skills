# Stage 02: Test Design

Loads: [run-state.md](../shared/run-state.md), [operating-rules.md](../shared/operating-rules.md),
[selector-verification.md](../shared/selector-verification.md),
[gherkin-conventions.md](../shared/gherkin-conventions.md),
[gate-presentation.md](../shared/gate-presentation.md), and — only when this run converts
existing Manual tests — [manual-conversion.md](../shared/manual-conversion.md), and — only when a
review finding raises `run.design_depth` — [impact-analysis.md](../shared/impact-analysis.md). Five
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

This stage carries the pipeline's two main human gates (design spec §5, marked ◀ HUMAN GATE): the
**approach gate at 2.2b**, which settles how the story will be tested before any Gherkin exists, and
the **design gate at 2.8**, which settles what was written. **Both are presented under
`gate-presentation.md`**, which owns everything a person reads and is why no step below specifies
its own wording: one question per message, alternatives carried by the choices, and no step number,
field name, or rule quoted at a reader. Everything Stage 03 automates and Stage
04 reports on treats this stage's output as settled. It turns the acceptance
criteria Stage 01 captured in `ticket.md` into approved Gherkin, deduplicated against whatever
Xray already covers, with every UI element resolved to real evidence before approval.

## What This Stage Receives

Per `run-state.md`, read only from `execution-report.md` and the artifact folder — never from
`stage-01-intake.md`: `run.jira_key`, `run.artifact_dir`, `profile.*`, `xray.query`,
`xray.cucumber_tests`, `xray.manual_tests`, and, on disk inside `run.artifact_dir`, `ticket.md`,
`existing-tests.feature`, `existing-tests-manual.md`, and `existing-tests-index.md`.
`existing-tests.feature` is empty and `existing-tests-manual.md` absent when Xray was unavailable at
Stage 01 — that absence is itself an input to step 2.2.

`existing-tests-index.md` is the **cheap read**: one row per test across both exports, carrying each
test's `Test Objective:` line or `no description`. Read it first and use it to decide which manual
tests' full step tables are worth reading closely. It orders attention and nothing else — it does
not shorten either export, and 2.2 matches against all of both whatever the index says
(`run-state.md` rule 19).

Also `discovery.related_candidates[]` — the stories Sweep 1 found along its five axes, each with
its `matched_by` — which this stage offers at the approach gate and reads the content of only after
a human has picked. `discovery.related_read[]` arrives absent, and absent is not empty.

Also `run.design_depth` with the reason Stage 01 recorded for it, `impact.*`, and
`impact-candidates.md` on disk. This stage does not run the impact sweep; it reads what Stage 01
left behind. `impact-analysis.md` is therefore declared as a **conditional** load, and only for the
one case that needs it: a review finding that raises `design_depth`, which re-runs the sweep at the
new breadth.

## Execution Order

The steps below run in the order design spec §5 fixes. They are numbered 2.1 through 2.8, with
2.2b inserted between 2.2 and 2.3, 2.4b between 2.4 and 2.5, and 2.7b between 2.7 and 2.8 — the
numbering marks position, not a count.

Stage 02 has **two** human gates: the approach gate at 2.2b and the design gate at 2.8. Everywhere
this file said "the human gate" before there was one of each, it now names the step.

### 2.1 Requirement analysis

Turn the **whole ticket** into a list of testable behaviours — every section, at every depth, not
the acceptance-criteria table alone. A blocking ambiguity — one that would make a behaviour
impossible to write correctly either way — is asked **once**. A non-blocking one is recorded under
Open Questions in `test-design.md` and the run continues; not every open question earns a stop.

**Asked under `gate-presentation.md`**: one question per message, and the question carries the
question — the reading being assumed goes beneath it or into the choices, not in front of it. A run
that asks *"this story's depth resolves to cross-cutting (new state, a migration write, an explicit
prohibition); before I go further, the ticket says X, I read this as Y, is that right?"* has put
three things a reader cannot act on ahead of the one they can, and that shape was reported as
unreadable by the QA team this step serves.

**How many blocking ambiguities there are is what bounds how many questions are asked.** Nothing
else does — not the depth, not the anchor type. Every ambiguity resolved by assumption rather than
by asking goes to Open Questions, named as an assumption (`gate-presentation.md` rule 2).

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

### 2.2b Test approach gate ◀ HUMAN GATE

The first point in the pipeline where a human is asked about the *shape* of the testing, and it is
placed here because this is where changing the answer is still cheap. At 2.8 every scenario is
written, self-reviewed, and adversarially reviewed; a disagreement there costs a full redesign, and
agreement partly bought by sunk cost is the reviewer-who-is-only-noticing failure 2.8's own impact
section exists to avoid.

**Why after 2.2 and not before it.** One approach a run must be able to choose is *lean on the
coverage that already exists*, and that cannot be stated without the dedup labels 2.2 produces.
Placed earlier, the gate would ask a human to choose between options one of which it could not
describe.

Present three sections, then **stop**:

| Section | Content |
|---|---|
| Related stories | The candidates Sweep 1 found, for a human to pick which are worth reading |
| Questions | Only questions whose answer changes the design |
| Approach | Alternatives with trade-offs, the recommendation first |

**`run.design_depth` is not one of them, and is not presented anywhere.** It scales the sweep's
breadth, the document's verbosity, and how many alternatives the third section offers — none of
which a reader can see or act on, which is what makes presenting it cost a turn and return a guess
(`gate-presentation.md`, rule 6). It is resolved at Stage 01 and stays internal. An earlier draft
opened this gate with it "so it can be disagreed with"; the disagreement it invited was about a
label, and the users who received it asked what the label meant.

**Related stories.** `discovery.related_candidates[]` is presented as one multi-select question,
each candidate an option carrying its summary and the axis that found it — *linked to this story*,
*same component*, *sibling under the same epic*, *matched the screen name*, *you named it*. The
answer is written to `discovery.related_read[]`, and **only those candidates have their content
read**, before the scenarios are designed.

Stage 01 deliberately stopped at keys and summaries, so this is the first point where reading is
possible at all, and it is placed at a gate that already stops rather than at one of its own. What
a person picks governs reading and nothing else: every candidate stays in `execution-report.md`, and
nothing derives a coverage judgement from a candidate nobody chose (`run-state.md` rule 20).

**What a related story teaches is a hypothesis about this one, never a fact about it.** A rule
observed in a story that was read — which statuses it applies to, what it preserves, what it
forbids — is evidence about *that* story. It becomes an assertion about this one only when this
ticket says the same thing, or when the human confirms it at this gate. Failing both, it goes to
Open Questions named as an assumption (`gate-presentation.md` rule 2), and any scenario resting on
it names the story it came from **and** that it is unconfirmed.

A borrowed rule asserted as a hard `Then` is the specific failure this exists to prevent, and it is
durable: it reads as ticket-derived to every later reader, it survives the adversarial review —
which attacks whether the design covers the ticket, not where each claim came from — and it
propagates, because the same borrowed premise usually reaches the coverage matrix and the execution
report too. The one reader who can catch it is a human who knows both stories, and by then the
design has been approved.

**Ceremony scales with `run.design_depth`. Whether an answer is taken does not** (`run-state.md`
rule 18). This is the boundary most at risk in this step: a gate that "scales to nothing" on
`trivial` is a gate that was removed.

| `design_depth` | Approaches presented | Approval |
|---|---|---|
| `trivial` | 1, in 2-3 sentences, **with the obvious alternative named and rejected in writing** | a nod suffices |
| `standard` | 2, with trade-offs and a recommendation | an explicit yes |
| `cross-cutting` | 3, with trade-offs and a recommendation | an explicit yes |

Even at `trivial`, one alternative is named and rejected. An approach offered with no alternative is
a decision presented as a fact, and `trivial` is where that is most tempting. The cost is one
sentence.

**Depth does not bound how many questions are asked, and the table no longer has a column for it.**
It carried one — `trivial` permitted *"only one that genuinely blocks"* — and that cap did not
reduce concerns, it converted them into silent assumptions, because the run must continue and the
ticket does not answer them. Ask what there is to ask; a concern left unasked is written into Open
Questions instead (`run-state.md` rule 12, `gate-presentation.md` rule 2).

**What an approach is.** A coherent position on five axes, not a slogan: the **surface mix** (which
behaviours are `ui`, `api`, `manual`); **granularity** (one scenario per criterion, or a
`Scenario Outline` with an examples table); **negative and boundary depth**; **what is left to
existing coverage** (which `SKIP`-labelled behaviours are genuinely covered); and the **test data
strategy** (fixtures, mocks, or live seeding). Shapes these combine into, as illustration and not a
fixed menu:

| | Approach | Trade-off |
|---|---|---|
| A | UI-heavy — every criterion a UI scenario, real data | Highest fidelity; slowest; most exposed to flake |
| B | API-first plus a UI smoke — invariants at the API layer, one or two UI happy paths | Fast and stable; blind to rendering defects |
| C | Thin — automate only `NEW` behaviours, leave `SKIP` rows to their existing Xray tests | Cheapest; depends entirely on dedup having run |

**When `xray.dedup` is `not-run`, approach C cannot be stated.** Say so, with the reason Stage 01
recorded for the unavailability. The gate still runs; it presents one option fewer. An unrun dedup
and a dedup that ran and found nothing are different facts everywhere else in this pipeline, and
they are different facts here.

**The questions asked here are not 2.1's questions.** 2.1 asks *"what does this line of the ticket
mean?"* and must stay at 2.1, because 2.2's dedup depends on the behaviour list being right. 2.2b
asks *"how should this be tested, and what matters to you?"* — purpose, constraints, what done looks
like. A question appearing in both lists was asked in the wrong place.

| Asked at | Kind | Recorded in |
|---|---|---|
| 2.1 | What does this line of the ticket mean? | Open Questions in `test-design.md`, or asked once when blocking |
| 2.2b | How should this be tested? What matters to you? | `design.approach_questions[]` and `test-design.md` §0 |

**Anchor resolution.**

| `run.anchor_type` | Third section becomes |
|---|---|
| `story` | approaches, per the table above |
| `epic` | approaches stated **once for the epic**, covering every child in one presentation |
| `test` | **batch scope** — which Manual tests this run converts and where the batch is cut |

An `epic` presents one gate, never one per child. The bound is 2.4b's bound and it is the same
reason: the ceiling is what one human reads at one sitting, and N gates for N children moves the
bottleneck rather than removing it. An epic too wide for one presentation is split, and the split is
stated, in the words `manual-conversion.md` uses for a conversion batch.

A `test` anchor gets **no approach menu**. The approach is fixed by the anchor — translate
faithfully — and offering alternatives would invite a redesign of an approved test that has been
executing for years, which is what `manual-conversion.md` exists to prevent. `approach_chosen`
records `faithful-conversion`. The other two sections still run: related stories are still offered,
and questions are still asked.

**An answer here may raise the depth, though nobody was asked about depth.** A human who names a
surface nobody swept, or picks a related story that widens the entity set, has changed what the
sweep should have covered — so the run raises `run.design_depth`, re-runs the impact sweep at the
new breadth by loading `impact-analysis.md`, and sets `run.depth_raised_in_02`, which is the
mechanism 2.7b already uses. The raise is a **consequence** of an answer about testing, never an
answer to a question about depth. **Lowering is refused:** the ratchet is one-way (`run-state.md`
rule 12).

**No answer ends the turn** (`operating-rules.md`, Turn-Ending Condition 14). A nod is an answer at
`trivial`. Silence is not an answer at any depth.

### 2.3 Scenario design

**When `run.anchor_type` is `test`, or discovery returned Manual tests the human elected to
convert, load `manual-conversion.md` and follow it for those scenarios.** Conversion is a different
job from design: the source is an approved test that has been executing for years, so the gate at
2.8 asks whether the translation is faithful, not whether the test is a good idea. Converted
scenarios carry `design.scenarios[].source_manual_test`, carry no `@TEST_` tag, and are imported as
new Cucumber tests linked to the manual originals — never as overwrites of them.

**Design to `design.approach_chosen`.** A scenario whose surface contradicts the approved approach
is either brought into line or carries the reason it departs — recorded, never silent, because
2.8 compares the approved approach against what was delivered and that comparison is what makes
drift visible.

Gherkin, one behaviour per scenario (`gherkin-conventions.md`, "Scenario Granularity"). Negative
and boundary cases are their own scenarios, not extra `And` steps folded onto the happy path. Every
scenario is assigned a `surface` — `ui`, `api`, or `manual` — matching `design.scenarios[].surface`
in the run-state contract. Build the coverage matrix: acceptance criterion → the scenario(s) that
cover it. A criterion with no row is not yet designed.

**Every scenario is also assigned a `priority`, derived from the ticket's own.** `ticket.md` carries
the story's Jira `priority` in its front matter; that value is the anchor, and the scale is whatever
the project's Jira uses — never one this skill invents:

| Scenario | `design.scenarios[].priority` |
|---|---|
| Happy path of a main acceptance criterion | the ticket's priority |
| Negative or boundary case | one level below |
| Rare edge case | two levels below |

Floored at the project's lowest level. Anchoring to the ticket avoids asking this skill for a
judgement it has no standing to make — *how important is this feature in absolute terms* — while
still separating the happy path from the edge case inside one ticket, which inheriting the ticket's
priority flat would lose. The value is proposed, not settled: a human adjusts it at 2.8.

**A scenario converted from a Manual test takes that test's priority and does not re-derive it.**
The source is an approved test that has been executing for years, so the gate asks whether the
translation is faithful, not whether the test is a good idea (`manual-conversion.md`). Re-deriving
its priority would re-decide something already decided, through a door the conversion path exists to
keep shut.

The level is written into the `.feature` file as `@Priority_<Level>` on the scenario, per
`gherkin-conventions.md`. That is what carries it to Xray through the import CI already runs — this
skill writes nothing to Xray directly.

### 2.4 Element intent map

Applies to `surface: ui` scenarios only — an `api` scenario names its endpoint and fixture instead,
and a `manual` scenario carries its one-line reason; neither has elements to name.

Both of those are **anchors, and an anchor is written on the scenario in the `.feature` file**, per
`gherkin-conventions.md`'s Anchor section — `# endpoint:` / `# fixture:` comment lines for `api`, the
reason comment for `manual`. `test-design.md` records why that endpoint is the right vantage point
and cites the file; it does not restate the values. Only `ui` scenarios put a map in
`test-design.md`, because a selector map is what the Stage 03 entry gate consumes and a `.feature`
file has no place to carry one.

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
carried through unchanged, placed at the level `profile.tag_placement` records.

**Anchor every scenario** per `gherkin-conventions.md`'s Anchor section. A `Background:` naming the
entry point when — and only when — every scenario in the file is `surface: ui` and shares one, and
`profile.background_style` is `entry-point`; otherwise each `ui` scenario opens with its own `Given`.
`api` scenarios carry `# endpoint:` and `# fixture:`; `manual` scenarios carry their reason. Scenario
names follow `profile.scenario_name_style`. These three profile fields are the repository's
convention, not this skill's preference: a file that anchors correctly in a shape the repo does not
use is still a file a reviewer rewrites by hand.

### 2.6 Write `test-design.md`

Into the same artifact folder: the scenarios, the coverage matrix, the element intent map (per
`selector-verification.md`, "The Two Map Shapes"), page objects to create or modify, the test
data and mock plan, the dedup decisions from 2.2 (including `dedup: not-run` when it applies), and
Open Questions from 2.1.

**§0 — Test approach**, placed first because it is the frame every later section sits inside: the
approach chosen and why, **every alternative considered with the reason it was rejected**, the
clarifying questions from 2.2b with their answers, which related stories the human chose to have
read, and the depth at the time of approval together with whether an answer at the gate raised it.
Depth appears in this document and never at the gate: `test-design.md` is a committed artifact whose
readers are auditing the run, which is exactly the reader a machine-facing field serves. Rejected alternatives are kept for the reason §9 keeps rejected
review findings: a choice recorded without the options it beat leaves the next reader unable to tell
a design that was never considered from one that was considered and held.

**§0b — Test case description**, one block per scenario set (the main set, and the impact set when
2.4b designed one). This is the block a person pastes into the Jira or Xray Description field, so it
is written in that field's own format:

```
Test Objective: <one paragraph — what is verified, under what conditions, with which
precedence rules, and what outcome or placement is expected>

Scenario:
1: <scenario name, exactly as it appears in the .feature file>
2: <…>
```

**The objective is written; the numbered list is derived** — generated from `design.scenarios[]` in
file order, never authored by hand. A hand-written list is a second statement of the same fact, and
the two disagree the first time a scenario is renamed at 2.8. 2.7 checks the derivation by
comparison rather than by judgement.

The impact set's block states the **invariants**, not the feature. One merged block would claim a
single objective over two sets that exist for opposite reasons — what the story builds, and what the
story must not break.

**This block is not written into the `.feature` file, and that is deliberate.** A description in the
ticket's format contains a line reading `Scenario:`, and in a `.feature` file that is a keyword —
Gherkin would parse it as a scenario with an empty name and `bddgen` would compile it. `Scenarios:`
is no safer; it is an alias for `Examples:`. Markdown makes the hazard disappear instead of working
around it, and lets the block match the field's format verbatim. Whether Xray's Cucumber import
would carry a Feature-level description onto the imported Test issue is unverified, so the benefit
that would justify the risk is unconfirmed.

Two further sections. **§2b — impact coverage**: each candidate, the scenario or scenarios designed
for it, its evidence path, and whether it came from the sweep, the human, or both. **§9 — review
findings**, written at 2.7b and kept afterwards, *including findings that were rejected*. A review
whose findings vanish once fixed leaves the next reader unable to tell a design that was never
challenged from one that was challenged and held.

### 2.7 Self-review gate

Every one of these must hold, checked mechanically, not asked about:

- `design.approach_chosen` is present and `design.approach_alternatives[]` is non-empty
  (`run-state.md` rule 18)
- `test-design.md` §0b holds one description block per scenario set the run produced, and each
  block's numbered list matches that set's scenario names in **count and order**
- Every acceptance criterion from `ticket.md` is covered by at least one scenario
- No `TODO`, `TBD`, or other placeholder anywhere in the `.feature` file or `test-design.md`
- Every `surface: ui` scenario names every element it touches in the element intent map
- Every `surface: api` scenario names its endpoint and its request/response fixture **on the scenario
  in the `.feature` file**, not only in `test-design.md`
- Every `surface: manual` scenario carries its one-line reason
- **Every `surface: ui` scenario has an anchor** — a `Background:` covering it, or its own opening
  `Given` naming the entry point
- **No `.feature` file holding a non-`ui` scenario carries a `Background:`.** Checked over the file,
  not the scenario: a `Background:` runs before every scenario in its file, and this is the one
  anchor defect that reads as correct in the file it was written into
- The `existing_tags` on generated scenarios sit at the level `profile.tag_placement` records, and
  scenario names follow `profile.scenario_name_style`
- Every behaviour carries a dedup label from step 2.2
- Every scenario carries a `priority`, and every scenario in the `.feature` file carries exactly one
  `@Priority_<Level>` tag matching it
- **Nothing presented to a human at either gate names a step, a run-state field, or a rule**, and no
  gate folds its alternatives into the question text (`gate-presentation.md`). This check reads what
  the gate is about to say, not what the stage file contains: the stage files are written in the
  contract's own vocabulary by design, and it is the crossing into user-facing text that this
  catches
- **No line of the ticket admitted into scope is left with two readings.** Each such line is
  resolved to one reading, and the resolution is written in `test-design.md` with **both** readings
  named. A line reading either as *this release does not build it* or as *the system must prevent
  it* is exactly the shape that has produced an uncovered constraint here before, and none of the
  six checks above looked for one.
- Every entry in `impact.candidates[]`, and every unmatched entry in `impact.declared[]`, is
  **satisfied** — by at least one scenario in the impact file, or by an entry in
  `impact.dropped_scenarios[]` (`run-state.md` rule 15). Requiring a scenario alone deadlocks the
  gate: a revision that drops a candidate's only scenario re-enters this check, fails it, and fails
  it again on every retry, which Turn-Ending Condition 4 stops on after three.
- No scenario in the impact file carries `UPDATE` or `SKIP`

A failing check is fixed at its source — in the scenario, the element intent map, or the design,
not by loosening the check — then re-verified. **The same check failing 3 consecutive times stops the
run** (`operating-rules.md`, Turn-Ending Condition 4).

### 2.7b Adversarial review

Dispatch a reviewer with `assets/adversarial-review-prompt.md`, giving it `ticket.md`, both
`.feature` files, `test-design.md`, `impact-candidates.md`, and `run.design_depth` with its reason.

**Why a second pass exists at all.** 2.7 asks *"is every acceptance criterion covered?"* and takes
its list of criteria from the pass being checked. That check is satisfiable while the ticket is
uncovered, because a criterion the extraction never admitted was one is not in the list it iterates.
2.7b asks *"which sentences in the ticket state a rule the system must uphold?"* — a question scoped
by the ticket rather than by the extraction. **The difference is the question, not the context.**
`test-design.md` states the extraction's boundary in its own opening line, so a reviewer holding it
was never isolated in the way an earlier draft claimed, and that draft's exemption for this step has
been withdrawn accordingly.

**§0 and §0b travel with `test-design.md` and are context, not targets.** The reviewer is not given
a fourth task asking whether the approach was wrong — that decision has an owner and was approved by
a human before the scenarios existed. What the existing tasks may now do is name the approach as a
*cause*: an invariant left uncovered *because* the approach put that surface at the API layer is an
ordinary task-2 finding. An objective in §0b claiming coverage no scenario provides is an ordinary
task-1 finding.

**Mode.** Prefer a subagent — a fresh context is less anchored on a conclusion it did not reach,
which is a real but unquantified benefit. Where dispatch is unavailable, run inline with the same
prompt and the same tasks, and record `design.review_mode: inline`. It is never skipped for want of
dispatch, which is why `design.adversarial_review` has no `not-run` value (`run-state.md` rule 11).

**Loop.** `Issues Found` routes by task: findings from tasks 1 and 3 return to 2.1, findings from
task 2 return to 2.4b. A finding that **can only be fixed by changing the approach** returns to
2.2b instead — a second trip through the approach gate, setting `design.approach_revised_in_02`.
Every path re-runs 2.7 and then re-reviews, and every path counts against the same three-round cap. Scenarios added carry
`origin: adversarial-review`, and are labelled where they are created — dedup is a rule, not a step
that already ran.

**Bounds.** Every dispatch is one round, whatever caused the re-entry, capped at **three** — the
same three-strikes bound `operating-rules.md` sets everywhere else. Leaving the third round with
findings still open writes `design.adversarial_review: issues-open`; those findings go to the gate
verbatim and a human decides. A fourth round would mean the extraction and the reviewer disagree
persistently, which is a question for a person and not for another loop.

A finding that raises `run.design_depth` sets `run.depth_raised_in_02` and **re-runs the impact
sweep at the new breadth**, by loading `impact-analysis.md` — a shared leaf, loadable by whichever
stage needs it, exactly as this stage conditionally loads `manual-conversion.md`. An earlier draft
refused that re-run citing "a stage never reads another stage's reference file"; that rule governs
*pipeline* files reading each other, and the sweep does not live in one. The escape hatch that draft
offered instead — asking the human to request a resume — named no reachable `run.resume_from` value,
and nothing ever cleared the staleness flag it set.

Findings and their dispositions are written to `test-design.md` §9, **including rejected ones**.

### 2.8 Human gate

Present five sections, **one at a time**, per `gate-presentation.md` rule 4 — a section carrying a
decision stands alone, and reporting sections may be grouped:

| # | Section | Content | Carries a decision |
|---|---|---|---|
| 1 | What was agreed, and what was written | The approach approved earlier beside the surfaces actually delivered | no — unless they differ |
| 2 | Description | The §0b blocks, for approval. Human-facing prose intended for a Jira field — the only artifact of this run a person may copy somewhere the pipeline cannot check | **yes** |
| 3 | Coverage and priority | The coverage matrix, the dedup labels rendered in plain words, the priority proposed per scenario, the element intent map, Open Questions | **yes** — priority |
| 4 | Review | `approved`, `issues-fixed` with each finding and its disposition, or `issues-open` with the open findings verbatim | no |
| 5 | Impact | Every designed impact scenario with its candidate's evidence path and provenance; `impact.declared[]` alongside `impact.candidates[]`; the existing tests found per candidate | **yes** |

**Section 1 replaces what was once a Depth section, and keeps the half that was load-bearing.** That
section carried two things: `run.design_depth`, which is no longer presented anywhere, and the
approved approach beside what was delivered — **the only place a drift between the approach agreed
before any Gherkin existed and the scenarios that came out of 2.3–2.4b becomes visible.** Deleting
the section wholesale would have removed a check while appearing to remove a label. Without it, the
earlier approval could be honoured in name and abandoned in fact, with nothing noticing.

`design.review_mode` is recorded on the run and is not presented: it names which context the review
ran in, which is a fact about this skill's machinery and not one a reader can act on
(`gate-presentation.md` rule 6).

**Section 3 proposes priority; a human settles it.** The values 2.3 derived are shown per scenario,
with one question asking which need changing. Unlike the impact section below, silence here is not a
stop — the proposed values stand, because a derived priority is a defensible default while an
unanswered impact question is not (see below).

Take approval or revisions — a revision returns to whichever of 2.1–2.7b it affects and re-runs
self-review before returning here. On approval, commit the design artifacts.

The impact section requires one of three answers, and **without one of them the run does not
continue** (`operating-rules.md`, Turn-Ending Condition 12). This is the one place in the pipeline
where a human's absence of knowledge and a human's assertion of no impact must not look alike: a
sweep returning nothing is not evidence, and only a person can say which of the two it was.

| Answer | Effect |
|---|---|
| Keep a subset | The rest are dropped; see below |
| Keep a subset **and name a flow nobody found** | A revision that **returns to 2.4b**, re-runs 2.7 and 2.7b, and comes back here |
| No feature is impacted | Writes `impact.acknowledged_empty: true`, drops all, deletes the impact file |

The middle row is why *nothing authors Gherkin after this gate* survives literally: an addition is
not written at 2.8. It re-enters the step that authors impact scenarios and passes every check the
first batch passed. A human naming a flow the sweep missed is this design working; letting them
hand-write a scenario past 2.7 and 2.7b would be the same hole in a new place.

Impact scenarios are presented **unapproved by default**. A pre-checked list converts the human's
job from deciding to noticing, and a reviewer who is only noticing approves everything.

Dropped scenarios are removed from the `.feature` file before commit and kept, with their reasons,
in `impact-candidates.md` and `impact.dropped_scenarios[]` — which is what satisfies 2.7 on the
re-run, and what keeps the next run from re-litigating a decision a human already made. **When every
impact scenario is dropped the file is deleted, not left empty**, for the reason 2.4b declines to
write one: an empty feature file is materialized by Stage 03 and imported by CI as a file containing
no tests.

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
required in full, self-review still runs every check, and both gates still gate.

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
| An existing test's key matches nothing in the new design | `REVIEW <TEST-key>` — reported at the 2.8 design gate, never deleted or modified by the pipeline |

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
- `design.scenarios[]` — one entry per scenario, each carrying `name`, `surface`, `dedup`, `origin`,
  and `status: pending` (Stage 03 is what moves a scenario off `pending`); impact scenarios also
  carry `impact: true` and `impact_flow`
- `design.approach_chosen`, `design.approach_rationale`, `design.approach_alternatives[]`, and
  `design.approach_questions[]`, all from 2.2b — written before 2.3 authors anything
  (`run-state.md` rule 18); `design.approach_revised_in_02` when 2.7b routed a finding back there
- `xray.dedup` — `ran | not-run`, from step 2.2
- `design.adversarial_review`, `design.review_mode`, and `design.review_rounds`, from 2.7b
- `impact.approved_scenarios[]`, `impact.dropped_scenarios[]`, and `impact.acknowledged_empty`, all
  written by the human at 2.8
- `run.depth_raised_in_02`, when a review finding raised the depth

Not `sweep_breadth_stale`, and not `design.review_reason`. Both appeared in earlier drafts of this
design and were removed — the first because this stage can load the sweep's leaf and re-run it, the
second because the condition that would have written `not-run` no longer exists. A field nothing
writes is one a reader assumes means something.

And, on disk inside `run.artifact_dir`: the `.feature` file(s) from 2.5, `test-design.md` from 2.6
including its §0, §0b, §2b and §9, and `impact-candidates.md` updated with each candidate's
decision. No `.feature` file carries a description block — see 2.6.

## Enter Stage 03

Once the 2.8 design gate is passed and the design artifacts are committed, enter Stage 03 in the same
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
| "2.7 passed, so the design is checked — 2.7b is a formality" | 2.7 takes its list of criteria from the pass it checks, so it is satisfiable while the ticket is uncovered. That is the entire reason 2.7b exists, and it is the check most likely to be skipped precisely because 2.7 reported clean |
| "This host can't dispatch a subagent, so the review can't run" | It runs inline, with the same prompt and the same tasks, recorded as `review_mode: inline`. What makes it work is the question it asks, not the context it holds |
| "The sweep found nothing, so the impact section can be skipped at the gate" | An empty sweep is not evidence of no impact — the knowledge lives in a human's head. The section asks its question on every run, and `acknowledged_empty: true` is a person's answer, not a default |
| "The human dropped every impact scenario, so the empty file is harmless" | Delete it. Stage 03 materializes it and CI imports it as a file containing no tests |
| "One element is unnamed, but the rest of the map is done — good enough to pass 2.7" | Self-review checks every element of every `ui` scenario. One missing row fails the gate. Name it, or reclassify the scenario's `surface` with a reason — marking the scenario blocked is not an exit here, since this stage leaves every scenario `pending` and `blocked` is a Stage 03 verdict |
| "Depth is `trivial`, so I'll pick the approach and mention it at 2.8" | 2.8 is after the Gherkin is written. Disagreement there costs a redesign and a re-review — which is the cost 2.2b exists to remove |
| "There's only one sensible approach here" | Then say so, **and say why the others were rejected**. An approach presented with no alternative is a decision presented as a fact |
| "I'll batch the questions into one message to save a round trip" | One at a time. A batch of questions gets a batch of half-answers, and the half-answer to the question that mattered is indistinguishable from the rest |
| "The index says this manual test is unrelated, so leave it out of dedup" | The index orders attention, never input. Every exported test is matched, whatever its objective line says (`run-state.md` rule 19) |
| "The description reads better in the `.feature` file, next to the scenarios" | A line reading `Scenario:` is a keyword there. It parses as an empty scenario and `bddgen` compiles it. The block stays in `test-design.md` §0b |
| "This failed self-review before, I'll just approve it at 2.8 and fix it in Stage 03" | Stage 03's fix loop cannot edit `.feature` files at all (`operating-rules.md`). A design defect that reaches 2.8 unfixed stays a defect through automation |
