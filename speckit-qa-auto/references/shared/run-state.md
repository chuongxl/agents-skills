# Shared: Run-State Contract

Needs at load time: nothing. This file is a leaf — it links to no other file, and reads none.

## Overview

Stages hand off through state written to disk, never through each other's prose. This file is
that state's data shape: the one contract every stage reads and writes, so a stage can be
rewritten without touching its neighbours.

## Where It Lives

`docs/qa/<jira-key>-<slug>/execution-report.md` carries this as a fenced `yaml` block. There is
one run-state block per artifact folder, updated in place as the run progresses.

## Field Reference

```yaml
run:
  jira_key:            MOM-1234
  anchor_type:         story | epic | test
  slug:                agreement-reset-button
  artifact_dir:        docs/qa/mom-1234-agreement-reset-button
  branch:              test/mom-1234-agreement-reset-button
  isolation:           branch | worktree      # branch is the default; --parallel-worktree selects worktree
  workspace_path:      .                      # isolation: branch   -> the source checkout root
                                              # isolation: worktree -> .worktrees/test/mom-1234-agreement-reset-button
  mode:                default
  design_only:         false
  code_state:          landed | pending
  design_depth:        trivial | standard | cross-cutting   # resolved in Stage 01
  depth_raised_in_02:  false      # a 2.7b finding raised it; Stage 02 re-runs the sweep
  full_suite:          false
  stage:               00 | 01 | 02 | 03 | 04 | completed
  resume_from:         02

discovery:
  ran:                 true | false
  framework:           playwright-bdd | none
  linked_issues:       [{key, issue_type, relation, status}]
  xray_tests:          [{key, test_type, summary, requirement, objective}]
                       # objective: the description's `Test Objective:` line, or its first
                       # non-empty line, or null. See discovery.md; never a filter (rule 19)
  repo_tests:          [{feature_path, scenarios, tags}]
  orphan_features:     ["src/tests/login/login-auth.feature"]
  related_candidates:  [{key, summary, matched_by}]
                       # matched_by: link | component | epic-sibling | text | declared
                       # evidence, never a relevance verdict. See discovery.md
  related_read:        ["MOM-12500"]   # chosen by a human; governs reading, never recording (rule 20)

profile:
  # every field re-derived each run from the playbook; see repo-profile.md
  source_paths:        [".github/skills/mom-auto-testing/SKILL.md", "package.json"]
  gherkin_shape:       discovered | default
                       # default: the repo had no .feature file to learn background_style,
                       # scenario_name_style, or tag_placement from. Never cached in `answers`

baselines:
  workspace_baseline:  {path, head_sha, worktree_diff_sha256, index_diff_sha256, untracked}
  frontend_baseline:   {path, head_sha, worktree_diff_sha256, index_diff_sha256, untracked}
  frontend_edits_approved: false
  untracked_fingerprint: full | degraded   # degraded: untracked cap hit, paths and sizes only
  preexisting_dirty:                       # isolation: branch only; empty under worktree
    - {path: src/foo.ts, sha256: 9a3f...}  # sha256: null -> path absent from disk at intake
  owned_paths:                             # isolation: branch only; every write and every git add
    - docs/qa/mom-1234-agreement-reset-button
    - src/tests/features

xray:
  query:               testRequirement | linkedIssues | not-run
  cucumber_tests:      12
  manual_tests:        7
  dedup:               ran | not-run

impact:
  ran:                 true | false
  reason:              ok | no-frontend-source | entity-unresolved | submodule-uninitialized
  entities:            ["work_order_candidate"]
  declared:            ["Change Setting"]        # from --impact; human-authored
  candidates:                                    # evidence, never verdicts
    - flow:            RefreshWorkOrderCandidates
      evidence:        "om-mom-frontend/src/graphql/work-order-candidate.graphql:123"
      writes:          work_order_candidate
      existing_tests:  []                        # branch B → Stage 04 recommendation
      source:          sweep | declared | both
  approved_scenarios:  ["Refreshing candidates does not remove ..."]   # human, at 2.8
  dropped_scenarios:                             # kept with reasons, never deleted
    - name:            "Cancelling a work order ..."
      reason:          "cancel is blocked upstream for interfaced candidates"
  acknowledged_empty:  false
  by_child:                       # `epic` anchors only; absent otherwise
    MOM-12195:
      entities:            ["work_order"]
      candidates:          []
      approved_scenarios:  []
      acknowledged_empty:  true

design:
  approach_chosen:     api-first-plus-ui-smoke        # for a `test` anchor: faithful-conversion
  approach_rationale:  "the invariant is enforced server-side; one UI path covers the render"
  approach_alternatives:                              # never empty once 2.2b has run; see rule 18
    - name:            ui-heavy
      rejected_because: "every criterion through the UI triples runtime for one extra render check"
  approach_questions:
    - question:        "Is the precedence rule regression-critical this release?"
      answer:          "yes — it changed in 12194 and broke twice"
  approach_revised_in_02: false                       # a 2.7b finding routed back to 2.2b
  selector_evidence:   source | live-dom | fallback | deferred   # roll-up; see rule 16
  adversarial_review:  approved | issues-fixed | issues-open     # three values; see rule 11
  review_mode:         isolated | inline
  review_rounds:       1                                         # 0..3
  scenarios:
    - name:            Verify the Reset button is renamed
      surface:         ui | api | manual
      priority:        Highest | High | Medium | Low | Lowest   # the project's own Jira scale
      dedup:           NEW | UPDATE MOM-5678 | SKIP MOM-5678 | REVIEW MOM-5678
      source_manual_test: MOM-5678     # absent unless converted from a Manual Xray test
      origin:          extraction | adversarial-review
      selector_evidence: source | live-dom | fallback | deferred | n/a   # n/a: api, manual
      status:          pending | green | blocked
      blocked_reason:  needs-design-change
      attempts:        0
      commit:          <sha the result was produced on>
    - name:            Refreshing candidates does not remove an invoice-attached candidate
      surface:         ui
      priority:        High
      impact:          true
      impact_flow:     RefreshWorkOrderCandidates
      origin:          adversarial-review
      dedup:           NEW | REVIEW-OVERLAP MOM-5678   # never UPDATE, never SKIP
      selector_evidence: source
      status:          pending | green | blocked
      attempts:        0
```

