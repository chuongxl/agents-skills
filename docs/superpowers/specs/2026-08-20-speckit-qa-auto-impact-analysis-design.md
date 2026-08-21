# speckit-qa-auto — Adversarial Design Review and Impact Analysis

Date: 2026-08-20 (round 2 and round 3: 2026-08-21, after two adversarial reviews)
Status: approved (design), not yet implemented
Extends [`2026-08-19-speckit-qa-auto-design.md`](2026-08-19-speckit-qa-auto-design.md); decision
numbering continues from that document's D22.

**Scope.** `speckit-qa-auto/` version `0.2.0 → 0.3.0`.

| Kind | Files |
|---|---|
| New | `references/shared/impact-analysis.md`; `assets/adversarial-review-prompt.md` |
| Edited | `references/shared/discovery.md`, `run-state.md`, `host-adaptation.md`, `gherkin-conventions.md`, `operating-rules.md`, `selector-verification.md`, `manual-conversion.md`; `references/pipeline/stage-01-intake.md`, `stage-02-test-design.md`, `stage-03-automate.md`, `stage-04-finish.md`; `SKILL.md`; the skill's own `README.md` |
| Edited outside the skill | root `README.md` — the skills-table row's version badge, which `tools/validate_skills.py:292` compares against `SKILL.md`, **and that row's flags column, which `--impact` changes**; `tools/validate_coupling.py` — new check C3 (see §8); `test-case/speckit-qa-auto/` — new rows and one fixture |

Two files share a name and are not the same file: the **leaf** `references/shared/impact-analysis.md`
(how the sweep works) and the **artifact** `impact-candidates.md` (what one run found). The artifact
was renamed in round 2 for exactly this reason.

## Problem

A story tells you what the feature does. It rarely tells you what the feature *breaks*. A real run
against MOM-12194 dropped two classes of required coverage, and reported full coverage while doing
it.

### Class A — a constraint stated in the ticket, outside the AC table

`ticket.md` carries this line under **Out-Scope**:

> Do not allow user/system modify any candidate has attached to APM's invoice.

It is a testable constraint. No scenario covers it, because `stage-02-test-design.md` §2.1 reads
only the acceptance criteria, and the design document it produced records that boundary as a fact
about itself: *"Eight testable behaviours derived from `ticket.md`'s Scenarios table"*.

The coverage matrix then reported **"No criterion is uncovered."** True against its own definition
of *criterion*, false against the ticket. **A gap that reports itself as full coverage is worse
than a gap that reports nothing** — it spends the reviewer's attention and returns a false negative.

### Class B — an invariant imposed on a feature the ticket never names

Changing a work order setting refreshes its candidates, removing and regenerating them. Once a
candidate is attached to an APM invoice it must survive that refresh. The invoice story creates
this invariant; the Change Setting story predates it and says nothing.

`discovery.md` runs three sweeps and all three exist to **deduplicate**, not to find impact. A
`grep` for `regress|impact|blast|affected` across the skill returns five hits, none of them logic.

### Why "more input" is not the fix

The obvious response is to fetch more: another sweep, wider parsing, stricter rules. **Class A
refutes it.** That sentence was already in `ticket.md`, already fetched, already in the context of
the model that wrote `test-design.md`. Nothing was missing from the input.

What was missing was a **question whose scope the extraction did not set**. Step 2.7 self-review
asks *"is every acceptance criterion covered by at least one scenario"* — and takes its list of
criteria from the pass being checked. The check is satisfiable while the ticket is uncovered,
because the criteria the extraction never admitted were criteria are not in the list it iterates.

## Constraint 5: A Check Cannot Find What Its Own Question Excludes

This is the operative claim, and round 2 corrected it. The first draft attributed the fix to
*context isolation*; adversarial review showed that attribution does not hold, and the correction
matters because a wrong attribution buys the wrong mechanism.

**What actually differs is the question.** 2.7 asks *"is every criterion covered?"* — scoped by the
extraction's criterion list. 2.7b asks *"which sentences in the ticket state a rule the system must
uphold?"* — scoped by the ticket. The second question can return a sentence the first question's
list never contained. That property belongs to the question, and it survives whether the question
is asked in a subagent or in the main run.

**Isolation does not do the work it was credited with.** The reviewer is handed `test-design.md`,
which states the extraction's boundary in its own opening line and, under D34, its both-readings
resolutions. The argument is in the output, not only in the reasoning, so a "clean" context is not
clean in the way the first draft claimed.

Isolation is retained as a **preference**, not a precondition: a fresh context is less anchored on
a conclusion it did not reach, which is a real but unquantified benefit. It is recorded per run
(`design.review_mode`) precisely so the benefit can be measured against real runs rather than
asserted — the same standard §11 applies to the second-reviewer question.

Two things follow, and both were wrong in round 1:

- 2.7b **does** degrade to inline, like every other dispatch (D33 revised). A host without
  dispatch gets a review with its mode recorded, not zero review.
- The reviewer receiving reasoning is **not** a defect to design around. It is stated plainly in
  §5.4 rather than forbidden in a rule the design then violates.

## Design Decisions

Rows marked ⟲ were revised in round 2; ⟲⟲ marks a row revised again in round 3. Both rounds
followed an adversarial review, and this was the third and last the design's own bound allows.

