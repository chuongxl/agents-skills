# speckit-qa-auto — Gate Usability, Discovery Reach, and Test Case Priority

Date: 2026-08-22
Status: implemented in `speckit-qa-auto` 0.6.0
Extends [`2026-08-19-speckit-qa-auto-design.md`](2026-08-19-speckit-qa-auto-design.md),
[`2026-08-20-speckit-qa-auto-impact-analysis-design.md`](2026-08-20-speckit-qa-auto-impact-analysis-design.md),
and [`2026-08-21-speckit-qa-auto-approach-gate-design.md`](2026-08-21-speckit-qa-auto-approach-gate-design.md);
decision numbering continues from that document's D63, acceptance criteria from its AC56.

This design is the first one written from **evidence of the skill being used by its intended
users**. A QA team ran the pipeline on GitHub Copilot against MOM-12634 and reported five problems.
Four of them are one problem — the pipeline speaks its internal contract out loud at people who
never agreed to learn it — and the fifth is a missing field. Nothing here changes what the pipeline
decides. It changes what the pipeline says, what it looks at, and one thing it records.

**Scope.** `speckit-qa-auto/` version `0.5.0 → 0.6.0`.

| Kind | Files |
|---|---|
| New | `references/shared/gate-presentation.md` |
| Edited | `references/pipeline/stage-01-intake.md`, `references/pipeline/stage-02-test-design.md`, `references/pipeline/stage-04-finish.md`; `references/shared/run-state.md`, `references/shared/discovery.md`, `references/shared/gherkin-conventions.md`; `SKILL.md`; the skill's own `README.md` |
| Edited outside the skill | root `README.md` — the `speckit-qa-auto` version badge, which `tools/validate_skills.py` compares against `SKILL.md`; `test-case/speckit-qa-auto/test-cases.md` — new rows AC57–AC76 |

No new stage. No new human gate. No renumbering of any existing step. One new reference leaf, and
it is a leaf in the strict sense the skill uses: it links to no file and reads none.

## Problem

### The evidence

The reported session is `copilot-session-3fe507d5-7571-4e4d-9098-bf46d1e5544c.md`. Five findings,
in the users' words, with what produced each:

| # | Reported | Produced by |
|---|---|---|
| 1 | Discovery reads a lot but misses the user stories that matter | `discovery.md` Sweep 1 walks **one hop of Jira link topology** and returns `{key, issue_type, relation, status}`. A related story nobody linked is invisible; a linked one arrives as a bare key |
| 2 | Test cases carry no priority | No `priority` anywhere in the run-state contract. Rule 3: a field absent from the contract does not travel between stages |
| 3 | The clarifying step is hard to read — the words are too complicated | 2.1 and 2.2b emit one paragraph per question carrying justification, assumption, and question together |
| 4 | Why does it say "stage 2.1: `<question>`"? Users do not care about stages | The gate text names its own step, and restates the skill's own constraints back at the reader |
| 5 | What is `design_depth`? Users cannot understand it well enough to choose | 2.2b presents `run.design_depth` with its reason "so it can be disagreed with" |

Verbatim from the session, the approach gate's question field:

> `"Test approach for MOM-12634 (design_depth: cross-cutting, three alternatives as required):\n\nA — UI-heavy: … \n\nB (recommended) — …"`

with the options reduced to `"Approve Approach B (Recommended)"` and `"I want Approach A instead"`.

That single string contains findings 3, 4, and 5 at once. It names the step's own governing rule
("three alternatives as required") to a reader who has no rule book. It exposes a run-state field
name. And it serialises all three alternatives into the question, leaving the options — the place
built to carry alternatives — holding acknowledgements instead.

### The shape of the problem

Findings 3, 4, and 5 are not three wording defects. They are the absence of a **boundary between
what the pipeline holds and what a person is shown**. The skill has an unusually strong internal
contract: `run-state.md` fixes every field, dedup labels are produced mechanically so two runs agree,
`design_depth` ratchets one way, gates have turn-ending conditions. All of that is load-bearing and
none of it is wrong. But there is no file that owns the other side of the boundary, so each gate
improvises its own presentation, and improvised presentation defaults to reciting the contract.

