# speckit-qa-auto — The Test Approach Gate (Step 2.2b)

Date: 2026-08-21
Status: approved (design), not yet implemented
Extends [`2026-08-19-speckit-qa-auto-design.md`](2026-08-19-speckit-qa-auto-design.md) and
[`2026-08-20-speckit-qa-auto-impact-analysis-design.md`](2026-08-20-speckit-qa-auto-impact-analysis-design.md);
decision numbering continues from that document's D46.

**Scope.** `speckit-qa-auto/` version `0.4.0 → 0.5.0`.

| Kind | Files |
|---|---|
| New | none |
| Edited | `references/pipeline/stage-02-test-design.md`; `references/shared/run-state.md`, `references/shared/operating-rules.md`; `assets/adversarial-review-prompt.md`; `SKILL.md`; the skill's own `README.md` |
| Edited outside the skill | root `README.md` — the skills-table row's version badge, which `tools/validate_skills.py:292` compares against `SKILL.md`; `test-case/speckit-qa-auto/test-cases.md` — new rows AC37–AC49 |

No new stage, no new reference leaf, no renumbering of any existing step. The change is one
inserted step and the fields it writes.

## Problem

The pipeline goes from discovery to authored Gherkin without asking a human anything about *how*
the story should be tested. Stage 01 has no human gate by design. Stage 02 runs 2.1 (requirement
analysis) → 2.2 (dedup) → 2.3 (scenario design) → … → 2.8, and 2.8 is the first place a person is
consulted. By then every scenario is written, self-reviewed at 2.7, and adversarially reviewed at
2.7b.

That ordering makes one class of disagreement expensive out of all proportion to its content. A
human who would have said *"don't drive this through the UI, the invariant is an API-level one"*
cannot say it until the UI scenarios exist, have an element intent map, have survived two review
passes, and have been committed to a design document. Their agreement at 2.8 is then partly an
artifact of sunk cost, which is precisely the reviewer-who-is-only-noticing failure the impact
section of that same gate was built to avoid.

### What already covers this, and what does not

The superpowers `brainstorming` skill formalizes the ceremony this pipeline is missing. Most of its
checklist is already present here, and in three places this pipeline is stronger. Stating the
overlap is what keeps this design additive rather than duplicative.

| `brainstorming` step | speckit-qa-auto today | |
|---|---|---|
| Explore project context | Stage 01: repo profile, three discovery sweeps, Xray export, impact sweep | covered, and wider |
| Classify, and announce it so it can be overridden | `run.design_depth` — `trivial` / `standard` / `cross-cutting` — resolved at 01.7 **with its reason**, presented at 2.8 | classification present; **announcement is late** |
| Ask clarifying questions, one at a time | 2.1 asks a *blocking* ticket ambiguity, **once**; 01.1 asks one round for unresolved profile fields | present but narrow and one-shot |
| Propose 2-3 approaches with trade-offs and a recommendation | nothing — 2.1 produces behaviours and 2.3 turns them into scenarios | **absent** |
| Present design, get approval | 2.8: four sections, a mandatory impact answer, impact scenarios unchecked by default | covered, and stronger |
| Spec self-review | 2.7, mechanical | covered |
| Fresh-eyes review | 2.7b adversarial review — `brainstorming` has no equivalent | exceeds |
| Write the design doc, commit it | `test-design.md`, committed at 2.8 | covered |
| Hard gate before implementation | 2.8 → Stage 03 | covered |
| Ratchet: hidden complexity upgrades the path mid-task | a 2.7b finding raises `design_depth`, sets `run.depth_raised_in_02`, re-runs the sweep | covered |

Three gaps, and they are one gap wearing three faces: **there is no point in the run where a human
is asked about the shape of the testing while changing the answer is still cheap.**

- **A — no approach exploration.** Nothing proposes alternatives, so nothing is chosen; a single
  approach is arrived at implicitly and presented as a fact.
- **B — the classification is announced too late to be cheap to override.** `design_depth` is
  resolved at 01.7 and shown at 2.8. Disagreeing at 2.8 costs a full redesign plus a re-review.
- **C — clarifying questions are the wrong kind.** 2.1 asks what a *line means*. Nothing asks what
  the team wants out of the testing — purpose, constraints, what "done" looks like.

### `design_depth` already is the three paths

`trivial` / `standard` / `cross-cutting` map onto spike / bounded / architectural closely enough
that a fourth classification field would be a second name for one axis. Two classifiers over the
same run diverge the first time a reviewer raises one and not the other, and every reader
afterwards has to know which one governs. This design adds no classifier. It scales the new gate's
ceremony along the axis that already exists, and it moves the announcement of that axis to a point
where disagreement is cheap.