## Rules

1. `workspace_path` is the one path every `git -C` and every file path in the run resolves
   against, and it is derived from `isolation` and `branch`, never re-spelled. Under
   `isolation: worktree` it is `<repo-root>/.worktrees/<branch>` with the branch name used
   verbatim, so a branch name containing `/` nests. Under `isolation: branch` — the default — it
   is the source checkout root, because in that mode the checkout *is* the workspace. The values
   above are instances of the rule, not the rule itself.
2. A stage reads only this file and the artifact folder. **It never reads another stage's
   reference file.**
3. A field absent from this contract does not travel between stages. Adding one means editing
   this file first.
4. `status: green` is only ever written next to the commit sha the run was produced on. A result
   with no sha is not a result.
5. **`discovery.*` holds evidence, never verdicts.** Every entry is something that was found —
   an issue key, a test key, a file path, a tag — and nothing under `discovery` is a judgement
   about whether a behaviour is already covered. Coverage labels live in `design.scenarios[].dedup`
   and are produced only by the normalized-key rule. Discovery is gathered by subagents, whose
   output varies run to run; a dedup label that varied run to run would break the guarantee that
   two runs over unchanged inputs produce an identical label set.
6. **`run.code_state: pending` forbids Stage 03.** Pending means the feature's code has not
   landed, so no selector can resolve against anything real. A run in that state ends after
   Stage 02 with `resume_from` naming the selector gate, and resumes once the code exists. Stage 03
   entered against `code_state: pending` would automate against selectors nobody could verify.
7. **`selector_evidence: deferred` is not `fallback`.** `fallback` means evidence was sought and a
   semantic strategy was accepted as a recorded risk. `deferred` means there was nothing to seek
   yet. Collapsing the two would make every pre-code run look like a risky run and drain the
   meaning out of the one value that flags real selector risk in the Stage 04 report.
   The value now lives on **each scenario**, and the top-level field is a roll-up over them
   (rule 16). The distinction this rule protects is per element — one element resolving from
   source while another needs a live DOM is the ordinary case in a landed run, and a single
   run-level value collapses it.
8. `run.anchor_type` records what the `--issue` argument resolved to. `story` covers one
   requirement; `epic` fans out to its children and produces one `.feature` per child; `test`
   anchors on an existing Xray test and takes its requirement as the `@REQ_` target. The field is
   written at intake and never re-derived downstream.

> **9. `impact.declared[]` and `impact.candidates[]` are never merged into one list.** A flow the
> human declared and the sweep also found is a cross-confirmation; a flow only one of them produced
> is a different signal. `candidates[].source` records which, and merging the lists erases all three
> distinctions.

> **10. `impact.approved_scenarios[]` names scenarios, not flows, and is written only by a human at
> the Stage 02 gate.** Scenarios exist by then, so the human decides on concrete text rather than on
> an abstract flow name. An empty list is meaningless alone — it is read together with
> `acknowledged_empty`, which is the record that a person said there is no impact. `ran: false`
> implies neither. A flow is **approved** when at least one of its scenarios is in this list; that
> is a derivation, not a stored field, and Stage 04's regression recommendation reads it.

> **11. `design.adversarial_review` has exactly three values, and none of them means "did not
> run".** A review that approved writes `approved`; one whose findings were fixed writes
> `issues-fixed`; one leaving its third round with findings still open writes `issues-open`. A
> fourth value, `not-run`, was carried by an earlier draft that let a host without subagent dispatch
> skip the step — the review now degrades to inline instead, so nothing can write it, and a value
> nothing writes is one a reader assumes means something. Failure to perform the review at all is an
> infrastructure stop, not a run-state value.

