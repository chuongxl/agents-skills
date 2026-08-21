# speckit-qa-auto — The Test Approach Gate and Test Case Descriptions

Date: 2026-08-21
Status: approved (design), not yet implemented
Extends [`2026-08-19-speckit-qa-auto-design.md`](2026-08-19-speckit-qa-auto-design.md) and
[`2026-08-20-speckit-qa-auto-impact-analysis-design.md`](2026-08-20-speckit-qa-auto-impact-analysis-design.md);
decision numbering continues from that document's D46.

Two changes ship together in one version because they are implemented in one pass over the same
stage files: a human gate on the test approach (§1–§6), and reading and writing the `description`
field that Jira and Xray test cases carry (§7).

**Scope.** `speckit-qa-auto/` version `0.4.0 → 0.5.0`.

| Kind | Files |
|---|---|
| New | none |
| Edited | `references/pipeline/stage-01-intake.md`, `references/pipeline/stage-02-test-design.md`; `references/shared/run-state.md`, `references/shared/operating-rules.md`, `references/shared/discovery.md`; `assets/adversarial-review-prompt.md`; `SKILL.md`; the skill's own `README.md` |
| Edited in a second skill | `jira-to-speckit/references/XRAY_API.md` — `description` added to the Xray-path field list; `jira-to-speckit/SKILL.md` — version `0.3.0 → 0.4.0` |
| Edited outside both skills | root `README.md` — **both** skills-table version badges, which `tools/validate_skills.py:292` compares against each `SKILL.md`; `test-case/speckit-qa-auto/test-cases.md` — new rows AC37–AC56, and **AC02 updated**, since it currently asserts `jira-to-speckit` reads `v0.3.0` |

No new stage, no new reference leaf, no renumbering of any existing step. One new artifact file
per run — `existing-tests-index.md` (§7.2). `gherkin-conventions.md` and the `.feature` files are
**not** touched, for the reason D60 gives.

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

### The second problem — descriptions are neither read nor written

A Jira or Xray test case carries a `description`, and teams use it as the test's own summary. A real
example, `MOM-12628`:

> **Test Objective:** Verify the Missing tab's Reason column correctly classifies each VVD's setup
> gap into one of the three defined missing-reason messages (or "N/A") based on the terminal's
> Agreement Item registration, status, and Default Vendor flag, applying the confirmed precedence
> when a terminal has multiple conflicting gaps and recalculating correctly once a gap is resolved;
> verify each Reason value's tooltip text and general tooltip display behavior; and verify a
> fully-configured terminal's resulting candidate is placed into the "Interfaced" or "Not
> Interfaced" tab depending on quantity.
>
> **Scenario:** 1: No Agreement Item registered for the terminal · 2: Agreement Item is registered
> and WFA/Approved but no Default Vendor flag · 3: Agreement Item registered, flagged Default
> Vendor, but status not yet Approved · … · 7: Only one tooltip visible at a time; tooltip hides on
> mouse-out

The pipeline reads neither end of this. **On the read side**, Sweep 2 fetches
`fields=summary,labels,issuetype` (`jira-to-speckit/references/XRAY_API.md:81`) — `description` is
not among them, so the cheapest available summary of what an existing test does is discarded, and
Stage 02 either reads every manual test's full step table or reads none of them. **On the write
side**, a designed test set produces a `.feature` file and a `test-design.md`, and nothing that
reads like the block above — so the next run over the same area finds tests this pipeline created
and has nothing to triage them by.

### What the description costs to obtain, and what triage actually saves

Both halves of the obvious framing are wrong in a way worth recording, because the design turns on
it.

**Fetching the description is free.** It is a field on the Jira issue, and the metadata call that
already runs takes a field list. Adding one name to that list adds no request.

**Triaging to avoid fetching steps saves almost nothing.** Steps do not come one test at a time:
`XRAY_API.md:108-121` specifies a single `getTests(jql: …)` GraphQL call paged at 100, chosen
precisely so keys and steps arrive together. Skipping tests would not remove a call. What triage
actually saves is **the tokens Stage 02 spends reading `existing-tests-manual.md`** — a full step
table across dozens of manual tests — and that saving is real.

The distinction matters because it fixes what the index is allowed to do. An index that saved API
calls would have to decide what gets fetched. An index that saves reading attention does not, and
must not.

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

**D58 — The description is read as a triage index, never as a filter on the dedup corpus.**
`existing-tests.feature` and `existing-tests-manual.md` are still written in full, and dedup still
matches mechanically against all of it. The index orders attention; it does not gate input. An
index that decided which tests entered the corpus would make dedup depend on a judgement about a
prose summary, and two runs over an unchanged Xray could then produce different labels — which is
the property AC07 exists to hold.

