# speckit-qa-auto — Impact Analysis (Blast Radius)

Date: 2026-08-20
Status: approved (design), not yet implemented
Scope: additive change to `speckit-qa-auto/` (version `0.2.0 → 0.3.0`); one new shared leaf; edits
to `discovery.md`, `run-state.md`, `stage-01-intake.md`, `stage-02-test-design.md`,
`stage-03-automate.md`, `SKILL.md`, `README.md`; new rows in `test-case/speckit-qa-auto/`.
Supersedes nothing in [`2026-08-19-speckit-qa-auto-design.md`](2026-08-19-speckit-qa-auto-design.md);
extends it. Decision numbering continues from that document's D22.

## Problem

A story tells you what the feature does. It rarely tells you what the feature *breaks*.

The pipeline as built turns acceptance criteria into scenarios and stops there. Two classes of
required coverage fall outside that boundary, and a real run against MOM-12194 dropped both.

### Class A — a constraint stated in the ticket, outside the AC table

`docs/qa/mom-12194-receive-invoice-info-from-apm/ticket.md` carries this line under **Out-Scope**:

> Do not allow user/system modify any candidate has attached to APM's invoice.

It is a testable constraint, filed under a heading whose other entries are genuinely not-built
(`Payment Due Date`, `Candidate Invoice Amount`). No scenario covers it, because
`stage-02-test-design.md` §2.1 reads only the acceptance criteria:

> Turn `ticket.md`'s acceptance criteria into a list of testable behaviours.

and the design document it produced records the same boundary as a fact about itself:

> Eight testable behaviours derived from `ticket.md`'s Scenarios table

The coverage matrix then reported **"No criterion is uncovered."** That statement is true against
its own definition of criterion and false against the ticket. **A gap that reports itself as full
coverage is worse than a gap that reports nothing** — it consumes the reviewer's attention budget
and returns a false negative.

### Class B — an invariant imposed on a feature the ticket never names

Changing a work order setting refreshes its candidates, which removes and regenerates them. Once a
candidate is attached to an APM invoice it must survive that refresh. The invoice story creates
this invariant; the Change Setting story predates it and says nothing.

Nothing in the pipeline can see it. `discovery.md` runs three sweeps and all three exist to
**deduplicate**, not to find impact:

| Sweep | Finds | Would it surface Change Setting? |
|---|---|---|
| 1 — Jira linkage | issues one hop from the anchor | Only if a human had already linked it |
| 2 — Xray tests | tests linked to the anchor | No |
| 3 — Repo tests | existing `.feature` files, for key matching | No |

`grep -rniE "regress\|impact\|blast\|affected"` across `speckit-qa-auto/` returns five hits, none
of them logic: one README line about suite scope, one Stage 03 scope sentence, two `@Regression_Test`
tag references, and one red-flag row. **The concept does not exist in the skill.**

## Design Decisions

| # | Decision | Rationale |
|---|---|---|
| D23 | Impact candidates come from **both** an automated sweep **and** an explicit human declaration, merged and never collapsed | User directive. Each covers the other's failure mode: a human who forgets is backed by the sweep; a sweep that misses domain knowledge is backed by the human. Keeping them in separate fields preserves the cross-confirmation signal that merging would destroy |
| D24 | Impact scenarios live in a **separate `.feature` file inside the same artifact folder**, under the same `@REQ_` tag | User directive. They exercise a different domain — different page objects, different selectors, different Stage 03 scope — while the artifact folder name remains the single identity (`@REQ_` target, dedup key, resume glob) that the whole pipeline indexes on |
| D25 | The Stage 02 gate **always** presents the impact section and **always** requires an explicit answer, including when the sweep found nothing | User directive. Class B knowledge lives only in a human's head; an empty sweep is not evidence of no impact. `impact.acknowledged_empty` records that a person said so, the same way `xray.dedup: not-run` records that dedup did not run |
| D26 | Sweep 4 runs **entity mutation traceability (code) and test inventory (existing tests)** in parallel; domain-vocabulary search is rejected | They answer different questions — "what can break that nobody tests" versus "what tests must re-run" — so they are complements, not alternatives. Vocabulary search on a mature project returns most of the system, which `discovery.md` already names as "noise priced as signal" |
| D27 | Sweep 4 returns **flows with evidence paths**, never the word *affected* | Rule 5 of the run-state contract, applied to the new sweep. Subagent output varies run to run; a verdict formed inside a subagent would make the approved set vary too |
| D28 | Step 2.1 reads **In-Scope, Out-Scope, Logical, and Edge Cases** in addition to the AC table, and every Out-Scope line must be classified `not-built` or `constraint` | This is the mechanism that catches Class A. Classification is forced for the same reason D25 forces an answer: silence is what produced the defect |
| D29 | `design.scenarios[].selector_evidence` is added per scenario; the existing top-level `design.selector_evidence` is redefined as the **weakest value present** | User choice. One run now legitimately holds two evidence states — `deferred` for the unbuilt feature, `source` for the existing flow the impact scenario touches. Rule 7 (`deferred` is not `fallback`) only carries meaning where the distinction is real, which is per scenario |
| D30 | Impact scenarios inherit `run.code_state` from the anchor feature | The invariant does not exist until the anchor's code lands, so a `pending` run cannot execute them. This follows from rule 6 unchanged — **no new rule is introduced** |