| # | Decision | Rationale |
|---|---|---|
| D23 | Impact candidates come from **both** an automated sweep **and** an explicit human declaration, merged and never collapsed | User directive. Each covers the other's failure mode. Separate fields preserve the cross-confirmation signal that merging destroys |
| D24 | Impact scenarios live in a **separate `.feature` file inside the same artifact folder**, under the same `@REQ_` tag at Feature level | User directive. They exercise a different domain — different page objects, selectors, Stage 03 scope — while the artifact folder name remains the single identity |
| D25 | The Stage 02 gate **always** presents the impact section and **always** requires an explicit answer, including when the sweep found nothing | User directive. Class B knowledge lives only in a human's head; an empty sweep is not evidence of no impact |
| D26 | Sweep 4 runs **entity mutation traceability** and **test inventory**; domain-vocabulary search is rejected | They answer different questions. Vocabulary search on a mature project returns most of the system — "noise priced as signal" |
| D27 | Sweep 4 returns **flows with evidence paths**, never the word *affected* | Rule 5 applied to the new sweep |
| D28 ⟲ | Step 2.1 reads the **whole ticket** at every depth. No rule is keyed to the heading named "Out-Scope", and depth never narrows the read | A rule keyed to that heading patches one ticket layout. Round 2: depth must not narrow the read either — narrowing the read *is* the Class A behaviour, and the pass that would authorize it is the pass being audited |
| D29 ⟲⟲ | `design.scenarios[].selector_evidence` is added per scenario. The top-level field becomes a **reporting roll-up with an explicit precedence** — `deferred` > `fallback` > `live-dom` > `source` — computed over `surface: ui` scenarios only; `api` and `manual` scenarios take `n/a` and are excluded |  Round 2 corrected the rationale. The case first given — `deferred` beside `source` — **cannot occur**: `source` is written only by the Stage 03 entry gate, that gate never runs at `code_state: pending`, and `deferred` is written only at `pending`. The real case is a landed run where one element resolves from `source` and another needs `live-dom` or `fallback`; that distinction is per element, is what rule 7 exists to protect, and is collapsed today. Round 3: "weakest" was undefined over an enum rule 7 calls non-comparable, and a landed run of only `api` scenarios would have rolled up to `deferred` — which turn-ending condition 11 stops on. The precedence is declared as a reporting convention; the per-scenario field stays the authority, which is what keeps rule 7 intact |
| D30 | Impact scenarios inherit `run.code_state` from the anchor feature | The invariant does not exist until the anchor's code lands. Follows from rule 6 unchanged |
| D31 ⟲ | Step 2.7b: a review pass with **three fixed attack tasks** and brainstorming's approve-unless-serious calibration. Isolation is preferred, not required | Round 2: rationale moved from isolation to the questions asked (Constraint 5). The calibration clause is carried over deliberately — an uncalibrated reviewer floods the gate, the human learns to skim, and the mechanism inverts into what it was built to prevent |
| D32 ⟲ | `run.design_depth` is resolved **in Stage 01**, from `ticket.md`, before Sweep 4. It scales **only** Sweep 4's entity breadth and `test-design.md` verbosity. It never scales the read and never disables a gate or 2.7b. Ratchets up only | Round 2 fixed two defects: it was resolved in Stage 02 while scaling a Stage 01 sweep, and at `trivial` it narrowed the read to the AC table — reproducing Class A under a new name |
| D33 ⟲⟲ | **2.7b degrades to inline like every other dispatch.** `design.review_mode` records which ran, and `adversarial_review` has **three** values, not four | Round 2 replaced the round-1 carve-out. Its argument rested on the isolation attribution Constraint 5 retracts, and an unfalsifiable exception sentence would let any future step hollow out the general rule. Zero review on a supported host is a worse outcome than a weaker review that says it is weaker. Round 3: `not-run` was left in the enum after this decision deleted the only condition that could produce it — a value nothing writes is one a reader assumes means something |
| D34 | Step 2.7 gains an **ambiguity check**: any ticket line admitting two readings is resolved to one, explicitly, with both readings named | Brainstorming's spec self-review has this check; 2.7's six did not. `Out-Scope` admitting both *not-built* and *must-not-happen* is exactly a two-reading line |
| **D35** ⟲ | **Impact scenarios are designed at 2.4b — before 2.7, 2.7b, and the gate — over every sweep candidate and declared flow. The human approves or drops individual scenarios at 2.8** | Round 2. In round 1 they were authored at 2.9, after the gate: never checked by 2.7, never seen by 2.7b, never approved, yet automated by Stage 03. It also made attack task 2 — the entire Class B fix — terminate in a finding nothing could consume, and specified 2.7b to receive a file that did not exist yet. Deciding on concrete scenarios is also a better gate question than deciding on abstract flow names. Round 3 closed the drop lifecycle: a candidate is satisfied by a scenario **or by a recorded drop**, additions at the gate re-enter 2.4b rather than authoring at 2.8, and 2.4b is bounded by the gate the way a conversion batch is |
| **D36** | **Sweep 4 runs after sweeps 1–3, not concurrently with them** | Round 2. Branch B consumes sweep 2's Xray list and sweep 3's repo-test list. `discovery.md`'s "share no inputs and no ordering" is amended to scope that claim to sweeps 1–3 |
| **D37** ⟲ | **`UPDATE` and `SKIP` are both forbidden in the impact file. A normalized-key match there labels `REVIEW-OVERLAP <TEST-key>`** | Round 2. Impact scenarios cover flows other stories own, so a match is likelier here than anywhere. `UPDATE` carries `@TEST_<TEST-KEY>` into a file tagged `@REQ_MOM-12194`; CI would update that test in place and move another story's test under this story's requirement. Round 3: reusing `REVIEW` was wrong — the dedup table defines it as *an existing test matches nothing in the new design*, the opposite direction, in the same field with no discriminator. `SKIP` is forbidden for the same ownership reason `UPDATE` is: an identical-steps match means another story's test may already assert this invariant, and deciding that automatically is exactly the move D37 exists to prevent |
| **D38** ⟲ | **All three anchor types are defined** (§7), with a **per-child run-state shape** for `epic`, a batch bound, and a **bidirectional** fidelity task set that `epic`-anchored conversions also receive | Round 2. The design assumed `story` throughout while D25 and D32 said the gate and review run always. Round 3: naming the three anchors was not enough — the fields were flat scalars with no child dimension, the fan-out had no ceiling before a gate one human reads, and the fidelity task asked only what the Gherkin *omits*, while `manual-conversion.md` treats a silent *addition* as equally indistinguishable from mistranslation |
| **D39** ⟲ | **Stage 03 widens materialization, never the run command.** Branch B's existing tests become a Stage 04 regression recommendation | Round 2. A pre-existing test pulled into a widened run command has no run-state entry, no attempts budget, and no verdict path — inside a no-stop zone whose exit condition is a verdict per scenario. Round 3 defined the term the recommendation reads from: a flow is **approved** when at least one of its scenarios is in `approved_scenarios[]`, and a flow whose scenarios were all dropped still has its Branch B tests reported — a human dropped a scenario, not the observation that tests exist there |
| **D40** ⟲ | **Acceptance criteria are split into deterministic checks and eval cases**, and the eval cases name a fixture and require agreement across runs | Round 2. Four round-1 criteria asserted that a model pass would return a specific judgement. One passing run does not distinguish a mechanism from luck, and every existing row in `test-cases.md` is deterministic. Round 3 rebuilt E4: `review_mode` is an observation of host capability with no flag to force it, and E1 was constructed to succeed every time, so comparing two ceilings could not discriminate. E4 now runs over E3's harder fixture and is recorded observationally |
| **D41** | **C3 checks backticked citations, not markdown links** | Round 3. Every markdown link in a stage file already sits on its own `Loads:` line, so a link-based check is tautologically satisfied and measures nothing. Leaves are cited in prose as `` `commit.md` ``, and four such citations are undeclared today — `stage-03-automate.md` cites `repo-profile.md` and `commit.md`; `stage-04-finish.md` cites `gherkin-conventions.md` and `selector-verification.md`. Declaring them is part of this change: a check that passes on a codebase holding four live violations is evidence it is not looking |
| **D42** | **Dedup is a rule applied wherever a scenario is created, not a step that runs once at 2.2** | Round 3. 2.2 precedes 2.4b, so impact scenarios had no step to label them while 2.7 required every behaviour to carry a label — and scenarios added by a 2.7b loop reopened the same gap. The rule is already defined as mechanical and position-independent ("Dedup Is A Rule, Not A Judgement"); saying so explicitly costs nothing and removes the ordering trap |
| **D43** | **2.4b is bounded by the gate, not by the candidate count**, in the words `manual-conversion.md` already uses | Round 3. A `cross-cutting` sweep over several entities, times one scenario per candidate, times a per-child fan-out, arrives at a gate that is one human reading one output. The skill already owns this principle for conversion batches; a second ceiling would give one idea two spellings |
| **D44** | **The impact gate becomes turn-ending condition 12** in `operating-rules.md` | Round 3. That list declares itself *"Exhaustive. Any other reason to stop is invalid."* A run that stops for want of an impact answer is a stop, and a stop absent from an exhaustive list is one a later reader deletes as a bug |
| **D45** | **`@IMPACT` is skill-owned, not written into the profile's `existing_tags`** | Round 3. `existing_tags` is a *discovered repository convention* (D5); writing a skill-invented tag into it inverts the split between process, which this skill owns, and convention, which the repo owns. Whether the tag participates in `scoped_run_cmd`'s filter is stated too, because a tag nothing filters on is decoration |
| **D46** | **Stage 02 may re-run Sweep 4 by loading `impact-analysis.md` conditionally. `sweep_breadth_stale` is deleted** | Round 3. The field's justification — "a stage never reads another stage's reference file" — misapplied the rule: Sweep 4 lives in a *shared leaf*, which Stage 02 may load exactly as it conditionally loads `manual-conversion.md`. The escape hatch offered instead ("request a resume") named no reachable `resume_from` value, and nothing ever cleared the flag. Re-running the sweep is both possible and simpler than a field explaining why it is not |

