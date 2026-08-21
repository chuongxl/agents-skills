# speckit-qa-auto test cases

Scope: one case per acceptance criterion in design spec §12
(`docs/superpowers/specs/2026-08-19-speckit-qa-auto-design.md`). AC05–AC09 carry the design's real
risk and are written as executable scenarios — concrete preconditions and commands, not prose —
because each is exactly the case a plausible-looking implementation would silently fail.

| ID | Spec §12 item | Scenario | Preconditions | Steps | Expected result |
|---|---|---|---|---|---|
| AC01 | 1 | Validator passes | `speckit-qa-auto/` and its reference files are committed | Run `python3 tools/validate_skills.py` from repo root | Exit code `0`; `speckit-qa-auto` reported with `0` error(s) and `0` warning(s) |
| AC02 | 2 | Version rows agree | `speckit-qa-auto/SKILL.md` and `jira-to-speckit/SKILL.md` carry front-matter `version:`; `README.md` lists both skills | Read the version field from `speckit-qa-auto/SKILL.md`; read the `speckit-qa-auto` row in `README.md`; read the version field from `jira-to-speckit/SKILL.md`; read the `jira-to-speckit` row in `README.md` | `README.md`'s `speckit-qa-auto` row version equals `speckit-qa-auto/SKILL.md`'s version; `README.md`'s `jira-to-speckit` row reads `v0.3.0` and `jira-to-speckit/SKILL.md`'s front-matter version reads `0.3.0` |
| AC03 | 3 | `jira-to-speckit` backward compatibility | `.env` has valid Jira credentials; a resolvable issue key | Invoke `jira-to-speckit` supplying only `issue` and `ticket_output_path`, omitting `xray_tests` entirely | Exactly one file is written (`ticket_output_path`); no `XRAY_CLIENT_ID`/`XRAY_CLIENT_SECRET` lookup occurs; no request reaches `xray.cloud.getxray.app`; the brief follows the same output template `0.2.0` produced, with no Xray section |
| AC04 | 4 | Test-case file exists | None | Run `ls test-case/speckit-qa-auto/test-cases.md` | File exists and follows the column shape of `test-case/speckit-auto/test-cases.md` (scenario / preconditions / steps / expected result) |
| AC05 | 5 | Workspace baseline regression | See "AC05 — Workspace baseline regression" below | See below | See below |
| AC06 | 6 | Frontend baseline regression | See "AC06 — Frontend baseline regression" below | See below | See below |
| AC07 | 7 | Dedup determinism | See "AC07 — Dedup determinism" below | See below | See below |
| AC08 | 8 | Blocked-scenario round trip | See "AC08 — Blocked-scenario round trip" below | See below | See below |
| AC09 | 9 | Selector evidence branch | See "AC09 — Selector evidence branch" below | See below | See below |
| AC10 | 10 | Coupling check | `speckit-qa-auto/` complete | Run `python3 tools/validate_coupling.py speckit-qa-auto` | Output `speckit-qa-auto: ok` — no file under `references/shared/` links to another reference file, and no file under `references/pipeline/` links to another stage file |
| AC11 | 11 | Dry run reaches Stage 02 human gate | Reference repository (`om-mom-e2e-playwright`) checked out; Jira and Xray credentials configured in `.env`; a real story key in that project | Run `/speckit-qa-auto --issue <real-story-key>` in default mode against the reference repo checkout, through Stage 01 and Stage 02 up to (not past) step 2.8 | The run reaches the Stage 02 human gate presenting a coverage matrix covering every acceptance criterion in the story, a selector map with every element resolved (no unresolved rows), and dedup labels (`NEW`/`UPDATE`/`SKIP`/`REVIEW`) against the story's existing Xray tests |
| AC12 | C3 | Cited leaves are declared | `speckit-qa-auto/` complete | Run `python3 tools/validate_coupling.py speckit-qa-auto` | Output `speckit-qa-auto: ok` — every shared leaf a stage file cites in backticks is named on that stage's `Loads:` line. Run against the tree as it stood before this change's stage-file edits, the same command reports four errors: `stage-03` citing `repo-profile.md` and `commit.md`, `stage-04` citing `gherkin-conventions.md` and `selector-verification.md`. That the check was demonstrated to fail is what distinguishes a passing run from an unexercised one |
| AC13 | §9.1.1 | Depth resolved before the sweep | A run has reached the end of Stage 01 | Read `execution-report.md`'s run-state block | `run.design_depth` is present and is written before `impact.*`, with the reason recorded |
| AC14 | §9.1.2 | Impact sweep is sequenced, not concurrent | `speckit-qa-auto/` complete | Read `references/shared/discovery.md`'s sweep section and `references/pipeline/stage-01-intake.md` step 9 | `discovery.md`'s no-ordering claim is scoped to the three sweeps; step 9 states it runs after step 8 and why |
| AC15 | §9.1.3 | Unrun sweep is distinguishable from an empty one | A run where the frontend source is absent | Read `impact.ran` and `impact.reason` in `execution-report.md` | `ran: false` with a reason, distinct from `ran: true` with `candidates: []` |
| AC16 | §9.1.4 | Declarations and findings stay separate | A run invoked with `--impact "Change Setting"` where the sweep also finds that flow | Read `impact.declared[]` and `impact.candidates[]` | Both fields are present; the flow appears in `candidates[]` with `source: both`; `declared[]` is not merged away |
| AC17 | §9.1.5 | A candidate is satisfied by a scenario or a drop | A gate revision drops a candidate's only scenario, then self-review re-runs | Re-run Stage 02 step 2.7 | The check passes, satisfied by the `impact.dropped_scenarios[]` entry; the run does not reach three consecutive failures |
| AC18 | §9.1.6 | Impact file forbids UPDATE and SKIP | An impact scenario whose normalized key matches an existing Cucumber test | Read the impact `.feature` and `design.scenarios[]` | The label is `REVIEW-OVERLAP <TEST-key>`; no `UPDATE` or `SKIP` appears in the impact file |
| AC19 | §9.1.7 | @REQ_ sits at Feature level in both files | A run that designed impact scenarios | Read both `.feature` files in `run.artifact_dir` | `@REQ_<STORY-KEY>` appears at Feature level in each; not at Scenario level |
| AC20 | §9.1.8 | adversarial_review has three values | `speckit-qa-auto/` complete | `grep -rn "not-run" speckit-qa-auto/references/shared/run-state.md` | The only occurrence is rule 11's explanation of why the value was removed; the enum lists three values |
| AC21 | §9.1.9 | Review rounds are bounded at three | A run whose reviewer returns findings on every round | Read `design.review_rounds` and `design.adversarial_review` | `review_rounds` never exceeds 3; leaving round 3 with findings open writes `issues-open` |
| AC22 | §9.1.10 | A depth raise re-runs the sweep | A 2.7b finding raises `run.design_depth` | Read `run.depth_raised_in_02` and `impact.entities` | `depth_raised_in_02: true`; the sweep re-ran at the wider breadth; no `sweep_breadth_stale` field exists anywhere |
| AC23 | §9.1.11 | Nothing authors Gherkin at the gate | A human names a flow nobody found, at 2.8 | Follow the run | The addition returns to 2.4b, passes 2.7 and 2.7b, and comes back to the gate; the 2.8 next-hop table is unchanged |
| AC24 | §9.1.12 | trivial depth still runs every check | A run classified `design_depth: trivial` | Read `test-design.md` and `execution-report.md` | Step 2.1 read the whole ticket; 2.7b ran; the 2.8 gate ran with its impact section |
| AC25 | §9.1.13 | The review degrades to inline | A host with no subagent-dispatch capability | Run Stage 02 through 2.7b | The review runs with the same prompt and tasks; `design.review_mode: inline` is recorded and shown at the gate |
| AC26 | §9.1.14 | A pending run writes both files and stops | A story whose code has not landed, with impact candidates found | Run Stage 01–02 | Both `.feature` files are written; the run ends after Stage 02 with `run.resume_from: 02.4` |
| AC27 | §9.1.15 | selector_evidence roll-up excludes api and manual | A landed run whose scope holds only `surface: api` scenarios | Read `design.selector_evidence` and each `design.scenarios[].selector_evidence` | Each scenario carries `n/a`; the roll-up is `n/a`, never `deferred`; Turn-Ending Condition 11 does not fire |
| AC28 | §9.1.16 | Stage 03 does not widen the run command | A run with approved impact scenarios | Read `scoped_run_cmd` as executed at 3.3 | It covers only scenarios holding `design.scenarios[]` entries; no pre-existing test of an impact flow is pulled in |
| AC29 | §9.1.17 | Findings and drops survive | A run where the reviewer raised findings and the human dropped a scenario | Read `test-design.md` §9 and `impact-candidates.md` | Every finding appears with its disposition, rejected ones included; every dropped scenario appears with its reason |
| AC30 | §9.1.18 | epic fans out fields, not folders | An `epic` anchor with two children | Read `run.artifact_dir` and `impact.by_child` | One artifact folder, named for the epic; one impact file per child inside it; per-child values under `impact.by_child` |
| AC31 | §9.1.18b | test anchor runs the fidelity set | A `test` anchor conversion run | Read the reviewer prompt as dispatched | Attack tasks 1 and 3 are replaced by the bidirectional fidelity task; an `epic` of conversions receives the same |
| AC32 | §9.1.19 | Version agrees in three places | `speckit-qa-auto/` complete | Run `python3 tools/validate_skills.py` | Exit `0`; `speckit-qa-auto` reports `0` errors; `SKILL.md`, the skill README, and the root README row all read `0.3.0` |
| AC33 | §9.1.20 | C3 was demonstrated to fail | `speckit-qa-auto/` complete | Run `python3 tools/validate_coupling.py speckit-qa-auto`; then run it against the tree before this change's stage-file edits | `ok` now; four errors before — `stage-03` citing `repo-profile.md` and `commit.md`, `stage-04` citing `gherkin-conventions.md` and `selector-verification.md` |
| AC34 | §9.1.21 | Impact scenarios carry a dedup label at creation | A run where 2.7b added an impact scenario on a loop | Read `design.scenarios[]` for entries with `origin: adversarial-review` | Each carries a `dedup` value; none is unlabelled when 2.7 re-runs |
| AC35 | §9.1.22 | The impact gate is turn-ending condition 12 | `speckit-qa-auto/` complete | Read `references/shared/operating-rules.md`'s turn-ending list | Condition 12 names the Stage 02 gate's impact section with no answer given |
| AC36 | §9.1.23 | @IMPACT is skill-owned and out of the filter | A run that designed impact scenarios | Read `profile.existing_tags` and `scoped_run_cmd` | `@IMPACT` is absent from `existing_tags` and absent from the tag filter |

