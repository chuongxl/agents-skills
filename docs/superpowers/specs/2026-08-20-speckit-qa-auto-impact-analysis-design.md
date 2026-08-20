# speckit-qa-auto — Adversarial Design Review and Impact Analysis

Date: 2026-08-20
Status: approved (design), not yet implemented
Scope: additive change to `speckit-qa-auto/` (version `0.2.0 → 0.3.0`); one new shared leaf
(`impact-analysis.md`) and one new asset (`adversarial-review-prompt.md`); edits to `discovery.md`,
`run-state.md`, `host-adaptation.md`, `stage-01-intake.md`, `stage-02-test-design.md`,
`stage-03-automate.md`, `SKILL.md`, `README.md`; new rows in `test-case/speckit-qa-auto/`.
Extends [`2026-08-19-speckit-qa-auto-design.md`](2026-08-19-speckit-qa-auto-design.md); decision
numbering continues from that document's D22.

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
The concept does not exist.

### Why "more input" is not the fix

The obvious response is to fetch more: a fourth sweep, wider ticket parsing, stricter parsing
rules. **Class A refutes it.** That sentence was already in `ticket.md`, already fetched, already
in the context of the model that wrote `test-design.md`. Nothing was missing from the input.

What was missing was **anything that challenged the output**. Step 2.7 self-review checks *"every
acceptance criterion is covered by at least one scenario"* — a check whose scope is defined by the
same pass that did the extraction. It is self-consistent, and it is wrong. A pass cannot audit the
boundary it drew.

So the primary fix is a **second, independent pass whose only job is to attack the design**, and
the sweep is demoted from detection mechanism to evidence supplier for that pass.

## Design Decisions

| # | Decision | Rationale |
|---|---|---|
| D23 | Impact candidates come from **both** an automated sweep **and** an explicit human declaration, merged and never collapsed | User directive. Each covers the other's failure mode. Keeping them in separate fields preserves the cross-confirmation signal that merging destroys |
| D24 | Impact scenarios live in a **separate `.feature` file inside the same artifact folder**, under the same `@REQ_` tag | User directive. They exercise a different domain — different page objects, selectors, Stage 03 scope — while the artifact folder name remains the single identity (`@REQ_` target, dedup key, resume glob) |
| D25 | The Stage 02 gate **always** presents the impact section and **always** requires an explicit answer, including when the sweep found nothing | User directive. Class B knowledge lives only in a human's head; an empty sweep is not evidence of no impact. `impact.acknowledged_empty` records that a person said so, as `xray.dedup: not-run` records that dedup did not run |
| D26 | Sweep 4 runs **entity mutation traceability** and **test inventory** in parallel; domain-vocabulary search is rejected | They answer different questions — "what can break that nobody tests" versus "what tests must re-run". Vocabulary search on a mature project returns most of the system, which `discovery.md` already names "noise priced as signal" |
| D27 | Sweep 4 returns **flows with evidence paths**, never the word *affected* | Rule 5 applied to the new sweep. Subagent output varies run to run; a verdict formed inside a sweep would make the approved set vary too |
| D28 | Step 2.1 reads the **whole ticket**, not the AC table alone. It does **not** get a hard-coded rule about the heading named "Out-Scope" | Revised after review. A rule keyed to that heading patches exactly one ticket layout; the next ticket files its constraint under "Notes" or "Assumptions" and the rule misses it. Generalizing the read is cheap; generalizing the *judgement* is what D31 is for |
| D29 | `design.scenarios[].selector_evidence` is added per scenario; the top-level field is redefined as the **weakest value present** | User choice. One run now legitimately holds two evidence states — `deferred` for the unbuilt feature, `source` for the existing flow an impact scenario touches. Rule 7 (`deferred` is not `fallback`) only carries meaning where the distinction is real, which is per scenario |
| D30 | Impact scenarios inherit `run.code_state` from the anchor feature | The invariant does not exist until the anchor's code lands. Follows from rule 6 unchanged — no new rule |
| **D31** | **Step 2.7b: an adversarial review subagent with a clean context, three fixed attack tasks, and brainstorming's approve-unless-serious calibration** | The primary fix. Self-review cannot find what the extraction's own boundary excluded (see Constraint 5). Modelled on `superpowers/brainstorming/spec-document-reviewer-prompt.md`, including its calibration clause — an uncalibrated reviewer floods the gate with wording findings and trains the human to skim |
| **D32** | **`run.design_depth` is classified and stated out loud; it may scale the work but may never disable 2.7b or 2.8. One-way ratchet** | Ported from brainstorming's classify-first step and its anti-pattern *"what scales with simplicity is the artifact, never the approval"*. A depth flag that could switch off the review would let the extraction pass exempt itself — the exact self-assessment that failed |
| **D33** | **2.7b is the single exception to `host-adaptation.md`'s degrade-to-inline rule. Without subagent dispatch it records `not-run`** | That rule's stated reason is *"what is lost is context isolation, not capability."* For 2.7b, context isolation **is** the capability. Run inline, 2.7b is not a degraded review; it is no review wearing the name of one |
| **D34** | **Step 2.7 gains an ambiguity check**: any ticket line that admits two readings is resolved to one, explicitly, in `test-design.md` | Brainstorming's spec self-review has this check; 2.7's six checks did not. `Out-Scope` admitting both *not-built* and *must-not-happen* is precisely a two-reading line, and no check looked for one |