> **12. `run.design_depth` may scale the impact sweep's entity breadth, document verbosity, and how
> many approaches a gate offers. It may never scale what requirement analysis reads, never scale what
> is asked, and never disable a gate or the adversarial review.** A question not asked is a fact not
> obtained, and the pass that would authorize skipping it is the pass being audited — the same
> argument that forbids narrowing the read, in the same words. A cap on questions does not remove
> concerns; it converts them into silent assumptions (`gate-presentation.md`, rule 2). It ratchets up only. Narrowing the read is the very defect the review exists to catch,
> and the pass that would authorize the narrowing is the pass being audited. A raise inside Stage 02
> sets `depth_raised_in_02` and re-runs the sweep at the new breadth by loading
> `impact-analysis.md` — a shared leaf, loadable by whichever stage needs it.

> **13. `design.review_mode` is recorded on every run.** It exists to make the isolation preference
> measurable across real runs instead of assumed: a fresh context is less anchored on a conclusion
> it did not reach, which is a real but unquantified benefit, and what makes the review work is the
> question it asks rather than the context it holds.

> **14. Scenarios in the impact file carry `NEW` or `REVIEW-OVERLAP <TEST-key>`, never `UPDATE` and
> never `SKIP`.** `REVIEW-OVERLAP` is a distinct label, not a reuse of `REVIEW`: the dedup rule
> defines `REVIEW <TEST-key>` as *an existing test matching nothing in the new design*, and an
> impact match runs the other direction. One field carrying both directions under one name leaves
> the gate and the Stage 04 report unable to tell them apart. `UPDATE` and `SKIP` are refused
> because either would decide, with no human, that another story's Test issue now belongs to this
> one.

> **15. A candidate is satisfied by a scenario *or* by a recorded drop.** The self-review check that
> every entry in `impact.candidates[]` has a scenario reads `impact.dropped_scenarios[]` as equally
> satisfying. Without this, a gate revision that drops a candidate's only scenario re-enters
> self-review, fails the check, and fails it again on every retry — three consecutive failures being
> a turn-ending condition. The same rule is what lets a resumed run honour a drop instead of
> regenerating the scenario a human already rejected.

> **16. `design.selector_evidence` is a reporting roll-up over `surface: ui` scenarios only,** by the
> precedence `deferred` > `fallback` > `live-dom` > `source`. `api` and `manual` scenarios carry
> `n/a` and are excluded. Rule 7 says `deferred` and `fallback` are not comparable as *evidence*,
> and they are not — this precedence is a display order for one summary field, and the per-scenario
> value stays the authority. The exclusion is load-bearing: a landed run of only `api` scenarios
> would otherwise roll up to `deferred`, which a turn-ending condition stops on.

> **17. Under `isolation: branch`, `baselines.owned_paths[]` bounds every write and every `git add`
> the run makes.** That mode's whole point is that the pipeline works inside the developer's own
> checkout, so the worktree mode's guarantee — the checkout comes out untouched — is not available
> and is not claimed. What replaces it is narrower and checkable: the run writes only inside
> `owned_paths[]`, and every path in `baselines.preexisting_dirty[]` still hashes at Stage 04 to
> what it hashed at intake. **`git add -A` is forbidden in this mode** for exactly that reason — it
> stages in-flight work the pipeline did not write into a commit claiming the pipeline wrote it,
> and no later check can un-commit it. Under `isolation: worktree` neither list is populated or
> read: the tree is the pipeline's own, `add -A` is safe, and `workspace_baseline` keeps its
> whole-tree meaning.

> **18. `design.approach_chosen` exists before step 2.3 writes its first scenario, and
> `design.approach_alternatives[]` is never empty once 2.2b has run.** A scenario authored before
> the field exists is a scenario whose shape nobody approved; an empty alternatives list is a
> decision recorded as a fact. Neither is repaired by a later gate — 2.8 approves scenarios
> *against* an approach, and it cannot approve them against one that was never written down. **How
> many alternatives 2.2b presents** scales with `run.design_depth`; how many questions it asks does
> not, and whether an answer is taken does not (rule 12 draws the same line for every other check
> depth touches).

> **19. `discovery.xray_tests[].objective` orders attention and never filters a corpus.**
> `existing-tests.feature` and `existing-tests-manual.md` are written in full whatever the objectives
> say, and 2.2 matches against all of it. A test whose issue carries no description records
> `objective: null` and is still exported, still matched, still labelled. Letting the field decide
> what enters the corpus would make dedup depend on a judgement about a prose summary, and two runs
> over an unchanged Xray could then disagree — which is the determinism this contract exists to
> hold.

> **20. `discovery.related_read[]` orders attention and never filters a corpus.** Every entry of
> `discovery.related_candidates[]` stays in `execution-report.md` whatever a human picks, and the
> pick governs which candidates have their **content** read — never which are recorded, and never
> what any later step can see. This is rule 19's sentence for a second index, and it is written
> again rather than cross-referenced because the failure it prevents is the same one: a list that
> quietly became the corpus. Nothing derives a coverage judgement from a candidate's absence from
> this list; absence means *nobody chose to read it*, which is not a fact about coverage.