## 1. Sweep 4 — Impact Candidates

Runs in Stage 01 **after** sweeps 1–3 (D36). Two branches, one merged result. Its output is
evidence for 2.7b's second attack task first, and a gate input second.

### 1.1 Branch A — entity mutation traceability

1. Resolve the anchor's primary entity from `ticket.md`. MOM-12194 resolves to
   `work_order_candidate`.
2. Find every write operation against that entity in the frontend source and, where reachable, the
   API schema. In the reference repo this is one file — `om-mom-frontend/src/graphql/work-order-candidate.graphql`
   in `om-mom-e2e-speckit-auto`, whose MOM-12194 artifacts live on branch
   `test/mom-12194-receive-invoice-info-from-apm` (commit `7fa828f`), not on `main`:

   | Operation | File |
   |---|---|
   | `UpdateWorkOrderCandidateAmendment` | `graphql/work-order-candidate.graphql:111` |
   | `RefreshWorkOrderCandidates` | `graphql/work-order-candidate.graphql:123` |
   | `ReassignWorkOrderCandidateVendor` | `graphql/work-order-candidate.graphql:211` |
   | `CancelWorkOrderCandidates` | `graphql/work-order-candidate.graphql:283` |

3. Map each operation to the flow that calls it and the screen that flow belongs to.

`RefreshWorkOrderCandidates` is the Change Setting flow — the Class B case, produced mechanically
from the ticket plus the schema.

### 1.2 Branch B — test inventory

Consumes sweep 2's Xray list and sweep 3's repo-test list; records those exercising the same entity
or screen. Returns `feature_path` and scenario names only. Its output is the Stage 04 regression
recommendation (D39), not a Stage 03 run scope.

Branch A finds what may break with no test guarding it; Branch B finds what tests a human should
re-run. A flow in both is a stronger candidate, and the merged record keeps both provenances.

### 1.3 Bounds

`discovery.md`'s anti-crawl bounds apply, adapted, with `run.design_depth` — already resolved
earlier in Stage 01 (D32) — scaling entity breadth only:

- **One hop.** Entity → writers of that entity → owning flow. Not onward to entities those flows
  also touch; two hops from `work_order_candidate` reaches most of the system.
- **Entity set comes from the ticket, never widened by association.** `cross-cutting` permits more
  than one entity; it never permits inferring one.
- Paths and line numbers, never file contents.
- More than a page of entries returns the entries plus a truncation count.
- Branch B returns paths and scenario names, never a prediction that a test will fail.

### 1.4 When the sweep cannot run

`impact.ran: false` with `impact.reason`. Empty-because-nothing-writes-this-entity and
empty-because-the-sweep-could-not-run are different facts, as `discovery.ran` already distinguishes.
Neither releases the gate (D25), and neither excuses 2.7b — a reviewer with no candidate list still
runs, with less ammunition for task 2, and the gate says so.

## 2. Run-State Contract Additions