**This skill has already imported the fix once, for the other audience.** Every reference file
carries a *Red Flags* table — "thought | reality" — which is the `brainstorming` skill's mechanism,
ported wholesale. It was applied only where the model polices itself. The human-facing half was
never ported.

### Why this did not get fixed by noticing it

Suggestion S1167, recorded 2026-08-21, proposed a presentation rule preventing redundant gate-name
prefixes at 2.2b, 2.8, and Stage 04 — finding 4, seen a day before the users hit it. It was never
implemented. A presentation convention with no owning file and no check is a convention that dies
between sessions, and this one demonstrably did. **The new leaf exists so the rule has an address**,
which is the difference between this design and doing S1167 again.

## Design

### §1 The presentation leaf

**D64 — One leaf owns everything a human reads at a gate, and every gate loads it.**
`references/shared/gate-presentation.md`. Gates today improvise, and improvisation reverts to
reciting the contract because the contract is what the stage file is made of. A single address also
means the next gate added inherits the rules instead of re-deriving them — the failure S1167
records.

**D65 — The leaf is short, and most of its rules originate outside this design.** It is not a style
guide, not a vocabulary table, and not a set of numeric thresholds. An earlier draft of this design
carried a 25-word question cap and a grep list of banned tokens; both were cut. A presentation rule
the team must maintain is a presentation rule that goes stale, and the skill already has more
surface than one person can hold. What the leaf contains:

| Rule | Provenance — recorded here, not in the leaf |
|---|---|
| One question per message. A topic needing more exploration becomes more messages | `brainstorming`, verbatim: *"Only one question per message"* |
| The count of questions is never capped. A concern not asked is written into Open Questions, never assumed silently | this design — D66 |
| Alternatives are carried by the choices, never folded into the question, and the recommendation comes first | this design — D80 |
| Sections are presented one at a time, and each asks whether it looks right before the next | `brainstorming`, verbatim: *"Ask after each section whether it looks right so far"* |
| Nothing a user reads names a stage, a run-state field, or a rule number | this design — D68 |
| An internal label with no consequence a user can act on is not presented at all | `brainstorming`'s classification-with-consequence, applied in the negative — D69 |

Plus one Red Flags table, per the skill's own convention.

**D79 — The leaf states every rule in full and names no skill outside its own folder. Provenance
lives in this spec.** The right-hand column above is design history for whoever maintains this
repository; it is not content of the shipped file. `speckit-qa-auto` installs into a QA team's
`.github/skills/` with no expectation that `superpowers` is installed beside it, so a leaf whose
rule reads *follow `brainstorming`'s question discipline* states nothing on the machine that
matters. `SKILL.md` already fixes this for the one skill this pipeline genuinely depends on —
*"Never linked to — a link outside this skill folder fails the validator and breaks the moment this
skill is installed on its own. Refer to it by name only"* — and `tools/validate_skills.py:309`
enforces it as `link escapes the skill folder`. A skill this pipeline does **not** depend on gets
less latitude than one it does, not more: `brainstorming` is not named in the leaf at all.

**Three rules are this design's own, and the spec says which.** Attributing a whole cluster to
`brainstorming` because part of it came from there is how a rule nobody can source becomes
unfalsifiable — the reviewer who wants to change it later cannot tell whether they are contradicting
an external skill or an internal preference. Rows 2, 3, and 5 are this document's; row 6 is a
derivation from `brainstorming`'s mechanism rather than a quotation of it.

**D80 — The leaf's rules are stated as capabilities, not as one host's tool schema.** An earlier
draft expressed the third rule as *use the host's question tool as its own contract specifies*,
naming the option label and description fields. Those fields are not universal: GitHub Copilot's
`ask_user`, Claude Code's `AskUserQuestion`, and OpenCode's surface differ, and a tool surface with
no structured question widget at all is possible — there the question is prose. A rule shaped like a
schema breaks exactly where there is no schema.

So the rule is stated once, at the capability level, with its degradation named:

> Alternatives are carried by the choices, never folded into the question, and the recommendation
> comes first. Where the host offers structured options, each option is one alternative — its label
> naming the choice, its description carrying the trade-off. Where it offers none, the alternatives
> are a labelled list beneath a one-sentence question. The shape degrades; the contract does not.