## Constraint 4: Discovery Gathers Evidence, Impact Included

`discovery.md`'s governing rule extends to Sweep 4 without amendment. Sweep 4 may return

```yaml
- flow:     RefreshWorkOrderCandidates
  evidence: "om-mom-frontend/src/graphql/work-order-candidate.graphql:123"
  writes:   work_order_candidate
```

and may not return `affected: true`, `risk: high`, or `needs regression`. Candidate becomes
approved at the Stage 02 gate, by a person, recorded in `impact.approved[]`.

## Constraint 5: A Pass Cannot Audit Its Own Boundary

Step 2.7's checks are mechanical and they are all **inside** the extraction's frame: every check
takes the set of criteria the extraction produced and verifies each has a scenario. No arrangement
of such checks can find a criterion the extraction never admitted was one. Class A is not a bug in
2.7's check list; it is a limit of where the check list stands.

Two consequences fix the shape of everything below.

**The reviewer's context must exclude the extraction's reasoning.** It reads `ticket.md`,
`test-design.md`, the `.feature` files, and `impact.candidates[]` — the inputs and the outputs, not
the argument connecting them. Given the argument, a reviewer evaluates whether the conclusion
follows from it, which is a different and much weaker question than whether the conclusion is right.

**Therefore 2.7b cannot degrade to inline** (D33). Inline, the argument is unavoidably present.

## 1. Sweep 4 — Impact Candidates

Runs in Stage 01 alongside sweeps 1–3. Two branches, concurrent, one merged result. Its output is
**evidence for 2.7b's second attack task** first and a gate input second.

### 1.1 Branch A — entity mutation traceability

1. Resolve the anchor's primary entity from `ticket.md`. MOM-12194 resolves to
   `work_order_candidate`.
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
from the ticket plus the schema.

### 1.2 Branch B — test inventory

Scan the `.feature` files the repo profile named plus the Xray tests sweep 2 returned; record those
exercising the same entity or screen. Returns `feature_path` and scenario names only.

Branch A finds what may break with no test guarding it; Branch B finds what tests must re-run.
Neither subsumes the other, and a flow in both is a stronger candidate — the merged record keeps
both provenances.

### 1.3 Bounds

`discovery.md`'s anti-crawl bounds apply, adapted, scaled by `run.design_depth` (D32):

- **One hop.** Entity → writers of that entity → owning flow. Not onward to entities those flows
  also touch; two hops from `work_order_candidate` reaches most of the system.
- **Entity set comes from the ticket, never widened by association.** `work_order_candidate`, not
  also `work_order` because it sounds related. `cross-cutting` depth permits more than one entity;
  it does not permit inferring them.
- Paths and line numbers, never file contents.
- More than a page of entries returns the entries plus a truncation count. A silent cap reads as a
  complete answer.
- Branch B returns paths and scenario names, never a prediction that a test will fail.

### 1.4 When the sweep cannot run

`impact.ran: false` with `impact.reason` naming which cause. Empty-because-nothing-writes-this-entity
and empty-because-the-sweep-could-not-run are different facts, as `discovery.ran` already
distinguishes. Neither releases the gate at 2.8 (D25), and neither excuses 2.7b — a reviewer with
no candidate list still runs, with less ammunition, and says so.

## 2. Run-State Contract Additions