**D59 — The index is its own artifact, `existing-tests-index.md`, covering both corpora.** One
cheap file the design stage reads before descending into either export. Folding it into
`existing-tests-manual.md` would cover only half the tests and would put the cheap read behind the
expensive one; folding it into `test-design.md` would mix an input with an output.

**D60 — The designed description lives in `test-design.md` only, never in the `.feature` file.**
Three reasons, of which the first is decisive:

- A description that reproduces the ticket's format contains a line reading `Scenario:`, and in a
  `.feature` file **that is a keyword**. Gherkin would parse it as a scenario with an empty name and
  `bddgen` would compile it. `Scenarios:` is no safer — it is an alias for `Examples:`. Keeping the
  block in markdown removes the hazard rather than working around it, and lets the block match the
  ticket's format **verbatim**, which is what makes it paste-ready.
- Whether Xray's Cucumber import carries a Feature-level description onto the imported Test issue is
  **not documented in `XRAY_API.md` and is not verified here**. Writing into the `.feature` file
  would buy an unconfirmed benefit at the cost of the hazard above.
- `gherkin-conventions.md` and the `.feature` files stay untouched, so this change cannot affect
  what Stage 03 generates or what CI imports.

**The consequence is named rather than glossed:** the round trip becomes manual. Descriptions do not
reach Xray on their own, so tests this pipeline creates carry no description there, and a later
run's triage reports `no description` for exactly them — unless a human pastes the block from
`test-design.md` into the Jira field. Verifying the import mapping, and acting on it, is §11.

**D61 — The numbered list is derived from `design.scenarios[]` in file order, never authored
freehand.** It therefore cannot drift from the scenarios it claims to describe, and 2.7 can check it
by comparison rather than by judgement. A hand-written list would be a second statement of the same
fact, and the two would disagree the first time a scenario was renamed at the gate.

**D62 — Each scenario set gets its own block.** The main `.feature` set and the impact set are
described separately in `test-design.md`; the impact block's objective states the invariants, not
the feature. One merged block would claim a single objective over two sets that exist for opposite
reasons — what the story builds, and what the story must not break.

**D63 — `jira-to-speckit` gains `description` on the Xray path only.** The field list at
`XRAY_API.md:81` sits inside the Xray branch, which runs only when `xray_tests: true`. Default-mode
output is unchanged, so AC03's backward-compatibility guarantee holds without amendment and no
caller that omits `xray_tests` sees any difference.

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

## 7. Test Case Descriptions — Read and Write

### 7.1 The fetch

`jira-to-speckit/references/XRAY_API.md:81` gains one field name:

```
{JIRA_URL}/rest/api/2/issue/{issueKey}?fields=summary,labels,issuetype,description
```

Same call, same branch, no new endpoint (D63). `jira-to-speckit` bumps `0.3.0 → 0.4.0` and its root
README row follows, which is what makes `tools/validate_skills.py` pass.

### 7.2 `existing-tests-index.md` — the cheap read

Written by Stage 01 step 8, Sweep 2, into `run.artifact_dir`. One row per test, over **both**
corpora:

| Column | Value |
|---|---|
| Key | the Xray test key |
| Type | `Cucumber`, `Manual`, or `Generic` |
| Summary | the issue summary |
| Objective | the description's `Test Objective:` line; failing that its first non-empty line; failing that `no description` |

`no description` is a recorded fact, not a blank. A blank cell reads as "not looked at," and the
whole value of this file is that a reader can tell the two apart without opening the test.

**What the index may not do (D58).** It may not shorten `existing-tests.feature`, may not shorten
`existing-tests-manual.md`, and may not remove any test from what 2.2 matches against. Stage 02 reads
it first and uses it to decide which manual tests' step tables are worth reading closely — an
ordering of attention, applied to a corpus that is already complete.

`discovery.xray_tests[]` gains `objective`, carrying the same value the index row carries, so a
later stage reads it from run state rather than by re-parsing a markdown table
(`run-state.md` rule 5).

### 7.3 The written block

Step 2.5 writes, into `test-design.md`, one block per scenario set (D62), in the ticket's own format
verbatim — markdown, so `Scenario:` is inert text:

```
Test Objective: <one paragraph: what is verified, under what conditions, with which
precedence rules, and what the expected placement or outcome is>

Scenario:
1: <scenario name, exactly as it appears in the .feature file>
2: <…>
```

The numbered list is generated from `design.scenarios[]` in file order (D61). The objective is
written; the list is derived.

**2.7 gains two mechanical checks:** a block exists for every scenario set the run produced, and
each block's numbered list matches that set's scenario names in count and in order. Both fail the
way every other 2.7 check fails — fixed at source, three consecutive failures stopping the run.

**2.7b** sees the blocks inside `test-design.md`, which it already receives. An objective claiming
coverage no scenario provides is an ordinary task-1 finding; no new task is added, for the reason
D54 gives about the fourth task.