```yaml
run:
  design_depth:        trivial | standard | cross-cutting   # resolved in Stage 01 (D32)
  depth_raised_in_02:  false      # a 2.7b finding raised it; Stage 02 re-runs the sweep (D46)

impact:
  ran:                 true | false
  reason:              ok | no-frontend-source | entity-unresolved | submodule-uninitialized
  entities:            ["work_order_candidate"]
  declared:            ["Change Setting"]        # from --impact; human-authored
  candidates:                                     # evidence, never verdicts (D27)
    - flow:            RefreshWorkOrderCandidates
      evidence:        "om-mom-frontend/src/graphql/work-order-candidate.graphql:123"
      writes:          work_order_candidate
      existing_tests:  []                         # branch B → Stage 04 recommendation
      source:          sweep | declared | both
  approved_scenarios:  ["Refreshing candidates does not remove ..."]   # human, at 2.8
  dropped_scenarios:                              # kept with reasons, never deleted
    - name:            "Cancelling a work order ..."
      reason:          "cancel is blocked upstream for interfaced candidates"
  acknowledged_empty:  false
  by_child:                       # `epic` anchors only (D38); absent otherwise
    MOM-12195:
      entities:            ["work_order"]
      candidates:          []
      approved_scenarios:  []
      acknowledged_empty:  true

design:
  selector_evidence:   deferred   # roll-up by declared precedence, ui only (D29)
  adversarial_review:  approved | issues-fixed | issues-open       # three values (D33)
  review_mode:         isolated | inline          # D33
  review_rounds:       1                          # 0..3
  scenarios:
    - name:            Invoice No is displayed as a hyperlink
      selector_evidence: deferred
    - name:            Refreshing candidates does not remove an invoice-attached candidate
      impact:          true
      impact_flow:     RefreshWorkOrderCandidates
      origin:          extraction | adversarial-review
      surface:         ui | api | manual
      dedup:           NEW | REVIEW-OVERLAP MOM-5678   # never UPDATE, never SKIP (D37)
      selector_evidence: source | live-dom | fallback | deferred | n/a   # n/a: api, manual
```

Rules 9–16, following the existing eight:

> **9. `impact.declared[]` and `impact.candidates[]` are never merged into one list.** A flow the
> human declared and the sweep also found is a cross-confirmation; a flow only one produced is a
> different signal. `candidates[].source` records which, and merging erases all three distinctions.

> **10. `impact.approved_scenarios[]` names scenarios, not flows, and is written only by a human at
> 2.8.** Scenarios exist by then (D35), so the human decides on concrete text rather than on a flow
> name. An empty list is meaningless alone — it is read with `acknowledged_empty`, the record that a
> person said there is no impact. `ran: false` implies neither.

> **11. `design.adversarial_review` has exactly three values, and none of them means "did not
> run".** A review that approved writes `approved`; one whose findings were fixed writes
> `issues-fixed`; one leaving round three with findings still open writes `issues-open`. A fourth
> value, `not-run`, was carried over from the draft that let a host without subagent dispatch skip
> the step — D33 deleted that condition, and a value nothing can write is one a reader assumes
> means something. Failure to perform the review at all is an infrastructure stop under
> `operating-rules.md`, not a run-state value.

> **12. `run.design_depth` may scale Sweep 4's entity breadth and document verbosity. It may never
> scale what 2.1 reads, and never disable a gate or 2.7b.** It ratchets up only. A raise inside
> Stage 02 sets `depth_raised_in_02` and re-runs Sweep 4 at the new breadth by loading
> `impact-analysis.md` — a shared leaf, loadable by any stage that needs it, exactly as Stage 02
> already conditionally loads `manual-conversion.md` (D46).

> **13. `design.review_mode` is recorded on every run.** It exists to make the isolation preference
> measurable across real runs instead of assumed — the standard §11 applies to the second-reviewer
> question, applied to this design's own retained hypothesis.

> **14. Scenarios in the impact file carry `NEW` or `REVIEW-OVERLAP <TEST-key>`, never `UPDATE` and
> never `SKIP`** (D37). `REVIEW-OVERLAP` is a distinct label, not a reuse of `REVIEW`: the dedup
> table defines `REVIEW <TEST-key>` as *an existing test matching nothing in the new design*, and an
> impact match runs the other direction. One field carrying both directions under one name leaves
> the gate and the Stage 04 report unable to tell them apart.

> **15. A candidate is satisfied by a scenario **or** by a recorded drop.** 2.7's check that every
> entry in `impact.candidates[]` has a scenario reads `impact.dropped_scenarios[]` as equally
> satisfying. Without this, a gate revision that drops a candidate's only scenario re-enters 2.7,
> fails the check, and fails it again on every retry — three consecutive failures being turn-ending
> condition 4. The same rule is what lets a resumed run honour a drop instead of regenerating the
> scenario a human already rejected.

> **16. `design.selector_evidence` is a reporting roll-up over `surface: ui` scenarios only,** by
> the declared precedence `deferred` > `fallback` > `live-dom` > `source`. `api` and `manual`
> scenarios carry `n/a` and are excluded. Rule 7 says `deferred` and `fallback` are not comparable
> as *evidence*, and they are not — this precedence is a display order for one summary field, and
> the per-scenario value stays the authority. The exclusion is load-bearing: a landed run of only
> `api` scenarios would otherwise roll up to `deferred`, which turn-ending condition 11 stops on.

## 3. Artifact Layout

```
docs/qa/mom-12194-receive-invoice-info-from-apm/
├── ticket.md
├── existing-tests.feature
├── existing-tests-manual.md
├── impact-candidates.md                              # new — sweep evidence, declarations, decisions
├── candidate-monitoring-apm-invoice.feature          # scenarios from acceptance criteria
├── candidate-monitoring-apm-invoice-impact.feature   # new — invariant scenarios
├── test-design.md                                    # §2 AC coverage, §2b impact coverage,
│                                                     # §9 adversarial review findings
└── execution-report.md
```

The impact file's name is the main file's name plus `-impact`, derived, never separately chosen.
Both carry `@REQ_<STORY-KEY>` **at Feature level**, per `gherkin-conventions.md`'s tag table.

`impact-candidates.md` records, per candidate: flow, evidence path, provenance, existing tests, and
the decision with its reason. **A dropped candidate stays in the file with its rejection** — the
next run should not re-litigate a decision a human made, and should be able to see it was made.

`test-design.md` §9 records every reviewer finding and its disposition, **including rejected ones**.
A review whose findings vanish once fixed leaves the next reader unable to tell a design that was
never challenged from one that was challenged and held.