## Design Decisions

**D47 — The change is one new step, `2.2b`, inside Stage 02.** Not a new stage, not a new reference
leaf, not a new run-level classifier. `stage-02-test-design.md` already states that its numbering
"marks position, not a count" and already carries 2.4b and 2.7b; a third inserted step uses the
convention the file wrote for itself. A new stage would renumber the router, the resume values, and
every cross-reference to Stage 03 and Stage 04 — a cost paid for nothing, since the work belongs
between two steps of one stage.

**D48 — 2.2b sits after 2.2, not before it.** One of the approaches a run should be able to choose
is *lean on the coverage that already exists*, and that approach cannot be stated without the dedup
labels 2.2 produces. Placed before 2.2, the gate would ask a human to choose between options one of
which it could not describe.

**D49 — Ceremony scales with `design_depth`; approval does not.** The number of alternatives
presented and the number of questions asked scale. Whether an answer is taken never scales. This is
the same boundary `run-state.md` rule 12 already draws for depth, restated for the new step, and it
is the boundary most at risk here: a gate that "scales to nothing" on `trivial` is a gate that was
removed.

| `design_depth` | Questions | Approaches presented | Approval |
|---|---|---|---|
| `trivial` | only one that genuinely blocks | 1, in 2-3 sentences, **with the obvious alternative named and rejected in writing** | a nod suffices |
| `standard` | one at a time | 2, with trade-offs and a recommendation | an explicit yes |
| `cross-cutting` | one at a time | 3, with trade-offs and a recommendation | an explicit yes |

**D50 — One gate per run, never one per epic child.** An `epic` anchor presents per-child depth
inside a single presentation. This is 2.4b's ceiling rule applied to a second step: the bound is
what one human reads at one sitting, and N gates for N children moves the bottleneck rather than
removing it. An epic too wide for one presentation is split, and the split is stated — the same
words `manual-conversion.md` uses for a conversion batch.

**D51 — A `test` anchor gets no approach menu.** For a conversion the approach is fixed by the
anchor: translate faithfully. Offering alternatives there would invite a reviewer to redesign an
approved test that has been executing for years, which `manual-conversion.md` exists to prevent.
The third section of the gate becomes **batch scope** instead — which manual tests this run
converts and where the batch is cut. Depth is still announced and questions are still asked.

**D52 — 2.2b's questions are a different kind from 2.1's, and the boundary is written down.** 2.1
asks *"what does this line mean?"* and must stay at 2.1, because 2.2's dedup depends on the
behaviour list being right. 2.2b asks *"how should this be tested, and what matters to you?"* —
purpose, constraints, success criteria. Without the boundary stated, the two collapse: either 2.1
grows into a design conversation before dedup has run, or 2.2b re-asks what 2.1 already settled.

**D53 — Rejected alternatives are kept.** In run state and in `test-design.md` §0. This is the
reason §9 keeps rejected review findings, applied to a second decision: a choice recorded without
the options it beat leaves the next reader unable to distinguish a design that was never considered
from one that was considered and held. It is also what makes D56 enforceable.

**D54 — The reviewer at 2.7b gets §0 as context and no fourth task.** A task of the form *"was this
approach wrong?"* would reopen a decision a human has already approved, and would do it in the one
step of the pipeline that is deliberately unanchored. Instead the reviewer's existing tasks 1 and 2
may now name the approach as a *cause*: "this invariant is uncovered because the approach put this
surface at the API level." A finding that can only be fixed by changing the approach **routes back
to 2.2b**, re-runs 2.7, and re-reviews — counted against the same three-round cap
`operating-rules.md` sets everywhere else. That is the one-way ratchet, and it parallels the
existing `depth_raised_in_02` mechanism exactly.

**D55 — Stopping at 2.2b is turn-ending, not run-ending.** No new `run.resume_from` value. The gate
behaves the way Turn-Ending Condition 12 already behaves: the turn ends without an answer, and the
human's answer continues the same run. Introducing `resume_from: 02.2b` would create a resume path
with no stale state to re-resolve, since nothing has been produced yet.

**D56 — Even at `trivial`, one alternative is named and rejected in writing.** A single approach
offered with no alternatives is a decision presented as a fact, and `trivial` is where that is most
tempting. The cost is one sentence.

