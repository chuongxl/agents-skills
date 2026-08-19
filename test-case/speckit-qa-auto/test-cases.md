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

The two label sets are identical: the same behaviours, in the same order, each carrying the same
label and the same referenced `TEST-key` where applicable. This follows because the normalized
scenario key (lowercase; tags, the `Scenario:`/`Scenario Outline:` prefix, punctuation, and
whitespace stripped; quoted literals and numbers stripped) is a pure function of the scenario text
and the fixed export — nothing in the matching rule depends on model judgement or run order.

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
- AC07 produces byte-for-byte identical label sets across two independent runs.
- AC08 shows the test tree and `docs/qa/` diverge in exactly the documented way — the blocked
  scenario is missing from one and present, tagged, in the other — and that only `docs/qa/` is fit
  to zip for import.
- AC09 shows all three terminal outcomes of the selector gate reachable from one starting
  precondition: offer-and-accept, offer-declined-with-fallback, and offer-declined-with-stop.