```yaml
run:
  design_depth:        trivial | standard | cross-cutting   # D32; stated at the gate

impact:
  ran:                 true | false
  reason:              ok | no-frontend-source | entity-unresolved | submodule-uninitialized
  entities:            ["work_order_candidate"]
  declared:            ["Change Setting"]      # from --impact; human-authored
  candidates:                                   # evidence, never verdicts (D27)
    - flow:            RefreshWorkOrderCandidates
      evidence:        "om-mom-frontend/src/graphql/work-order-candidate.graphql:123"
      writes:          work_order_candidate
      existing_tests:  []                       # branch B
      source:          sweep | declared | both
  approved:            ["RefreshWorkOrderCandidates"]   # written by the human at 2.8
  acknowledged_empty:  false

design:
  selector_evidence:   deferred                 # roll-up: weakest value present (D29)
  adversarial_review:  approved | issues-fixed | not-run    # D31, D33
  review_reason:       no-subagent-dispatch     # present only when not-run
  review_rounds:       1
  scenarios:
    - name:            Invoice No is displayed as a hyperlink
      selector_evidence: deferred
    - name:            Refreshing candidates does not remove an invoice-attached candidate
      impact:          true
      impact_flow:     RefreshWorkOrderCandidates
      origin:          extraction | adversarial-review        # D31
      selector_evidence: source
```

Rules 9–12, following the existing eight:

> **9. `impact.declared[]` and `impact.candidates[]` are never merged into one list.** A flow the
> human declared and the sweep also found is a cross-confirmation; a flow only one produced is a
> different signal. `candidates[].source` records which, and merging erases all three distinctions.

> **10. `impact.approved[]` is written only by a human at the Stage 02 gate.** An empty
> `approved[]` is meaningless alone — it is read with `acknowledged_empty`, the record that a person
> said there is no impact. `ran: false` implies neither.

> **11. `design.adversarial_review: not-run` is never written because the reviewer found nothing.**
> A reviewer that ran and approved writes `approved`. `not-run` means the review did not happen,
> and it is surfaced at the gate rather than buried, for the reason `xray.dedup` draws the same
> distinction.

> **12. `run.design_depth` may scale work; it may never disable a gate or 2.7b.** It ratchets up
> only. A reviewer finding raises it and never lowers it, and the value that reaches the gate is
> the highest the run ever held.

## 3. Artifact Layout

```
docs/qa/mom-12194-receive-invoice-info-from-apm/
├── ticket.md
├── existing-tests.feature
├── existing-tests-manual.md
├── impact-analysis.md                               # new — sweep evidence, declarations, approvals
├── candidate-monitoring-apm-invoice.feature          # scenarios from acceptance criteria
├── candidate-monitoring-apm-invoice-impact.feature   # new — invariant scenarios
├── test-design.md                                    # §2 AC coverage, §2b impact coverage,
│                                                     # §9 adversarial review findings
└── execution-report.md
```

The impact file's name is the main file's name plus `-impact`, derived, never separately chosen.
Both carry the same `@REQ_<STORY-KEY>`; the folder remains the one identity.

`impact-analysis.md` records, per candidate: flow, evidence path, provenance, existing tests found,
and the approval decision with its reason. **A rejected candidate stays in the file with its
rejection** — the next run should not re-litigate a decision a human made, and should be able to
see it was made.

`test-design.md` §9 records every reviewer finding and its disposition, including findings that
were rejected. A review whose findings vanish once fixed leaves the next reader unable to tell a
design that was never challenged from one that was challenged and held.

## 4. Stage 01 Changes

One step added after the existing sweeps: run Sweep 4, write `impact.*` to run state and
`impact-analysis.md` to the artifact folder. `--impact "<flow>[, <flow>...]"` populates
`impact.declared[]` verbatim; the flag is optional, and its absence answers nothing (D25 puts the
required answer at the gate, not at intake).

## 5. Stage 02 Changes

### 5.1 Step 2.0 — classify design depth (new, D32)

Before extraction, resolve `run.design_depth` and **state it, with its reason, in
`test-design.md`**:

| Depth | Signals | Scales |
|---|---|---|
| `trivial` | Single surface, no new entity write, no state transition | 2.1 reads the AC table and In-Scope; Sweep 4 takes one entity; `test-design.md` stays short |
| `standard` | One entity, one screen, ordinary CRUD or display | Default |
| `cross-cutting` | New entity write, a new state a record can hold, or an explicit prohibition anywhere in the ticket | 2.1 reads every section; Sweep 4 may take more than one entity; §2b required |

MOM-12194 classifies `cross-cutting` on two independent signals: candidates gain a new state
(*attached to an invoice*), and the ticket contains an explicit prohibition.

Stating the classification is not decoration. An unstated classification cannot be disagreed with
at the gate, and the run that dropped Class A had made this judgement implicitly and never showed
it.