**D57 — 2.8 shows the approved approach beside what was delivered.** The Depth section of the 2.8
gate carries `design.approach_chosen` alongside `run.design_depth`. This is not ceremony: it is the
only place a *drift* between the approach a human approved at 2.2b and the scenarios that actually
came out of 2.3–2.4b becomes visible. Without it, 2.2b's approval could be honoured in name and
abandoned in fact, with no check anywhere that noticed.

## 1. Step 2.2b — Test Approach Gate

Inserted between 2.2 and 2.3.

### 1.1 What the gate presents

Three sections, then a stop.

| Section | Content |
|---|---|
| Depth | `run.design_depth` with the reason Stage 01 recorded — presented **here** so it can be disagreed with before any Gherkin exists |
| Questions | Asked one at a time; only questions whose answer changes the design |
| Approach | 2-3 alternatives (per D49) with trade-offs, the recommendation first |

A human raising the depth here re-runs the impact sweep at the new breadth by the mechanism 2.7b
already uses — `impact-analysis.md` is a shared leaf, loadable by the stage that needs it — and
sets `run.depth_raised_in_02`. Lowering the depth is refused: the ratchet is one-way, and the run
records the disagreement as an approach question with its answer rather than acting on it.

### 1.2 What an approach is

An approach is a coherent position on five axes, not a slogan. The axes:

- **Surface mix** — which behaviours are `ui`, which are `api`, which stay `manual`
- **Granularity** — one scenario per criterion, versus `Scenario Outline` with an examples table
- **Negative and boundary depth** — how far past the happy path this run goes
- **What is left to existing coverage** — which `SKIP`-labelled behaviours are genuinely covered
- **Test data strategy** — fixtures, mocks, or live seeding

Shapes these combine into, as illustration and not as a fixed menu:

| | Approach | Trade-off |
|---|---|---|
| A | UI-heavy — every criterion a UI scenario, real data | Highest fidelity; slowest; most exposed to flake |
| B | API-first plus a UI smoke — invariants at the API layer, one or two UI happy paths | Fast and stable; blind to rendering defects |
| C | Thin — automate only `NEW` behaviours, leave `SKIP` rows to their existing Xray tests | Cheapest; depends entirely on dedup having run |

**When `xray.dedup` is `not-run`, approach C cannot be stated**, and the gate says so with the
reason Stage 01 recorded for the unavailability. The gate still runs; it presents one option fewer.
An unrun dedup and a dedup that ran and found nothing are different facts everywhere else in this
pipeline, and they are different facts here.

### 1.3 The question boundary

Per D52, and stated in the stage file so it is never guessed:

| Asked at | Kind | Recorded in |
|---|---|---|
| 2.1 | What does this line of the ticket mean? | Open Questions in `test-design.md` (non-blocking), or asked once (blocking) |
| 2.2b | How should this be tested? What matters to you? What does done look like? | `design.approach_questions[]` and `test-design.md` §0 |

The two lists do not overlap. A question that appears in both was asked in the wrong place.

### 1.4 Anchor resolution

| `run.anchor_type` | Depth section | Questions | Third section |
|---|---|---|---|
| `story` | the run's depth and reason | per D49 | approaches per D49 |
| `epic` | per-child depth, in one presentation (D50) | per D49, over the epic | approaches per D49, stated once for the epic |
| `test` | the run's depth and reason | per D49 | **batch scope** — which manual tests convert, where the batch is cut (D51) |

## 2. Run-State Contract Additions

Under `design:`:

```yaml
design:
  approach_chosen: <string>            # for a `test` anchor: faithful-conversion
  approach_rationale: <string>
  approach_alternatives:               # never empty once the gate has run (D56)
    - name: <string>
      rejected_because: <string>
  approach_questions:
    - question: <string>
      answer: <string>
  approach_revised_in_02: true | false  # set when a 2.7b finding routed back to 2.2b (D54)
```

**New rule 18** in `run-state.md`:

> `design.approach_chosen` is present before step 2.3 writes its first scenario, and
> `design.approach_alternatives[]` is never empty once 2.2b has run. A scenario authored before the
> field exists is a scenario nobody approved the shape of; an empty alternatives list is a decision
> recorded as a fact. Neither is repaired by a later gate — 2.8 approves scenarios against an
> approach, and it cannot approve them against one that was never written down.

No existing field changes meaning. Nothing downstream of Stage 02 reads any of these — they are
design-time fields, read by 2.3, carried to 2.7b as context inside `test-design.md` §0, and
displayed at 2.8 per D57.

## 3. `test-design.md` §0 — Test Approach