## 4. Stage 01 Changes

Two steps, in this order, after Jira intake produces `ticket.md`:

1. **Resolve `run.design_depth`** from `ticket.md` (D32). Reading the whole ticket to classify costs
   nothing, because 2.1 reads all of it at every depth anyway.
2. **Run Sweep 4**, after sweeps 1–3 (D36). Write `impact.*` to run state and `impact-candidates.md`
   to the artifact folder.

`--impact "<flow>[, <flow>...]"` populates `impact.declared[]` verbatim. The flag is optional and
its absence answers nothing — D25 puts the required answer at the gate, not at intake.

## 5. Stage 02 Changes

Existing step numbers are preserved; two steps are inserted.

| Step | Status |
|---|---|
| 2.1 Requirement analysis | changed — whole ticket (D28) |
| 2.2 Dedup against Xray | unchanged, plus D37 for the impact file |
| 2.3 Scenario design | unchanged |
| 2.4 Element intent map | unchanged |
| **2.4b Impact design** | **new (D35)** |
| 2.5 Write `.feature` | changed — writes both files |
| 2.6 Write `test-design.md` | changed — §2b and §9 |
| 2.7 Self-review | changed — ambiguity check (D34), two impact checks |
| **2.7b Adversarial review** | **new (D31)** |
| 2.8 Human gate | changed — four sections |

### 5.1 Step 2.1, generalized (D28)

Read the **whole ticket** — every section, at every depth. No special rule attaches to any heading
name. Headings are how a writer organized their thoughts, not a schema; a rule keyed to `Out-Scope`
patches one layout and misses the next.

Judgement about which lines are testable constraints is where 2.1 already failed once, which is why
D31 puts a second question on it rather than a stricter rule here.

### 5.2 Step 2.4b — impact design (new, D35)

Design at least one scenario per entry in `impact.candidates[]` **and** per entry in
`impact.declared[]` that the sweep did not find. This is provisional: the human keeps or drops each
scenario at 2.8.

Designing before approval is deliberate. It puts the impact file in front of 2.7's checks, in front
of 2.7b, and in front of the human as concrete text — and it gives attack task 2's findings
somewhere to land, which they had nowhere to do when this step ran after the gate.

When both lists are empty — whether the sweep found nothing or could not run — **no impact
`.feature` file is written**. An empty feature file would be materialized by Stage 03 and imported
by CI as a file with no tests. The gate's impact section still runs (D25); its content is the
sweep's `ran`/`reason` and the required human answer.

Each scenario states the **invariant**, not the new feature:

```gherkin
@REQ_MOM-12194 @IMPACT @Regression_Test
Feature: Existing flows respect the APM invoice attachment

  Scenario: Refreshing candidates does not remove a candidate attached to an APM invoice
    Given a work order candidate is attached to an APM invoice
    When the user changes the work order setting and candidates are refreshed
    Then the attached candidate remains and its invoice information is unchanged
```

`@REQ_` sits at Feature level. `@IMPACT` is a **skill-owned** tag, not an addition to the profile's
`existing_tags` (D45): `existing_tags` records a convention this pipeline *discovered* in the
repository (D5), and writing a skill-invented tag into it inverts the split between the process this
skill owns and the conventions the repo owns. The profile's own tags are carried through unchanged
beside it, as on any other scenario. `@IMPACT` does not appear in `scoped_run_cmd`'s filter —
impact scenarios are selected by having `design.scenarios[]` entries, like every other scenario, and
a tag that changed the run scope would reopen exactly the widening D39 refuses.

**Dedup runs here, on these scenarios, as they are created.** 2.2 precedes this step, so a step-based
reading would leave impact scenarios unlabelled while 2.7 requires every behaviour to carry a label.
Dedup is a rule, not a position (D42): the same normalized-key rule 2.2 states is applied wherever a
scenario comes into existence, including on a 2.7b loop.

One change applies here and nowhere else (D37): a key match labels `REVIEW-OVERLAP <TEST-key>` —
never `UPDATE`, never `SKIP`. Both of those would decide, automatically, that another story's test
now belongs to this one. An existing Change Setting test asserting that refresh *removes* candidates
has a different key and labels `NEW`; that pair is exactly what a human should see, since the two
describe a conditional behaviour whose condition is new.

**A candidate is satisfied by a scenario or by a recorded drop** (rule 15). This step reads
`impact.dropped_scenarios[]` before designing: a candidate a human already rejected on an earlier
run is not re-designed, and the resume path at `02.4` therefore does not regenerate the scenarios
that run's gate threw out.

**The batch is bounded by the gate, not by the candidate count** (D43). The ceiling is what one
human will actually read at one sitting — the same rule `manual-conversion.md` states for a
conversion batch, and the same reasoning: a run producing more scenarios than anyone reads has moved
the bottleneck from writing to reviewing and hidden it behind an approval nobody could give
properly. When the candidate list exceeds that, design the batch, **say the batch was split**, and
carry the remainder into the run that follows.

### 5.3 Step 2.7, three checks added

The six existing checks stand, applied to both files. Added:

- **Ambiguity (D34).** No line of the ticket admitted into scope is left with two readings. The
  resolution is written in `test-design.md` with both readings named.
- Every entry in `impact.candidates[]`, and every unmatched entry in `impact.declared[]`, is
  **satisfied** — by at least one scenario in the impact file, or by an entry in
  `impact.dropped_scenarios[]` (rule 15). Requiring a scenario alone would deadlock the gate: a
  revision that drops a candidate's only scenario re-enters this check, fails it, and fails it again
  on every retry, which turn-ending condition 4 stops on after three.
- No scenario in the impact file carries `UPDATE` or `SKIP`.

`Do not allow user/system modify any candidate has attached to APM's invoice` reads either as *this
release does not build modification* or as *the system must prevent modification*. Both are
recorded; the second is chosen; the choice is visible.

### 5.4 Step 2.7b — adversarial review (new, D31)

Dispatched with `assets/adversarial-review-prompt.md` — an asset rather than a reference file
because it is a template sent verbatim to another agent, not a document a stage reasons from.

**Inputs:** `ticket.md`, both `.feature` files, `test-design.md`, `impact-candidates.md`,
`run.design_depth` with its reason.