## Constraint 4: Discovery Gathers Evidence, Impact Included

`discovery.md`'s governing rule extends to Sweep 4 without amendment: sweeps find, the main run
decides, and a human approves. Concretely, Sweep 4 may return

```yaml
- flow:     RefreshWorkOrderCandidates
  evidence: "om-mom-frontend/src/graphql/work-order-candidate.graphql:123"
  writes:   work_order_candidate
```

and may not return `affected: true`, `risk: high`, or `needs regression`. The transition from
candidate to approved happens at the Stage 02 gate, performed by a person, recorded in
`impact.approved[]`.

## 1. Sweep 4 — Impact Candidates

Runs in Stage 01 alongside sweeps 1–3, sharing no inputs and no ordering with them. Two branches,
concurrent, one merged result.

### 1.1 Branch A — entity mutation traceability

1. Resolve the anchor's primary entity from `ticket.md`. MOM-12194 resolves to
   `work_order_candidate` (navigation names Candidate Monitoring; the Requirements table attaches
   invoice data to candidates).
2. Find every write operation against that entity in the frontend source and, where reachable, the
   API schema. In the reference repo this is one file:

   | Operation | File |
   |---|---|
   | `UpdateWorkOrderCandidateAmendment` | `graphql/work-order-candidate.graphql:111` |
   | `RefreshWorkOrderCandidates` | `graphql/work-order-candidate.graphql:123` |
   | `ReassignWorkOrderCandidateVendor` | `graphql/work-order-candidate.graphql:211` |
   | `CancelWorkOrderCandidates` | `graphql/work-order-candidate.graphql:283` |

3. Map each operation to the flow that calls it and the screen that flow belongs to.

`RefreshWorkOrderCandidates` is the Change Setting flow — the Class B case, produced mechanically
from the ticket plus the schema, with no inference about business intent.

### 1.2 Branch B — test inventory

Scan the `.feature` files the repo profile named plus the Xray tests sweep 2 returned, and record
those exercising the same entity or screen. Returns `feature_path` and scenario names only.

Branch A finds what may break with no test guarding it. Branch B finds what tests must re-run.
Neither subsumes the other; a flow appearing in both is a stronger candidate, and the merged record
keeps both provenances.

### 1.3 Bounds

`discovery.md`'s anti-crawl bounds apply, adapted:

- **One hop.** Entity → writers of that entity → owning flow. Not onward to entities those flows
  also touch; two hops from `work_order_candidate` reaches most of the system.
- **Entity set comes from the ticket, never widened by association.** `work_order_candidate`, not
  also `work_order` because it sounds related.
- Paths and line numbers, never file contents.
- More than a page of entries returns the entries plus a truncation count. A silent cap reads as a
  complete answer.
- Branch B returns paths and scenario names, never a prediction that a test will fail.

### 1.4 When the sweep cannot run

Absent frontend source, an uninitialized submodule, or an unresolvable entity: `impact.ran: false`
with `impact.reason` naming which. Empty-because-nothing-writes-this-entity and
empty-because-the-sweep-could-not-run are different facts, exactly as `discovery.ran` already
distinguishes them. Neither value releases the gate at 2.8 — see D25.

## 2. Run-State Contract Additions

Added to `run-state.md`'s field reference:

```yaml
impact:
  ran:                 true | false
  reason:              ok | no-frontend-source | entity-unresolved | submodule-uninitialized
  entities:            ["work_order_candidate"]
  declared:                                     # from --impact; human-authored
    - "Change Setting"
  candidates:                                   # evidence, never verdicts (D27)
    - flow:            RefreshWorkOrderCandidates
      evidence:        "om-mom-frontend/src/graphql/work-order-candidate.graphql:123"
      writes:          work_order_candidate
      existing_tests:  []                       # branch B
      source:          sweep | declared | both
  approved:            ["RefreshWorkOrderCandidates"]   # written by the human at 2.8
  acknowledged_empty:  false                    # true only when a human states there is no impact
```

Amended under `design`:

```yaml
design:
  selector_evidence:   deferred                 # roll-up: weakest value present (D29)
  scenarios:
    - name:            Invoice No is displayed as a hyperlink
      selector_evidence: deferred
    - name:            Refreshing candidates does not remove an invoice-attached candidate
      impact:          true
      impact_flow:     RefreshWorkOrderCandidates
      selector_evidence: source
```

Two new rules follow the existing eight:

> **9. `impact.declared[]` and `impact.candidates[]` are never merged into one list.** A flow the
> human declared and the sweep also found is a cross-confirmation; a flow only one of them
> produced is a different signal. `candidates[].source` records which, and merging the lists would
> erase all three distinctions.

> **10. `impact.approved[]` is written only by a human at the Stage 02 gate.** An empty
> `approved[]` is meaningless on its own — it is read together with `acknowledged_empty`, which is
> the record that a person said there is no impact. `ran: false` never implies either.

## 3. Artifact Layout

```
docs/qa/mom-12194-receive-invoice-info-from-apm/
├── ticket.md
├── existing-tests.feature
├── existing-tests-manual.md
├── impact-analysis.md                              # new — sweep evidence, declarations, approvals
├── candidate-monitoring-apm-invoice.feature         # scenarios from acceptance criteria
├── candidate-monitoring-apm-invoice-impact.feature  # new — invariant scenarios
├── test-design.md                                   # §2 AC coverage, §2b impact coverage
└── execution-report.md
```

The impact file's name is the main file's name plus `-impact`, derived, never separately chosen.
Both carry the same `@REQ_<STORY-KEY>` at feature level; the folder remains the one identity.

`impact-analysis.md` records, for each candidate: flow, evidence path, provenance (`sweep`,
`declared`, `both`), existing tests found, and the approval decision with the reason given. A
rejected candidate stays in the file with its rejection — the next run over the same story should
not re-litigate a decision a human already made, and should be able to see that it was made.

## 4. Stage 01 Changes

One step added after the existing sweeps: run Sweep 4, write `impact.*` into run state and
`impact-analysis.md` into the artifact folder. `--impact "<flow>[, <flow>...]"` populates
`impact.declared[]` verbatim; the flag is optional and its absence is not an answer to anything
(D25 places the required answer at the gate, not at intake).

## 5. Stage 02 Changes

### 5.1 Step 2.1, expanded (D28)

Beyond the acceptance criteria table, read `In-Scope`, `Out-Scope`, `Logical`, and `Edge Cases`.
Every `Out-Scope` line is classified exactly once:

| Classification | Meaning | Where it goes |
|---|---|---|
| `not-built` | Genuinely outside this release | Recorded in `test-design.md`, no scenario |
| `constraint` | A rule the system must uphold | A behaviour, designed into the impact file |

Applied to MOM-12194's five Out-Scope lines:

| Line | Classification |
|---|---|
| Handle in-discrepancy invoices | `not-built` |
| Candidate Invoice Amount | `not-built` |
| Payment Due Date | `not-built` |
| Detach candidates from APM's invoice | `not-built` |
| Do not allow user/system modify any candidate has attached to APM's invoice | `constraint` |

Four of five are genuinely not-built, which is why the fifth was missed: the heading's usual
meaning is correct four times out of five, and the exception is stated in the grammar of a rule
("do not allow") rather than the grammar of a scope boundary.

An unclassified line fails self-review at 2.7. **There is no silent path past a line of the
ticket.**

### 5.2 Step 2.8, gate section B (D25)

The gate presents, always:

- Sweep candidates with evidence paths, each with its provenance
- `impact.declared[]` alongside them, not folded in
- Existing tests found for each candidate