A new first section, placed ahead of the existing §1, because it is the frame every later section
sits inside:

- The approach chosen, and why
- Every alternative considered, and why each was rejected (D53)
- The clarifying questions asked at 2.2b with their answers
- The depth at the time of approval, and whether the human changed it

§0 travels to the 2.7b reviewer automatically: the reviewer's input list already names
`test-design.md`, so no new input is added to the prompt.

## 4. Stage 02 Changes Outside 2.2b

**2.3** reads `design.approach_chosen` and designs to it. A scenario whose surface contradicts the
approved approach is either brought in line or accompanied by the reason it departs — recorded, not
silent, because D57's drift check at 2.8 reads exactly this.

**2.6** writes §0.

**2.7** gains one check: `design.approach_chosen` is present and `design.approach_alternatives[]`
is non-empty. It is mechanical, like every other check in that list, and it fails the way they do —
fixed at its source, three consecutive failures stopping the run.

**2.7b** routes an approach-caused finding back to 2.2b, within the existing three-round cap, and
sets `design.approach_revised_in_02` (D54). The existing routes — tasks 1 and 3 to 2.1, task 2 to
2.4b — are unchanged.

**2.8** Depth section carries `design.approach_chosen` beside `run.design_depth` (D57). The gate's
four sections stay four; one of them gains a line.

**Red Flags** — three rows appended to the table the stage file already carries:

| Thought | Reality |
|---|---|
| "Depth is `trivial`, so I'll pick the approach and mention it at 2.8" | 2.8 is after the Gherkin is written. Disagreement there costs a redesign and a re-review — which is the cost 2.2b exists to remove |
| "There's only one sensible approach here" | Then say so, **and say why the others were rejected**. An approach presented with no alternative is a decision presented as a fact (D56) |
| "I'll batch the questions into one message to save a round trip" | One at a time. A batch of questions gets a batch of half-answers, and the half-answer to the question that mattered is indistinguishable from the rest |

## 5. `operating-rules.md` Changes

**New Turn-Ending Condition 14:**

> The Stage 02 test-approach gate (2.2b) with no answer given. As with condition 12, the run cannot
> tell a human who has not decided from a human who agrees with the recommendation, and at this gate
> that difference decides the shape of every scenario the run goes on to write.

**Condition 3 is reworded** to name step 2.8 explicitly. It currently reads "The Stage 02 human
gate"; Stage 02 now has two, and an unqualified reference to "the" gate is ambiguous the moment the
second one exists.

## 6. `assets/adversarial-review-prompt.md` Change

One clause added under **Calibration**:

> `test-design.md` §0 records a test approach a human approved before the scenarios were written.
> Treat it as context, not as a target. Do not flag "a different approach would have been better" —
> that decision has an owner. Do flag the *consequence*: a constraint or an invariant left uncovered,
> naming the approach as the cause if that is what it is.

The three tasks are unchanged, and the `test`-anchor fidelity set is unchanged. Adding a fourth task
is refused for the reason D54 gives.

## 7. SKILL.md and README Changes

`SKILL.md`:

- **Stage Router table** — Stage 02's "Human gate" cell becomes `yes — 2.2b approach, 2.8 design`.
  A bare `yes` was unambiguous while the stage had one gate and is not now.
- **Modes section** — "Both human gates — Stage 02 design approval and Stage 04 commit-and-push
  approval" becomes three, naming 2.2b first. The section's claim is that no flag skips a gate; a
  gate the section does not list is one the claim does not cover.
- **`description` front matter** — one clause added, that the pipeline agrees the test approach with
  a human before authoring any Gherkin. The description is what a host matches an invocation
  against, and this is now user-visible behaviour, not an internal step.
- **`version`** — `0.4.0` → `0.5.0`.

The skill's own `README.md` mirrors the gate count and the version. The **root `README.md`** row for
`speckit-qa-auto` takes the version badge `v0.5.0` — `tools/validate_skills.py:292` compares that
badge against `SKILL.md`'s front matter, so a bump in one place and not the other fails the
validator. The row's flags column is unchanged: this design adds no flag.

## 8. Acceptance Criteria

Deterministic, CI- or read-checkable, continuing `test-case/speckit-qa-auto/test-cases.md` from
AC36.

### 8.1 Deterministic