Depth does not gate anything (rule 12). 2.7b and 2.8 run at every depth.

### 5.2 Step 2.1, generalized (D28)

Read the **whole ticket** — every section, at `cross-cutting` depth — not the AC table alone. No
special rule attaches to any heading name. Headings are how a writer organized their thoughts, not
a schema; a rule keyed to `Out-Scope` patches one layout and misses the next.

Judgement about which lines are testable constraints is where 2.1 already failed once, which is why
D31 puts a second pass on it rather than a stricter rule here.

### 5.3 Step 2.7, ambiguity check added (D34)

The six existing checks stand. One is added:

> **No line of the ticket admitted into scope is left with two readings.** A line that could be
> read two ways is resolved to one, and the resolution is written in `test-design.md` with both
> readings named.

`Do not allow user/system modify any candidate has attached to APM's invoice` reads either as *this
release does not build modification* or as *the system must prevent modification*. Both readings
are recorded; the second is chosen; the choice is visible.

### 5.4 Step 2.7b — adversarial review (new, D31)

A subagent with a clean context, dispatched with the prompt in
`speckit-qa-auto/assets/adversarial-review-prompt.md` — an asset rather than a reference file
because it is a template sent verbatim to another agent, never a document this skill's stages read
and reason from. It receives **only**:

- `ticket.md`
- `test-design.md` and both `.feature` files
- `impact.candidates[]` with evidence paths
- `run.design_depth` and its stated reason

It does **not** receive the extraction's reasoning, the conversation, or any record of what 2.1
considered and dismissed (Constraint 5).

Three fixed attack tasks:

1. **Uncovered constraints.** Which sentences in `ticket.md` state a rule the system must uphold,
   and which of those have no row in the coverage matrix? Quote the sentence.
2. **Created invariants.** What must remain true of existing behaviour once this story ships that
   was not true before? Check each flow in `impact.candidates[]` against the ticket and name the
   invariant, or state that the flow creates none.
3. **Classification by name.** Which lines were classified by the heading they sit under rather
   than by what the sentence says? Name the line and both readings.

Output follows brainstorming's reviewer format: `Approved | Issues Found`, issues as
`[Section]: [issue] — [why it matters]`, recommendations advisory and non-blocking. Its calibration
clause is carried over verbatim in intent:

> Only flag issues that would cause real problems. A missing constraint, a contradiction, or a line
> admitting two readings — those are issues. Wording improvements and stylistic preferences are
> not. Approve unless there are serious gaps.

Without calibration a reviewer returns a page of findings per run, the human learns to skim, and
the mechanism inverts into the thing it was built to prevent.

**Loop.** `Issues Found` returns to 2.1 (or 2.0, when the finding raises depth), re-runs 2.7, and
re-reviews. Bounded at **three rounds**, matching `operating-rules.md`'s existing three-strikes
rule. A fourth round would mean the extraction and the reviewer disagree persistently, which is a
question for the human at 2.8 and not for another loop. Scenarios added this way carry
`origin: adversarial-review`.

**When dispatch is unavailable** (D33): write `adversarial_review: not-run` with
`review_reason`, and surface it at the gate as its own line. It does not run inline. The reason is
Constraint 5, and `host-adaptation.md` is amended to name this exception rather than leaving its
blanket claim to cover a case where it is false.

### 5.5 Step 2.8, gate

The gate presents, always:

| Section | Content |
|---|---|
| Depth | `run.design_depth` with its stated reason — disagreeable, therefore stated |
| Coverage | AC matrix, dedup labels, element intent map, Open Questions |
| **Review** | `approved`, `issues-fixed` with each finding and its disposition, or **`not-run` with its reason, flagged** |
| **Impact** | Sweep candidates with evidence paths and provenance, `declared[]` alongside them, existing tests per candidate |

The impact section requires one of: an approved subset, an approved subset plus additions, or an
explicit statement that no feature is impacted (writing `acknowledged_empty: true`). **Without one
of those three answers the run does not continue** — this is the one place where a human's absence
of knowledge and a human's assertion of no impact must not look alike.

Sweep candidates are presented **unapproved by default**. A pre-checked list converts the human's
job from deciding to noticing, and a reviewer who is only noticing approves everything.

### 5.6 Step 2.9 — impact design

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
asserting that refresh removes candidates has a different normalized key and labels `NEW` — and the
pair is exactly what a reviewer should see, since the two describe a conditional behaviour whose
condition is new.

`@IMPACT` is a new tag, additive to the profile's `existing_tags` per `gherkin-conventions.md`.