`host-adaptation.md` established both the pattern and the argument for subagent dispatch: the work
still happens inline when no dispatcher exists, and *"a contract that only works when a subagent is
available is a contract that breaks on the hosts that need it most."* The same sentence holds with
*question widget* substituted for *subagent*, and the QA team that reported these findings runs the
host with the least uniform tool surface of the three.

### §2 Questions are bounded by concerns, not by a budget

**D66 — `design_depth` may not scale how many questions are asked. D49's Questions column is
removed.** D49 established that ceremony scales with depth: the number of alternatives presented
*and the number of questions asked*. The questions half is now withdrawn.

The reason is a mechanism, not a preference. At `trivial`, D49's table permits *"only one that
genuinely blocks"*. A run holding four genuine concerns under that cap does not lose three concerns
— it converts them into three silent assumptions, because the run must proceed and the ticket does
not answer them. The cap manufactures exactly the failure the gate exists to prevent.

This extends a line `run-state.md` rule 12 already draws. Depth *"may never scale what requirement
analysis reads"*, for the reason that narrowing the read is the defect review exists to catch. What
is asked is subject to the same argument in the same words: a question not asked is a fact not
obtained, and the pass that would authorise skipping it is the pass being audited.

After this, `design_depth` scales three things and nothing else: the impact sweep's entity breadth,
document verbosity, and the number of approaches presented at 2.2b. Approval never scales — D49's
last column stands unchanged.

**D67 — An unasked concern is written where a human sees it.** Open Questions in `test-design.md`
already exists and already receives 2.1's non-blocking ambiguities; this makes it mandatory rather
than discretionary for any assumption the run makes in place of a question. Not asking is
permitted. Not asking silently is not.

### §3 Internal vocabulary stops at the gate

**D68 — No text a user reads names a stage, a run-state field, or a rule.** Step identifiers
(`2.1`, `2.2b`, `stage 04`), field names (`design_depth`, `dedup`, `approach_chosen`), and
self-referential clauses (*"three alternatives as required"*, *"per the depth table"*) are the
model's scaffolding. Their presence tells the reader the run is talking to itself.

**No replacement marker is introduced.** An intermediate option — renumbering into user-facing steps
("Step 2 of 4 — agreeing the test approach") — was considered and rejected by the users this design
serves: the question stands alone. The pipeline's shape is not the user's problem to track, and a
progress marker is one more thing to keep true when a step is added.

Labels that must appear in a table a human reads are written in plain words: `SKIP MOM-5678` reads
as *already covered by MOM-5678*, `REVIEW-OVERLAP MOM-5678` as *overlaps an existing test, needs a
look*. The stored value is unchanged — this is a rendering rule, and `design.scenarios[].dedup`
keeps its mechanical vocabulary so the determinism guarantee that vocabulary exists for is untouched.

**D69 — `design_depth` is never presented. The Depth section is removed from 2.2b and from 2.8.**
The previous design listed the depth announcement as covered-but-late, and D57 placed it at 2.8 so
it could be disagreed with. Both are superseded. A person cannot meaningfully disagree with a label
whose entire effect is on knobs they cannot see; asking them to costs a turn and returns a guess.
Depth is resolved at 01.7 exactly as before, and stays internal.

This is the negative half of `brainstorming`'s own mechanism, not a departure from it. That skill
announces its classification *with its consequence* — *"this looks bounded, so I'll present a short
design here rather than write a spec"* — and the consequence is the part a partner can judge. Where
a classification has no consequence a user can act on, the announcement carries nothing, and the
rule that requires it produces ceremony.

**D70 — D57's drift check survives the removal of the section that carried it.** The 2.8 Depth
section held two things: `run.design_depth`, and `design.approach_chosen` beside the surfaces
actually delivered. The second is the only place in the pipeline where a drift between the approach
approved at 2.2b and the scenarios that came out of 2.3–2.4b becomes visible. Deleting the section
wholesale would remove a check while appearing to remove a label. The section is therefore **renamed
and narrowed**, not deleted: it presents the agreed approach beside what was written, under a name
that says that, and it drops the depth line only.