## AC05 — Workspace baseline regression

Proves what a `git status --porcelain` string comparison misses: an already-dirty path keeps the
same status letter through any further edit, so a status-string check cannot see the second edit.

**Preconditions**

- The source checkout (not the pipeline's worktree) already has, before Stage 01 runs:
  - one tracked file with an uncommitted local edit — e.g. `README.md` has an unstaged one-line
    change
  - one untracked file already present and not gitignored — e.g. `scratch-notes.txt` at the repo
    root, containing one line of text
- Stage 01 step 2 has captured `workspace_baseline` (`workspace-guard.md`, "The Two Baseline
  Schemas") against the checkout in exactly this dirty state: `head_sha`, `worktree_diff_sha256`
  ( `git diff --binary HEAD` ), `index_diff_sha256` ( `git diff --cached --binary HEAD` ), and the
  `untracked` list including `scratch-notes.txt` with its size and sha256.

**Steps**

1. Run `git status --porcelain` against the source checkout. Record the two lines, e.g.
   ` M README.md` and `?? scratch-notes.txt`.
2. Without going through the pipeline, append a further line directly to `README.md` (the already-
   modified tracked file) and append a further line directly to `scratch-notes.txt` (the already-
   untracked file).
3. Run `git status --porcelain` again. Compare to step 1.
4. Run Stage 04's baseline verification (`workspace-guard.md`, "Capture Commands" + "On
   Violation"): recompute `worktree_diff_sha256` and the `untracked` fingerprint for
   `scratch-notes.txt`, and compare each to the values captured in the precondition.

**Expected result**

- Step 3's `git status --porcelain` output is byte-identical to step 1's — ` M README.md` and
  `?? scratch-notes.txt`, unchanged — proving a status-letter comparison alone would report no
  violation for either path.
- Step 4's content-addressed comparison shows `worktree_diff_sha256` differs from the captured
  baseline (the `README.md` append is caught) **and** the untracked-file entry's sha256 for
  `scratch-notes.txt` differs from the captured baseline (the untracked-file append is caught).
- Both paths are reported as violations, with baseline and current hashes named. The run stops
  before any commit. The source checkout is not reverted.

## AC06 — Frontend baseline regression

Proves that a parent repository's `git diff HEAD` sees a submodule only as a gitlink — a commit
pointer — so it cannot catch an uncommitted edit to a file inside it, which is why the frontend
gets its own baseline (§4 step 5, D12).

**Preconditions**

- The repo profile resolves `frontend_source_root` to a submodule. Stage 01 step 4
  (`git submodule update --init -- <path>` inside the worktree) succeeded, and step 5 captured
  `frontend_baseline` over `<worktree>/<frontend_source_root>`.
- `baselines.frontend_edits_approved` is `false` — no frontend edit was approved at Stage 02 step
  2.4.

**Steps**

1. Inside the frontend working tree at `<worktree>/<frontend_source_root>`, edit one existing
   tracked file — e.g. append a line to a component file — without running `git add` or `git
   commit` inside the submodule.
2. From the parent worktree, run `git -C <worktree> diff HEAD -- <frontend_source_root>` (the
   parent repo's own view of the submodule). Record the output.
3. Run Stage 04's `frontend_baseline` verification: recompute `worktree_diff_sha256` via
   `git -C <worktree>/<frontend_source_root> diff --binary HEAD`, hashed, and compare to the value
   captured at Stage 01 step 5.

**Expected result**

- Step 2's parent-repo diff shows no change to the submodule's gitlink — the pointer is unchanged
  because nothing was committed inside the submodule — demonstrating that a single, parent-scoped
  baseline would not catch this edit.
- Step 3's independent `frontend_baseline` comparison shows `worktree_diff_sha256` differs from the
  captured baseline.
- Because `baselines.frontend_edits_approved` is `false`, this difference is reported as a
  violation and stops the run before any commit — not merely surfaced for review. (Had
  `frontend_edits_approved` been `true`, the same diff would instead be reported at step 4.2 for
  human review, per `workspace-guard.md`, "On Violation".)

## AC07 — Dedup determinism

Proves the dedup rule (design spec §5.1, D13; `stage-02-test-design.md`, "Dedup Is A Rule, Not A
Judgement") is a mechanical string transform, not a per-run judgement call.

**Preconditions**

- A Jira story with a fixed list of acceptance criteria in `ticket.md`.
- `existing-tests.feature`, the Cucumber export from Xray, is identical across both runs — same
  Xray state, same file content.

**Steps**

1. Run Stage 02 steps 2.1 (requirement analysis) through 2.2 (dedup) once over the story. Record
   the ordered list of behaviour → label pairs from the resulting `test-design.md` (each label one
   of `NEW`, `UPDATE <TEST-key>`, `SKIP (covered by <TEST-key>)`, `REVIEW <TEST-key>`).
2. Discard the run's design output (do not persist it as the approved artifact).
3. Re-run Stage 02 steps 2.1–2.2 a second time, from the same `ticket.md` and the same unchanged
   `existing-tests.feature`.
4. Record the second run's ordered list of behaviour → label pairs.

**Expected result**

**Each behaviour present in both runs carries the same label**, referencing the same `TEST-key`
where applicable. This follows because the normalized scenario key (lowercase; tags, the
`Scenario:`/`Scenario Outline:` prefix, punctuation, and whitespace stripped; quoted literals and
numbers stripped) is a pure function of the scenario text and the fixed export — nothing in the
matching rule depends on model judgement or run order.

**The scenario *set* is not part of this guarantee, and an earlier version of this case wrongly
required it to be** ("the same behaviours, in the same order"). Step 2.1 is a model pass, and step
2.7b can add scenarios the first run did not produce. What rule 5 guarantees is that the labelling
of a given scenario is identical across runs, not that two runs enumerate the same scenarios. A run
that legitimately finds one more behaviour would have failed this case as written, which would have
made the first honest improvement look like a regression.

Compare labels behaviour-by-behaviour on the intersection, and record any behaviour present in only
one run rather than failing on it.

## AC08 — Blocked-scenario round trip

Proves that CI importing from `docs/qa/` (D15, §10) — rather than from the materialized test tree —
is what keeps an approved-but-unautomated scenario from being silently dropped.

**Preconditions**

- A designed `.feature` file exists in `docs/qa/<jira-key>-<slug>/`, approved at Stage 02, with at
  least two scenarios.
- Stage 03 ran to completion: one scenario is `blocked: needs-design-change` (fix attempts
  exhausted, or the only fix available would edit Gherkin), the rest are `green`.
- Stage 04 step 4.2's human review approved the blocked list, and step 4.4 wrote `@not-automated`
  into the blocked scenario in the **artifact** version of the `.feature` file.

**Steps**

1. Inspect the materialized copy at `feature_path` (the test tree, e.g. `src/tests/...`). Confirm
   which scenarios are present.
2. Inspect the artifact version at `docs/qa/<jira-key>-<slug>/<domain>-<aspect>.feature`. Confirm
   which scenarios are present and check the blocked scenario's tags.
3. Run the §10 CI import command's archive step against `docs/qa/`:
   `zip -r features.zip docs/qa -i \*.feature -x \*existing-tests.feature`, then list the zip's
   contents (`unzip -l features.zip`) instead of actually posting to Xray.
4. For contrast, build a second archive the same way but rooted at the test tree instead of
   `docs/qa/` (i.e. `zip -r features-wrong.zip <feature_path parent> -i \*.feature`), and list its
   contents.

**Expected result**

- Step 1: the test tree never contained the blocked scenario — it was omitted from the
  materialized copy at Stage 03 (§6.3) and stays omitted.
- Step 2: the artifact version still contains the blocked scenario, now tagged `@not-automated`,
  alongside the green scenarios.
- Step 3: `features.zip` (built from `docs/qa/`) contains the blocked scenario, tagged
  `@not-automated`, in the same file as the green scenarios — the CI import command in spec §10
  picks it up.
- Step 4: the contrasting archive built from the test tree does **not** contain the blocked
  scenario — demonstrating that zipping the test tree instead of `docs/qa/` would silently drop an
  approved test case from the Xray import, which is exactly what D15 exists to prevent.

## AC09 — Selector evidence branch

Proves the selector gate offers live DOM inspection rather than stopping when no frontend source is
available (Constraint 3, `selector-verification.md`'s `selector_resolution` diagram), and that
declining every evidence source is what actually stops the run — not the mere absence of frontend
source.

**Preconditions**

- Repo profile discovery ran and did **not** resolve `frontend_source_root` — no submodule, no
  repo-local frontend checkout found; the field is absent from the profile.
- Stage 02 reaches step 2.4 (the selector gate) for a scenario with `surface: ui`.
- The host exposes browser automation and the application under test is reachable (base URL, and
  credentials if required, are available), so the live-DOM branch of the gate is reachable.

**Steps — three sub-cases from the same starting point**

1. **Sub-case A (offer accepted).** With `frontend_source_root` absent, reach the gate. Per the
   `selector_resolution` diagram, "Frontend source in repo?" is "no", which routes to "Browser
   automation and app reachable?" — "yes" — which routes to "Offer live DOM inspection?". Confirm
   the run **asks** this question rather than stopping. Accept it. Confirm a subagent is dispatched
   (D20) and that only a selector map — not a full DOM dump — returns to the main run.
2. **Sub-case B (offer declined, fallback accepted).** From the same gate, decline the live-DOM
   offer but accept the semantic fallback. Inspect the resulting `test-design.md`.
3. **Sub-case C (offer declined, fallback declined).** From the same gate, decline both the
   live-DOM offer and the semantic fallback.

**Expected result**

- Sub-case A: the run never stops merely because `frontend_source_root` is absent — it reaches and
  presents the live-DOM offer. Accepting it produces a selector map for the scenario's elements;
  the main run's context does not receive a raw DOM dump.
- Sub-case B: `test-design.md` records `design.selector_evidence: fallback` (run-state field
  `design.selector_evidence`) together with the user's acknowledgement of the accepted risk; the
  selector map's rows carry a `role`/label/text strategy for each element. Stage 04's step 4.2
  report later repeats this evidence source.
- Sub-case C: the run stops — Turn-Ending Condition 7 (`operating-rules.md`) / the
  `selector_resolution` diagram's "STOP: no evidence and fallback declined" node — before Gherkin
  is approved. No selector map is fabricated to route around the stop.

## Minimum pass criteria

- AC01–AC04, AC10, and AC11 return the expected output or state exactly as described.
- AC05 and AC06 both demonstrate the same fact from opposite ends: a status-letter or parent-repo
  diff comparison alone reports no violation, while the content-addressed baseline comparison
  catches it.
- AC07 produces identical labels for every behaviour present in both runs.
- AC08 shows the test tree and `docs/qa/` diverge in exactly the documented way — the blocked
  scenario is missing from one and present, tagged, in the other — and that only `docs/qa/` is fit
  to zip for import.
- AC09 shows all three terminal outcomes of the selector gate reachable from one starting
  precondition: offer-and-accept, offer-declined-with-fallback, and offer-declined-with-stop.

## Eval cases — manual, recorded, not CI gates

E1–E4 assert that a model pass returns a specific judgement. **One passing run does not distinguish
a mechanism from luck**, so each runs **three times** and the number of runs producing the expected
finding is recorded below. A case that does not reach 3/3 is recorded at its rate, not quietly
dropped — the rate is the evidence this design asked for, and a rate nobody writes down is a design
decision made by forgetting.

Each fixture is a **complete 2.7b input set** in its own directory under
`test-case/speckit-qa-auto/fixtures/` — `ticket.md`, the `.feature` file(s), `test-design.md`,
`impact-candidates.md`, and a depth with its reason. The reviewer takes five inputs; a fixture
supplying one cannot be run. The repository had no prior `fixtures/` convention, so these establish
one.

| # | Fixture | Attack task | Expected finding | Runs |
|---|---|---|---|---|
| E1 | `fixtures/out-scope-constraint/` | 1 | Names `ticket.md`'s line "Do not allow user/system modify any candidate has attached to APM's invoice", which no scenario covers although the coverage matrix reports none uncovered | `_/3` |
| E2 | `fixtures/out-scope-constraint/` | 2 | Names the invariant `RefreshWorkOrderCandidates` creates — a candidate attached to an invoice must survive a refresh — citing `work-order-candidate.graphql:123` | `_/3` |
| E3 | `fixtures/constraint-under-notes/` | 1 | Names the line "A charge that has been included in a settlement must not be re-rated or re-assigned…", filed under a heading called `Notes` | `_/3` |
| E4 | `fixtures/constraint-under-notes/`, run once with an isolated reviewer and once inline | 1 | Both rates, recorded side by side | isolated `_/3`, inline `_/3` |

**E3 is the case that matters most.** It is what distinguishes this design from a rule keyed to the
word `Out-Scope`. Its acceptance-criteria table is deliberately complete without the constraint: if
the table were internally incomplete, a reviewer could find the gap from the table alone and the
fixture would prove nothing about reading the whole ticket. If the mechanism only fires on that one
heading, E3 fails and the design is what it was accused of being.

**E4 runs over E3's fixture, not E1's.** E1 is constructed so the finding is expected every time,
and comparing two rates at the ceiling cannot discriminate between an isolated reviewer and an
inline one — an earlier draft of this design made exactly that mistake. E3 is the harder case, so
its rate has room to differ. `design.review_mode` is otherwise an observation of host capability
with no flag to force it, and "no flag skips a gate" forecloses adding one casually; E4 is therefore
run by dispatching the reviewer both ways against the fixture directory, outside a pipeline run.

**What a rate obliges.** A case below 3/3 does not block this design. It is recorded, and it is the
input to the open question of whether one adversarial pass needs a second one auditing it — a
question the design deliberately deferred to evidence from real runs rather than settling by
argument. A rate written down with no consequence named would be the same omission with extra steps,
which is why the consequence is named here.