`test-design.md` carries the extraction's reasoning, and that is accepted rather than designed
around (Constraint 5). The mechanism rests on the three questions below, not on withholding
context.

**Three attack tasks** (`story` anchor; see §7 for the others):

1. **Uncovered constraints.** Which sentences in `ticket.md` state a rule the system must uphold,
   and which of those have no row in the coverage matrix? Quote the sentence.
2. **Created invariants.** What must remain true of existing behaviour once this story ships that
   was not true before? Check each flow in `impact.candidates[]` against the ticket, and name the
   invariant or state that the flow creates none.
3. **Classification by name.** Which lines were classified by the heading they sit under rather
   than by what the sentence says? Name the line and both readings.

**Output** follows brainstorming's reviewer format: `Approved | Issues Found`, issues as
`[Section]: [issue] — [why it matters]`, recommendations advisory. Its calibration clause is
carried over in intent:

> Only flag issues that would cause real problems. A missing constraint, a contradiction, or a line
> admitting two readings — those are issues. Wording improvements and stylistic preferences are
> not. Approve unless there are serious gaps.

**Mode (D33).** Preferably a subagent. Where dispatch is unavailable, it runs inline with the same
prompt and the same tasks, and `design.review_mode: inline` is recorded and shown at the gate. It
is never skipped for want of dispatch, which is why `adversarial_review` has no `not-run` value
(rule 11).

**Loop.** `Issues Found` routes by task: findings from tasks 1 and 3 return to 2.1; findings from
task 2 return to 2.4b. Either path re-runs 2.7 and then re-reviews. Scenarios added carry
`origin: adversarial-review`, and they are **labelled where they are created** — dedup is a rule,
not a step that ran once at 2.2 (D42). Without that, a scenario added on a loop reaches 2.7's
"every behaviour carries a dedup label" check with none.