| ID | Item | Check | Expected |
|---|---|---|---|
| AC37 | The gate precedes authored Gherkin | At the 2.2b stop, read run state and `run.artifact_dir` | `design.approach_chosen` is present; no `.feature` file exists in the artifact folder |
| AC38 | No fourth classifier | `grep -nE 'engagement\|approach_path\|spike\|bounded\|architectural' speckit-qa-auto/references/shared/run-state.md` | No classifier field beyond `run.design_depth`; the three-path vocabulary appears nowhere as a field |
| AC39 | Ceremony scales, approval does not | A run classified `design_depth: trivial`, taken through 2.2b | `approach_alternatives[]` holds at least one rejected entry; an answer was taken; every 2.7 check still runs |
| AC40 | One gate per epic | An `epic` anchor with two children | Exactly one 2.2b presentation; per-child depth inside it; one artifact folder |
| AC41 | `test` anchor takes no approach menu | A `test`-anchor conversion run at 2.2b | No alternatives menu is presented; the third section confirms batch scope; `approach_chosen: faithful-conversion` |
| AC42 | Rejected alternatives survive | A run approved at 2.2b, read after 2.8 | Each rejected alternative appears in `design.approach_alternatives[]` and in `test-design.md` §0 with its `rejected_because` |
| AC43 | Unrun dedup removes an option, not the gate | A run where Stage 01 could not reach Xray | The gate runs; the coverage-leaning approach is absent; the reason Stage 01 recorded is stated |
| AC44 | 2.2b is turn-ending 14, not a resume point | `speckit-qa-auto/` complete | `operating-rules.md` lists condition 14 naming 2.2b; `grep -rn '02\.2b' speckit-qa-auto/references/shared/run-state.md` finds no `resume_from` value |
| AC45 | An approach-caused finding routes to 2.2b | A 2.7b finding fixable only by changing the approach | The run re-enters 2.2b, re-runs 2.7, re-reviews; `design.approach_revised_in_02: true`; `design.review_rounds` never exceeds 3 |
| AC46 | The reviewer keeps three tasks | Read `assets/adversarial-review-prompt.md` as dispatched | The `story` set has three tasks, not four; the Calibration section carries the do-not-re-litigate clause |
| AC47 | Drift is visible at 2.8 | A run whose 2.3 output departs from the approved approach | The 2.8 Depth section shows `approach_chosen` beside the delivered surfaces, and the departure is stated |
| AC48 | Version agrees in three places | `python3 tools/validate_skills.py`; `python3 tools/validate_coupling.py speckit-qa-auto` | Exit `0`, `0` errors; `SKILL.md`, the skill README, and the root README row all read `0.5.0` |
| AC49 | The question boundary holds | A run with one ticket ambiguity and one how-to-test question | The first appears in `test-design.md` Open Questions or was asked at 2.1; the second appears in `design.approach_questions[]`; neither appears in both lists |

### 8.2 Not a CI gate

Whether 2.2b changes outcomes is an empirical question this design does not settle by argument. It
is answered by recording, across real runs, how often the human picks something other than the
recommendation. A gate whose recommendation is accepted every time on every ticket is either a very
good recommender or a rubber stamp, and the two are told apart by the rate, not by the design. That
rate is recorded and reported; it obliges nothing on its own, and it is the input to whether the
alternatives being generated are real alternatives.

## 9. What This Does Not Do

- It does not add a fourth classification axis. `run.design_depth` is the only classifier (D47).
- It does not let a human author Gherkin at a gate. 2.2b decides the shape; 2.3 and 2.4b author,
  and everything they author passes 2.7 and 2.7b. This is the same property 2.8 already preserves.
- It does not touch Stage 01, Stage 03, or Stage 04. Stage 01 keeps its "no human gate" property;
  Stage 03 remains a no-stop zone.
- It does not skip anything. `--design-only`, `code_state: pending`, and every `design_depth` value
  run 2.2b. No flag skips a gate, and this design adds no flag.
- It does not report the approach in Stage 04's summary. Nothing downstream reads the field, and
  adding a consumer that only displays is a coupling paid for nothing.

## 10. Out Of Scope (v2 Candidates)

- **A library of named approaches.** The five axes in §1.2 are stated so a run can reason to a
  coherent position, not so it can pick from a catalogue. A catalogue is worth building once real
  runs show the same three or four positions recurring — and worth nothing before that.
- **Per-behaviour approach overrides.** One approach per run today. A story wanting the API layer
  for one behaviour and the UI for another says so in the rationale; whether that deserves its own
  field is a question for evidence.
- **Carrying an approved approach across resumed runs.** A `02.4` resume re-enters after the code
  lands, and the approach it was approved against may no longer fit what was built. Re-asking is the
  safe default; caching it is an optimization with a correctness cost, and it needs its own design.