While editing: the 2.8 table announces *"Present four sections"* and lists five. Corrected.

### §4 Discovery reaches past link topology

**D71 — Sweep 1 gains discovery axes beyond Jira links, and each candidate records which axis found
it.** One hop of link topology finds only what somebody took the trouble to link, which is the
mechanism behind finding 1: the sweep is not shallow, it is looking along one axis.

| `matched_by` | Source |
|---|---|
| `link` | one hop from the anchor — unchanged |
| `component` | the ticket's `components` field, already fetched by `jira-to-speckit` |
| `epic-sibling` | the other children of the anchor's parent epic |
| `text` | JQL text search on the entity or screen name taken from the ticket |
| `declared` | the `--related` flag (D73) |

`matched_by` is evidence, not a verdict — it records *why this was found*, never *whether it is
relevant*. `discovery.md`'s governing rule is untouched: sweeps find, the main run decides.

**D72 — Stage 01 does not read candidate content; a human chooses what is read, at a gate that
already stops.** Adding axes increases candidates, and reading all of them would worsen the half of
finding 1 that says *reads a lot*. Stage 01 records `{key, summary, matched_by}` only. At 2.2b — no
new gate — one multi-select question asks which of these to read, each option a story with its
`matched_by` as the description. Only chosen candidates have their content read, before scenario
design.

This is the pattern `existing-tests-index.md` established and rule 19 protects: **an index orders
attention and never filters a corpus.** Every candidate stays in `execution-report.md` whatever the
human picks; the choice governs reading, not recording, and nothing is removed from what any later
step can see.

**D73 — `--related MOM-123,MOM-456` mirrors `--impact` exactly.** A human who already knows the
related story should not have to wait for a sweep to guess it. The precedent is complete: `--impact`
declares flows, `impact.candidates[].source` records `sweep | declared | both`, and rule 9 refuses
to merge declared and swept lists because a flow both a human and a sweep produced is a stronger
signal than either alone. The same three-valued distinction applies here for the same reason.

**D74 — The text axis is bounded and reports its truncation.** Same project only, a cap, and the
count of what was cut returned alongside the entries — `discovery.md`'s existing bound, which states
that *a silent cap reads as a complete answer*. Text search is the one axis that can return the
project, so it is the one that most needs the bound the file already specifies.

### §5 Test case priority

**D75 — Priority is derived from the ticket's own Jira priority, stepped down by scenario kind.**

| Scenario | Priority |
|---|---|
| Happy path of a main acceptance criterion | the ticket's priority |
| Negative or boundary case | one level below |
| Rare edge case | two levels below |

Floored at the project's lowest level. The scale is whatever the project's Jira uses — not a scale
this skill invents, and not hardcoded. Anchoring to the ticket avoids asking the skill for a
judgement it has no standing to make (*how important is this feature in absolute terms*) while still
separating the happy path from the edge case inside one ticket, which is what inheriting the ticket
priority flat would lose.

**D76 — A scenario converted from a Manual test takes that test's priority and does not re-derive
it.** `manual-conversion.md`'s premise is that the source is an approved test that has been
executing for years, so the gate asks whether the translation is faithful, not whether the test is a
good idea. Re-deriving priority would be re-deciding something already decided, through a back door
the conversion path exists to keep shut.

**D77 — Priority travels as a scenario tag, `@Priority_<Level>`, skill-owned.** It joins `@REQ_`,
`@TEST_`, and `@IMPACT` in `gherkin-conventions.md` as skill-owned, at scenario level. The prefix is
`Priority_` rather than a bare `@High` because `existing_tags` — `@Automation`, `@Regression_Test`,
plus repo domain tags — is repo-owned and open-ended, and a bare level name is exactly the kind of
word a repo tag might already be.

Living in the `.feature` file means **no new integration**: CI already imports the file to Xray, so
the tag arrives with it, and `--tags @Priority_Highest` selects a smoke subset with no further work.
The skill still writes nothing to Xray directly — `jira-to-speckit` stays read-only.