**Bounds.** Every dispatch of 2.7b is one round, whatever caused the re-entry, capped at **three**
(matching `operating-rules.md`'s three-strikes rule). Exiting round 3 with findings open writes
`adversarial_review: issues-open`; the open findings go to the gate verbatim and the human decides.
A fourth round would mean extraction and reviewer disagree persistently, which is a question for a
person, not for another loop.

A finding that raises `design_depth` sets `depth_raised_in_02` and **re-runs Sweep 4 at the new
breadth** (rule 12, D46). Stage 02 loads `impact-analysis.md` to do it — a shared leaf, loadable by
whichever stage needs it, exactly as this stage already conditionally loads `manual-conversion.md`.
An earlier draft refused the re-run on the grounds that "a stage never reads another stage's
reference file"; that rule governs *pipeline* files reading each other, and the sweep does not live
in one. The escape hatch offered instead — asking the human to request a resume — named no
reachable `run.resume_from` value, and nothing ever cleared the staleness flag it set.

### 5.5 Step 2.8, human gate

| Section | Content |
|---|---|
| Depth | `design_depth` with its reason, and whether a 2.7b finding raised it mid-run — stated so it can be disagreed with |
| Coverage | AC matrix, dedup labels, element intent map, Open Questions |
| Review | `approved` / `issues-fixed` with each finding and disposition / **`issues-open` with findings verbatim** — plus `review_mode` |
| Impact | Every designed impact scenario with its candidate's evidence path and provenance; `declared[]` alongside `candidates[]`; existing tests per candidate |

The impact section requires one of three answers, and **without one of them the run does not
continue** — turn-ending condition 12 (D44). This is the one place where a human's absence of
knowledge and a human's assertion of no impact must not look alike.

| Answer | Effect |
|---|---|
| Keep a subset | The rest are dropped; see below |
| Keep a subset **and name a flow nobody found** | A revision that **returns to 2.4b**, re-runs 2.7 and 2.7b, and comes back here |
| No feature is impacted | Writes `acknowledged_empty: true`, drops all, deletes the impact file |

The middle row is why "nothing authors Gherkin after this gate" survives literally: an addition is
not written at 2.8. It re-enters the step that authors impact scenarios and passes every check the
first batch passed, under the revision rule this gate already has — *a revision returns to whichever
step it affects and re-runs self-review before returning here*. A human naming a flow the sweep
missed is the Class B case working as designed; letting them hand-write a scenario past 2.7 and
2.7b would be the same hole in a new place.

Impact scenarios are presented **unapproved by default**. A pre-checked list converts the human's
job from deciding to noticing, and a reviewer who is only noticing approves everything.

Dropped scenarios are removed from the `.feature` file before commit and retained with their reasons
in `impact-candidates.md` and `impact.dropped_scenarios[]` — which is also what satisfies 2.7 on the
re-run (rule 15), and what keeps the next run from re-litigating the decision.

**When every impact scenario is dropped, the impact `.feature` file is deleted, not left empty.**
Same reason 2.4b declines to write one: an empty feature file is materialized by Stage 03 and
imported by CI as a file containing no tests. `gherkin-conventions.md`'s degenerate-case rule covers
scenarios blocked at Stage 03 and does not reach a file emptied at the gate, so this is stated here.

The 2.8 next-hop table (`code_state` × `design_only`) is unchanged. Nothing authors Gherkin after
this gate.

### 5.6 What determinism survives

2.7b produces findings, and a model pass varies run to run. Rule 5's guarantee is narrower and is
unaffected: **dedup labels** must be identical across runs over unchanged inputs, and every scenario
2.7b causes to exist still passes through 2.2's normalized-key rule for its label. The scenario
*set* was never deterministic — 2.1 is a model pass too. What changes is that the set is now larger
and challenged rather than smaller and unexamined.

## 6. Stage 03 and Stage 04 Changes

**Stage 03 (D39).** The impact file is a second input to **materialization** and generation. The
scoped run command covers the scenarios that have `design.scenarios[]` entries — both files' — and
nothing else. It is **not** widened to sweep in pre-existing tests from the impact flows' domains:
such a test has no run-state entry, no attempts budget, and no verdict path, and the no-stop zone's
exit condition is a verdict recorded against every scenario in scope. Widening the command would
manufacture in-scope work the stage cannot discharge.

The selector entry gate runs over both files.

Impact scenarios inherit `run.code_state` (D30). `pending` ends the run after Stage 02 under rule 6.

**Stage 04.** Three additions to the report:

- Approved impact scenarios, with the flow and evidence path each came from.
- `design.adversarial_review` and `design.review_mode`. A run that shipped with an inline review, or
  with findings still open, must say so in the artifact a human reads last — not only in a gate they
  saw once.
- **Recommended regression**: Branch B's existing tests per flow, as a list for a human to run or
  schedule. It is a recommendation, not a run.

  A flow is **approved** when at least one of its scenarios is in `impact.approved_scenarios[]` —
  the derivation matters because rule 10 makes that list name scenarios, never flows, so "approved
  flow" is computed and not stored. A flow whose scenarios were **all dropped** still has its tests
  reported, marked as such: the human dropped a scenario, not the observation that tests exist on
  that surface, and dropping the report too would discard the one thing Branch B contributes.

**`host-adaptation.md`.** Its enumeration — *"Two parts of the pipeline dispatch subagents"* — is
now four: discovery's sweeps 1–3, Sweep 4, the selector gate's live-DOM read, and 2.7b. The
degrade-to-inline rule is unchanged and now covers all four (D33).

**`gherkin-conventions.md`.** `@IMPACT` is added to the tag table at Feature level, with the note
that a file carrying it may not contain `UPDATE` rows (D37).

## 7. Anchor Types (D38)

| Anchor | Sweep 4 + depth | 2.7b |
|---|---|---|
| `story` | Once, over the story's entity | Three tasks as specified |
| `epic` | **Per child**, each child's entity, each child's own depth | **Per child**, three tasks, against that child's `.feature` and impact file |
| `test` | Over the requirement the test links to; skipped when it links to none | **Fidelity task set** (below) |

### 7.1 `epic` — one folder, per-child fields

`epic` already fans out to one `.feature` per child; impact analysis follows that fan-out rather than
inventing an epic-level entity no ticket names.

**It does not fan out to more folders.** An epic run has exactly one artifact folder — the epic's,
named `<epic-key>-<slug>` — because that name is the `@REQ_` target, the dedup key, and the resume
glob, and a second folder would be a second identity. A round-2 draft said "each child gets its own
impact file inside that child's artifact folder", which described folders an epic run does not have.
Child impact files live in the epic's folder, named for the child, beside that child's `.feature`.

The per-child values live under `impact.by_child`, keyed by child issue key (§2). Without it, the
fields are flat scalars and an epic's second child overwrites its first — the shape has to carry the
dimension the fan-out creates, or the fan-out is not represented at all.

**The gate stays one review.** Per-child depth, sweep, and review multiply quickly, and the ceiling
is D43's: what one human reads at one sitting. An epic wider than that is split, and the split is
stated. `manual-conversion.md` already says this for conversion batches, in those words.

### 7.2 `test` — a bidirectional fidelity set

`test` anchors run `manual-conversion.md`, whose gate asks whether the translation is faithful, not
whether the test is a good idea. Attack tasks 1 and 3 have no subject there: no ticket prose to
mine, no heading to misclassify. 2.7b runs instead with:

1. **Fidelity, both directions.** What does the source Manual test assert that the Gherkin does not
   — and what does the Gherkin assert that the source does not? `manual-conversion.md` treats an
   added boundary case, a one-case-into-three split, and a dropped step alike, because a silent
   addition is *"indistinguishable from a mistranslation"*. A task asking only what was dropped
   audits one of the two ways a conversion goes wrong.
2. **Created invariants.** Unchanged, when the linked requirement exists; skipped when it does not.

**An `epic` anchor whose children are conversions gets this set too, per child.** `manual-conversion.md`
is loaded for `anchor_type: test` **or** `epic`, so an epic-anchored conversion batch given the story
task set would receive no fidelity review at all — the one review that anchor's gate turns on.

The gate and the impact section run at every anchor type (D25), with `acknowledged_empty` the
correct answer when a conversion creates no invariant.

## 8. Validator Change (C3)

`tools/validate_coupling.py` checks C1 (a `references/shared/` file links to no other file) and C2
(a `references/pipeline/` file does not link to another pipeline file). Neither validator checks
that a file's links resolve or stay within its declared `Loads:` set, so the round-1 acceptance
criterion asserting it was unverifiable.

A link-based check would measure nothing. **Every markdown link in a stage file already sits on the
`Loads:` line itself** — verified across all four stage files — so "each linked leaf is declared" is
tautologically true, and "every link resolves" is already covered by `validate_skills.py`. Round 3
caught this: the first version of C3 would have passed on a skill holding four live violations.

Leaves are cited in prose in backticks, not links, and that is where the coupling actually leaks.

**C3:** in a `references/pipeline/` file, every backticked `` `<name>.md` `` citation that resolves
to a file under `references/shared/` must appear on that file's `Loads:` line. Artifact filenames
(`ticket.md`, `test-design.md`, `execution-report.md`, `existing-tests-manual.md`) and other stage
files are excluded — a stage naming its successor is required behaviour, not a leak.

This is the invariant `stage-02-test-design.md` states in its own header — *"Every leaf this file
cites by rule or condition number is declared here: the `Loads:` line is the disclosure §11.2 rule 1
rests on, and a cited file that goes undeclared is read from memory instead of from the file"* — and
it has never been machine-checked. **It fails today in four places**, all of which this change
fixes:

| File | Cites, undeclared |
|---|---|
| `stage-03-automate.md` | `repo-profile.md`, `commit.md` |
| `stage-04-finish.md` | `gherkin-conventions.md`, `selector-verification.md` |

Failing on landing is the point. A validator that passes the moment it is written has not been
shown to look at anything.

## 9. Acceptance Criteria (D40)

### 9.1 Deterministic — CI-checkable

1. `run.design_depth` is written in Stage 01, before `impact.*`, in `execution-report.md`'s ordering.
2. Sweep 4's record shows it ran after sweeps 1–3; `discovery.md`'s no-ordering claim is scoped to
   sweeps 1–3.
3. `impact.ran: false` and `impact.candidates: []` are distinguishable.
4. A declared flow the sweep also found records `source: both`; `declared[]` and `candidates[]`
   remain separate fields.
5. Every entry in `impact.candidates[]` is satisfied before 2.7 passes by ≥1 scenario in the impact
   file **or** an entry in `impact.dropped_scenarios[]`; a gate revision that drops a candidate's
   only scenario does not fail 2.7 on the re-run.
6. No scenario in the impact file carries `UPDATE` or `SKIP`; a key match there carries
   `REVIEW-OVERLAP`, a label distinct from `REVIEW`.
7. Both `.feature` files carry `@REQ_` at Feature level.
8. `adversarial_review` takes one of **three** values; no code path writes `not-run`; `issues-open`
   has a gate row and a Stage 04 line; `review_mode` is written on every run.
9. `review_rounds` never exceeds 3, and a depth raise consumes a round.
10. A depth raise inside Stage 02 sets `depth_raised_in_02` and **re-runs Sweep 4** at the new
    breadth; no `sweep_breadth_stale` field exists.
11. Nothing writes Gherkin at 2.8; an addition named at the gate re-enters 2.4b and passes 2.7 and
    2.7b before returning. The 2.8 next-hop table is unchanged.
12. `design_depth: trivial` still runs 2.1 over the whole ticket, 2.7b, and 2.8.
13. On a host without dispatch, 2.7b runs inline and records `review_mode: inline`.
14. A `pending` run writes both files and ends after Stage 02 with `resume_from: 02.4`.
15. `design.selector_evidence` follows the precedence `deferred` > `fallback` > `live-dom` >
    `source` over `surface: ui` scenarios only; `api` and `manual` scenarios carry `n/a`, and a
    landed run containing no `ui` scenario does not roll up to `deferred`.
16. Stage 03's scoped run command covers only scenarios with `design.scenarios[]` entries.
17. Reviewer findings, including rejected ones, remain in `test-design.md` §9; dropped impact
    scenarios remain in `impact-candidates.md`.
18. `epic` produces one impact file per child **inside the epic's single artifact folder**, with
    per-child values under `impact.by_child`; `test` runs the bidirectional fidelity set, and so
    does an `epic` whose children are conversions.
19. `tools/validate_skills.py` passes, including the root README version badge at `0.3.0`.
20. `tools/validate_coupling.py` passes C1, C2, and the new C3 — and C3, run against the skill
    **before** this change's stage-file edits, reports the four undeclared citations named in §8. A
    C3 that passes on the pre-change tree has not been shown to check anything.
21. Every impact scenario carries a dedup label at the moment it is created, including those added
    on a 2.7b loop.
22. `operating-rules.md` lists the impact gate as turn-ending condition 12.
23. `@IMPACT` does not appear in the profile's `existing_tags` and does not appear in
    `scoped_run_cmd`'s filter.
24. `test-case/speckit-qa-auto/test-cases.md`'s existing AC07 row is amended: it currently requires
    byte-identical scenario sets across two runs, which §5.6 says was never guaranteed. Its
    determinism claim is narrowed to dedup labels.

### 9.2 Eval cases — manual, recorded, not CI gates

These assert that a model pass returns a judgement. One passing run does not distinguish the
mechanism from luck, so each is run **three times** and recorded in
`test-case/speckit-qa-auto/test-cases.md` with the number of runs that produced the finding. A case
that does not reach 3/3 is recorded at its rate, not silently dropped — the rate is the evidence
this design asked for.

| # | Fixture | Expected |
|---|---|---|
Each fixture is a **complete 2.7b input set** — `ticket.md`, both `.feature` files, `test-design.md`,
`impact-candidates.md`, and a depth with its reason — not a single file. They live under
`test-case/speckit-qa-auto/fixtures/<name>/`, one directory per case; the repository has no prior
`fixtures/` convention, so this establishes one.

| # | Fixture | Expected |
|---|---|---|
| E1 | `fixtures/out-scope-constraint/` — the real MOM-12194 `ticket.md` (branch `test/mom-12194-…`, commit `7fa828f`) with a `test-design.md` covering only the eight AC rows | Task 1 names the `Do not allow user/system modify…` line |
| E2 | E1's set, with `impact-candidates.md` carrying `RefreshWorkOrderCandidates` and its evidence path | Task 2 names the refresh invariant |
| E3 | `fixtures/constraint-under-notes/` — the same constraint filed under a heading named `Notes`, with an AC table complete without it | Task 1 names it, with no rule anywhere keyed to a heading |
| E4 | E3's set, run `inline` and run `isolated` | The two rates, recorded side by side |

E3 is the case that distinguishes this design from a rule keyed to `Out-Scope`: if the mechanism
only fires on that heading, E3 fails and the design is what it was accused of being. Its AC table
must be complete without the constraint, or a reviewer could find the gap from the AC table alone
and the fixture proves nothing.

**E4 runs over E3, not E1.** E1 is built so the finding is expected every time, and comparing two
ceilings cannot discriminate — a round-2 draft made exactly that mistake. E3 is the harder case, so
its rate has room to differ. `review_mode` is otherwise an observation of host capability with no
flag to force it, and "no flag skips a gate" forecloses adding one casually; E4 is therefore run by
executing the reviewer both ways against a fixture directory, outside a pipeline run.

**What a rate obliges.** A case below 3/3 does not block this design — it is recorded, and it is the
input to the §11 question of whether one adversarial pass needs a second. A rate nobody writes down
is a design decision made by forgetting; a rate written down with no consequence named is the same
thing with extra steps, which is why the consequence is named here.

## 10. What This Does Not Do

- **No automatic approval.** A sweep candidate becomes a shipped scenario only through a person.
- **No editing of existing feature files.** The Change Setting `.feature` in the test tree is not
  touched (D8).
- **No prediction of test failure.** Branch B reports which tests touch the same surface; Stage 04
  recommends running them.
- **No second entry flag for impact.** `--impact` supplies declarations only.
- **No reviewer-authored artifacts.** 2.7b returns findings; 2.1 and 2.4b write the files.

## 11. Out Of Scope (v2 Candidates)

- Backend service traceability where the API repo is not checked out
- Cross-story invariant registry — a persistent record so later stories inherit earlier constraints
- Detecting the inverse case: a story that *removes* an invariant
- Ranking candidates by risk. Ranking is a verdict, and D27 says sweeps do not produce those
- A second reviewer over 2.7b's findings. One adversarial pass is the change being made; whether it
  needs its own auditor is a question for E1–E4's recorded rates, not for this design