### 5.7 What determinism survives

2.7b is a subagent producing findings, and subagent output varies run to run. Rule 5's guarantee is
narrower than that and is unaffected: **dedup labels** must be identical across runs over unchanged
inputs, and every scenario 2.7b causes to exist still passes through 2.2's normalized-key rule to
get its label. The scenario *set* was never deterministic — 2.1 is a model pass too. What D31
changes is that the set is now larger and challenged rather than smaller and unexamined.

## 6. Stage 03, Stage 04, and host-adaptation Changes

**Stage 03.** The impact file is a second input to materialization and generation. Default scope
widens from the anchor's domain to the anchor's domain plus each approved flow's domain — narrower
than `--full-suite`, wider than today. The selector entry gate runs over both files; impact
scenarios generally resolve to `source` evidence because the flow they touch already exists, the
case D29 exists to represent.

Impact scenarios inherit `run.code_state`. `pending` ends the run after Stage 02 under rule 6, no
exception added (D30).

**Stage 04.** Impact scenarios are Cucumber tests carrying the anchor's `@REQ_`, imported by the
existing CI path from `docs/qa/`. They belong to the story that created the invariant even though
they exercise another screen. The report gains two lines: approved flows with scenario counts, and
`design.adversarial_review` — a run that shipped without a review must say so in the artifact a
human reads last, not only in the gate they saw once.

**`host-adaptation.md`.** The degrade-to-inline rule gains its exception (D33), stated with the
reason rather than as a bare carve-out: for the three sweeps and the live-DOM read, what inline
costs is context isolation; for 2.7b, context isolation is the capability being bought.

## 7. What This Does Not Do

- **No automatic approval.** A sweep candidate never becomes a scenario without a person.
- **No editing of existing feature files.** The Change Setting `.feature` in the test tree is not
  touched; the new scenario lives in this story's artifact folder. Authoring in the test tree
  remains forbidden (D8).
- **No prediction of test failure.** Branch B reports which tests touch the same surface. Whether
  they break is what running them determines.
- **No second entry flag for impact.** `--impact` supplies declarations; it never becomes an
  alternative anchor.
- **No reviewer-authored artifacts.** 2.7b returns findings. Scenarios are written by 2.1 on the
  re-run, so one pass owns the `.feature` file.

## 8. Acceptance Criteria

1. A run over MOM-12194 classifies `design_depth: cross-cutting` and states both signals in
   `test-design.md`.
2. 2.7b, given only `ticket.md` and a `test-design.md` covering the eight AC rows, returns
   `Issues Found` naming the `Do not allow user/system modify...` line (attack task 1) — with no
   rule anywhere keyed to the heading `Out-Scope`.
3. 2.7b, given `impact.candidates[]` containing `RefreshWorkOrderCandidates` with its evidence
   path, names the refresh invariant (attack task 2).
4. A ticket that files an equivalent constraint under a heading named `Notes` is caught by the same
   mechanism, with no change to the skill.
5. A run whose sweep returns zero candidates still stops at the gate and cannot proceed without
   either an added flow or `acknowledged_empty: true`.
6. On a host with no subagent dispatch, `adversarial_review: not-run` is written with a reason,
   shown at the gate and in the Stage 04 report, and the review does not run inline.
7. `impact.ran: false` and `impact.candidates: []` are distinguishable in `execution-report.md`.
8. A declared flow the sweep also found records `source: both`; declarations and candidates remain
   in separate fields.
9. A `pending` run writes the impact file and ends after Stage 02 with `resume_from: 02.4`, having
   added no rule beyond rule 6.
10. `design.selector_evidence` reports `deferred` when any scenario is `deferred`, while an impact
    scenario's per-scenario field reports `source`.
11. `design_depth: trivial` still runs 2.7b and 2.8.
12. Reviewer findings, including rejected ones, remain in `test-design.md` §9 after the loop ends.
13. `tools/validate_skills.py` passes; no reference file links outside its declared `Loads:` set.

## 9. Out Of Scope (v2 Candidates)

- Backend service traceability where the API repo is not checked out
- Cross-story invariant registry — a persistent record of every invariant so later stories inherit
  the constraints earlier ones created
- Automatic detection of the inverse case: a later story that *removes* an invariant
- Ranking candidates by risk. Ranking is a verdict, and D27 says sweeps do not produce those
- A second reviewer over 2.7b's findings. One adversarial pass is the change being made; whether it
  needs its own auditor is a question for evidence from real runs, not for this design