and requires one of: an approved subset, an approved subset plus additions, or an explicit
statement that no feature is impacted. The third writes `acknowledged_empty: true`. **Without one
of those three answers the run does not continue** — this is the one place in the pipeline where a
human's absence of knowledge and a human's assertion of no impact must not look alike.

Sweep candidates are presented unapproved by default. A pre-checked list converts the human's job
from deciding to noticing, and a reviewer who is only noticing approves everything.

### 5.3 Step 2.9, impact design (new)

Runs after 2.8 approval, over `impact.approved[]` only. Each approved flow yields at least one
scenario stating the **invariant**, not the new feature:

```gherkin
@REQ_MOM-12194 @IMPACT @Regression_Test
Scenario: Refreshing candidates does not remove a candidate attached to an APM invoice
  Given a work order candidate is attached to an APM invoice
  When the user changes the work order setting and candidates are refreshed
  Then the attached candidate remains and its invoice information is unchanged
```

Impact scenarios pass through 2.2's normalized-key dedup unchanged. An existing Change Setting test
asserting that refresh removes candidates has a different normalized key, so it labels `NEW` — and
the pair is exactly what a reviewer should see, since the two describe a conditional behaviour
whose condition is new.

`@IMPACT` is a new tag, additive to the profile's `existing_tags` per `gherkin-conventions.md`.

### 5.4 Step 2.7, two checks added

- Every `Out-Scope` line carries a classification
- Every flow in `impact.approved[]` has at least one scenario in the impact file

Both are mechanical. Both are subject to the existing three-strikes stop.

## 6. Stage 03 and Stage 04 Changes

**Stage 03.** The impact file is a second input to materialization and generation. Default scope
widens from the anchor's domain to the anchor's domain plus the domain of each approved flow —
narrower than `--full-suite`, wider than today. The selector entry gate runs over both files;
impact scenarios generally resolve to `source` evidence because the flow they touch already exists,
which is the case D29 exists to represent.

Impact scenarios inherit `run.code_state`. `pending` means the invariant has no code to hold it, so
the run ends after Stage 02 under rule 6 with no exception added (D30).

**Stage 04.** Impact scenarios are Cucumber tests carrying the anchor's `@REQ_`, imported by the
existing CI path from `docs/qa/`. They belong to the story that created the invariant even though
they exercise another screen. The Stage 04 report gains one line: approved flows, and the count of
scenarios written per flow.

## 7. What This Does Not Do

- **No automatic approval.** A sweep candidate never becomes a scenario without a person.
- **No editing of existing feature files.** The Change Setting `.feature` in the test tree is not
  touched; the new scenario lives in this story's artifact folder. Authoring in the test tree
  remains forbidden (D8).
- **No prediction of test failure.** Branch B reports which tests touch the same surface. Whether
  they break is what running them determines.
- **No second entry flag for impact.** `--impact` supplies declarations; it never becomes an
  alternative anchor.

## 8. Acceptance Criteria

1. A run over MOM-12194 with no `--impact` flag surfaces `RefreshWorkOrderCandidates` as a
   candidate with its evidence path.
2. A run over MOM-12194 classifies `Do not allow user/system modify any candidate has attached to
   APM's invoice` as `constraint`, and self-review fails if it is left unclassified.
3. A run whose sweep returns zero candidates still stops at the gate and cannot proceed without
   either an added flow or `acknowledged_empty: true`.
4. `impact.ran: false` and `impact.candidates: []` are distinguishable in `execution-report.md`.
5. A declared flow that the sweep also found records `source: both`; declarations and candidates
   remain in separate fields.
6. A `pending` run writes the impact file and ends after Stage 02 with `resume_from: 02.4`, having
   added no rule beyond rule 6.
7. `design.selector_evidence` reports `deferred` when any scenario is `deferred`, while the
   per-scenario field on an impact scenario reports `source`.
8. `tools/validate_skills.py` passes; no reference file links outside its declared `Loads:` set.

## 9. Out Of Scope (v2 Candidates)

- Backend service traceability where the API repo is not checked out
- Cross-story invariant registry — a persistent record of every invariant so later stories inherit
  the constraints earlier ones created
- Automatic detection of the inverse case: a later story that *removes* an invariant
- Ranking candidates by risk. Ranking is a verdict, and D27 says sweeps do not produce those