**2.8** presents the blocks for approval alongside the coverage matrix. This is human-facing prose
intended to be pasted into a Jira field, and it is the only artifact of the run that a person may
copy somewhere the pipeline cannot check.

## 8. SKILL.md and README Changes

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

The skill's own `README.md` mirrors the gate count and the version, and gains the description block
as a produced artifact. The **root `README.md`** takes `v0.5.0` on the `speckit-qa-auto` row and
`v0.4.0` on the `jira-to-speckit` row — `tools/validate_skills.py:292` compares each badge against
its skill's front matter, so a bump in one place and not the other fails the validator. Neither
row's flags column changes: this design adds no flag.

## 9. Acceptance Criteria

Deterministic, CI- or read-checkable, continuing `test-case/speckit-qa-auto/test-cases.md` from
AC36.

### 9.1 Deterministic

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

| AC50 | Description costs no extra call | Read `jira-to-speckit/references/XRAY_API.md` §4 | `description` appears in the existing `fields=` list; no new endpoint and no second request is specified |
| AC51 | The index covers both corpora | A run whose Xray query returned Cucumber and Manual tests | `existing-tests-index.md` holds a row for every test in both exports; a test whose issue has no description reads `no description`, not an empty cell |
| AC52 | Triage orders attention, never input | A run where several manual tests have no description | Every such test still appears in `existing-tests-manual.md` in full and still participates in 2.2's matching; no test is absent from a corpus because of its index row |
| AC53 | The block is not in the `.feature` | `grep -n 'Test Objective' <artifact_dir>/*.feature` | No match in any `.feature` file; the block is present in `test-design.md` |
| AC54 | The numbered list cannot drift | A run where a scenario was renamed at the 2.8 gate | The block's list matches `design.scenarios[]` in count and order after the revision; 2.7 re-ran and passed |
| AC55 | Each scenario set has its own block | A run that designed impact scenarios, and one that did not | Two blocks in the first, one in the second; the impact block's objective names invariants, not the feature |
| AC56 | `jira-to-speckit` version agrees | `python3 tools/validate_skills.py` | Exit `0`; `jira-to-speckit/SKILL.md` and its root README row both read `0.4.0`; AC02's assertion has been updated from `v0.3.0` |

### 9.2 Not a CI gate

Whether 2.2b changes outcomes is an empirical question this design does not settle by argument. It
is answered by recording, across real runs, how often the human picks something other than the
recommendation. A gate whose recommendation is accepted every time on every ticket is either a very
good recommender or a rubber stamp, and the two are told apart by the rate, not by the design. That
rate is recorded and reported; it obliges nothing on its own, and it is the input to whether the
alternatives being generated are real alternatives.

## 10. What This Does Not Do

- It does not add a fourth classification axis. `run.design_depth` is the only classifier (D47).
- It does not let a human author Gherkin at a gate. 2.2b decides the shape; 2.3 and 2.4b author,
  and everything they author passes 2.7 and 2.7b. This is the same property 2.8 already preserves.
- It does not touch Stage 01, Stage 03, or Stage 04. Stage 01 keeps its "no human gate" property;
  Stage 03 remains a no-stop zone.
- It does not skip anything. `--design-only`, `code_state: pending`, and every `design_depth` value
  run 2.2b. No flag skips a gate, and this design adds no flag.
- It does not report the approach in Stage 04's summary. Nothing downstream reads the field, and
  adding a consumer that only displays is a coupling paid for nothing.
- It does not write anything to Jira or Xray. `jira-to-speckit` stays read-only; `XRAY_API.md`'s
  list of things it does not do — "creates or edits a test, or its steps" — is unchanged, and the
  description block reaches a Jira field only if a person puts it there.
- It does not shorten either Xray export. The index is an additional file, not a replacement for
  one (D58).

## 11. Out Of Scope (v2 Candidates)

- **A library of named approaches.** The five axes in §1.2 are stated so a run can reason to a
  coherent position, not so it can pick from a catalogue. A catalogue is worth building once real
  runs show the same three or four positions recurring — and worth nothing before that.
- **Per-behaviour approach overrides.** One approach per run today. A story wanting the API layer
  for one behaviour and the UI for another says so in the rationale; whether that deserves its own
  field is a question for evidence.
- **Verifying the Cucumber-import description mapping.** Whether Xray's importer carries a
  Feature-level description onto the Test issues it creates is unverified, and `XRAY_API.md` does not
  say. It is worth one experiment against a real project. If it does carry, writing the block into
  the `.feature` file becomes viable — but only with the `Scenario:` keyword hazard solved, which is
  a separate problem D60 currently avoids rather than fixes. If it does not, the follow-up is a
  paste-ready file, and nothing else in this design changes.
- **Carrying an approved approach across resumed runs.** A `02.4` resume re-enters after the code
  lands, and the approach it was approved against may no longer fit what was built. Re-asking is the
  safe default; caching it is an optimization with a correctness cost, and it needs its own design.