**D78 — The skill proposes; the human decides at 2.8.** Priority becomes a column in the coverage
presentation. Because it is a section carrying a decision, it takes its own turn under D64's
one-section-at-a-time rule, with one question asking which priorities need changing. It is not a new
gate and adds no turn-ending condition — an unanswered priority question leaves the proposed values
standing, unlike the impact section, whose whole purpose is that silence and assertion must not look
alike.

## Run-State Changes

```yaml
discovery:
  related_candidates:  [{key, summary, matched_by}]   # matched_by: link | component | epic-sibling | text | declared
  related_read:        ["MOM-12500"]                  # chosen at 2.2b; governs reading, never recording

design:
  scenarios:
    - priority:        Highest | High | Medium | Low | Lowest   # the project's own scale; see D75
```

Rule edits:

- **Rule 12** gains *"and never what is asked"* alongside *"may never scale what requirement analysis reads"* (D66).
- **Rule 18**'s sentence *"the ceremony at 2.2b scales with `run.design_depth`"* is narrowed to alternatives and document verbosity, questions excluded (D66).
- **New rule 20**: `discovery.related_read[]` orders attention and never filters a corpus — the same sentence rule 19 makes for objectives, for the same reason (D72).

## Acceptance Criteria

| ID | Criterion |
|---|---|
| AC57 | `gate-presentation.md` exists, links to no file, reads none, and states its "needs at load time: nothing" header per the leaf convention |
| AC58 | Every step that asks a human a question — 2.1, 2.2b, 2.8, Stage 04, the selector gate — names `gate-presentation.md` in what it loads. A step that only stops with a quoted error, such as the Stage 01 branch gate, does not |
| AC59 | The leaf states every rule in full and names no skill outside `speckit-qa-auto/`; `brainstorming` and `superpowers` appear nowhere in the shipped skill |
| AC60 | The depth table at 2.2b has no Questions column |
| AC61 | No stage file caps the number of questions by `design_depth` |
| AC62 | `run-state.md` rule 12 names both reading and asking |
| AC63 | An assumption made in place of a question appears in Open Questions in `test-design.md` |
| AC64 | No gate presents `run.design_depth`; the Depth section is absent from 2.2b and 2.8 |
| AC65 | The 2.8 section carrying `design.approach_chosen` beside delivered surfaces still exists, under a name naming no field |
| AC66 | The 2.8 section count matches the number of sections listed |
| AC67 | Alternatives at 2.2b are carried by the choices offered, never serialised into the question text, in whatever form the host makes available |
| AC68 | `discovery.related_candidates[]` records `matched_by` for every entry, with no coverage judgement |
| AC69 | Stage 01 records key, summary and `matched_by` only — no candidate content |
| AC70 | 2.2b asks which candidates to read, and only `discovery.related_read[]` entries have content read |
| AC71 | `--related` is documented in `SKILL.md` and the skill's `README.md`, and its values reach `matched_by: declared` |
| AC72 | The text axis is bounded to the project, capped, and returns a truncation count |
| AC73 | `design.scenarios[].priority` is set for every scenario, and a converted scenario carries its Manual source's priority |
| AC74 | `@Priority_<Level>` appears in `gherkin-conventions.md` as skill-owned at scenario level, and on every scenario in every generated `.feature` |
| AC75 | The leaf's alternatives rule names its degradation for a host with no structured question tool, and every gate is presentable as prose |
| AC76 | `tools/validate_skills.py` passes; no reference file links outside the skill folder |

## What This Design Does Not Do

- It does not invoke the `brainstorming` skill from inside a gate. That skill carries its own control
  flow — classify, approaches, spec file, then `writing-plans` — and states its terminal states as
  binding. Nesting it inside a pipeline gate would put two control flows in one turn. Mechanisms are
  ported; the skill is not called.
- It does not translate gate text into another language. The reported difficulty was internal
  vocabulary, not English.
- It does not add a human gate, a stage, or a turn-ending condition.
- It does not change any dedup label, stored field value, or the determinism guarantee over them.
  D68 is a rendering rule.
- It does not make the shipped skill depend on `superpowers`. `brainstorming` shaped three of the
  leaf's six rules and is named nowhere inside `speckit-qa-auto/` (D79).
- It does not write priority to Xray directly. The tag rides the `.feature` file through the import
  CI already runs.
