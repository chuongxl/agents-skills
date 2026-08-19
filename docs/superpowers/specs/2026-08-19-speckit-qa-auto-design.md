# speckit-qa-auto — QA & Automation Test Delivery Pipeline

Date: 2026-08-19
Status: approved (design), not yet implemented
Scope: new skill `speckit-qa-auto/`; additive change to `jira-to-speckit/` (version `0.2.0 → 0.3.0`); new row in `README.md`; new `test-case/speckit-qa-auto/`

## Problem

`speckit-auto` delivers *product code* from a requirement. It has no path for QA work. A tester
starting from a Jira story today does all of the following by hand, in two disconnected halves:

1. Read the story, derive test scenarios, write manual test cases into Xray.
2. Later, separately, write Playwright BDD `.feature` files that restate the same scenarios in
   Gherkin, then step definitions, page objects, and selectors.

Four defects follow.

1. **The same test is authored twice.** A manual test case in Xray and a `.feature` scenario
   express the same behaviour in two artifacts with no link between them. They drift, and nobody
   can tell which one is current.
2. **Selectors are discovered too late.** Element selectors are found while writing step
   definitions — after the scenario is already written. When a selector does not exist in the
   frontend, the work is already committed to a shape that cannot be automated.
3. **Existing Xray coverage is invisible during design.** New test cases are designed without
   reading what is already covered, so duplicates are created and stale tests are left unrevised.
4. **QA conventions are trapped in one repo.** The reference repository
   (`om-mom-e2e-playwright`) encodes its conventions in repo-local skills — `mom-auto-testing`,
   `mom-manual-testing`, `e2e-testing` — plus a `workflows/e2e-test-development.md` pipeline
   description. None of it is reusable, and the pipeline description is prose, not an executable
   skill.

## Design Decisions

Recorded here because several were user overrides of the first proposal.

| # | Decision | Rationale |
|---|---|---|
| D1 | A **new sibling skill**, not a `--track qa` flag on `speckit-auto` | QA changes must not bump the version of a dev skill that is running stably |
| D2 | **Full chain in v1**: Jira → analysis → design → Gherkin → automation → run | The Gherkin file is the single artifact for both halves, so splitting v1 would not reduce work |
| D3 | **No spec provider.** No `.speckit/integration.json`, no `github-speckit`, no `superpowers`, no constitution gate | Those select a *dev spec framework*. Automation test authoring does not use one |
| D4 | **Playwright-BDD + TypeScript is assumed.** No abstraction over other test frameworks | User directive. Removes a layer of indirection that has no second consumer today |
| D5 | Repo conventions come from a **repo-local playbook**, discovered — not from a new config file | The reference repo already has one (`mom-auto-testing`). Shared skill owns *process*; repo owns *convention* |
| D6 | **No Xray write in the pipeline.** Import runs in CI when the PR merges | User directive. Keeps `jira-to-speckit` a pure reader (see D7) |
| D7 | Xray lives **inside `jira-to-speckit`**, not in a separate skill | User directive. Feasible without breaking its contract precisely because of D6 — read-only stays read-only |
| D8 | **`docs/qa/<key>/` is the source of truth** for `.feature`; Stage 03 copies into the test tree | User directive. One authored version, one derived version, one direction of flow |
| D9 | Fix loop **may not edit Gherkin** | Without this the pipeline makes tests green by weakening them. See §6.2 |
| D10 | **No submodule leak-guard machinery.** At most one submodule (frontend), read-only by default | User directive. Ordered multi-submodule commit guarding has no second consumer here |
| D11 | The workspace guard is **content-aware**, not `git status` string comparison | User defect report. A status string cannot distinguish "already dirty" from "dirty and then modified again". See §7.1 |

## Constraint 1: The Gherkin File Is The Only Test Artifact

One `.feature` file serves three consumers:

| Consumer | Reads it as |
|---|---|
| Manual tester | The test case — Given/When/Then steps to execute by hand |
| `playwright-bdd` | The spec that `bddgen` compiles into Playwright tests |
| Xray (via CI on merge) | A Cucumber Test issue, created or updated in place |

Nothing is authored twice, and there is no translation step between formats.

## Constraint 2: Xray Speaks Gherkin In Both Directions

Verified against Xray Cloud documentation (`docs.getxray.app`, fetched 2026-08-19):

| Direction | Endpoint |
|---|---|
| Authenticate | `POST https://xray.cloud.getxray.app/api/v2/authenticate` — body `{"client_id":…,"client_secret":…}`, returns a bearer token |
| Read existing tests | `GET  https://xray.cloud.getxray.app/api/v1/export/cucumber?keys=A;B` — returns a zip of `.feature` files |
| Write tests (CI only) | `POST https://xray.cloud.getxray.app/api/v2/import/feature?projectKey=<KEY>` — multipart `file=@features.zip` |

No MCP server is required; `curl` is sufficient, which keeps the skill portable across GitHub
Copilot, Claude Code, and OpenCode — the same approach `jira-to-speckit` already takes with the
Jira REST API.

Xray binds issues to Gherkin through tags:

| Tag | Level | Meaning |
|---|---|---|
| `@REQ_<STORY-KEY>` | Feature | Links every test in the file to the story as its requirement |
| `@TEST_<TEST-KEY>` | Scenario | Binds the scenario to an existing Test issue — import **updates in place** instead of creating a duplicate |

These are **additive**. The reference repo's existing tags (`@Automation`, `@Regression_Test`,
`@MOM-3776`, domain tags) stay exactly as they are, so `--grep` filtering and the current CI
workflow are unaffected.

## Constraint 3: Selectors Must Resolve Before Gherkin Is Approved

The reference repo already proves this step
(`.github/skills/brainstorming/references/selector-verification.md`): derive the UI elements each
scenario touches, grep the frontend source for `data-testid`, and produce a selector map where
every element resolves to one of three states — existing testid, proposed testid (with the exact
file and line to add it), or semantic fallback (role/label/text).

This design promotes it from a sub-flow to a **hard gate on Stage 02**. It cannot be skipped, not
even in `--yolo`. When the frontend source is unavailable the run stops; it never guesses a
selector. Guessed selectors are the dominant cause of red tests, and every red test costs a fix
iteration.

## 1. Skill Inventory

| Skill | State | Owns |
|---|---|---|
| `speckit-qa-auto` | new, initial version `0.1.0` | The four-stage QA pipeline. Contains no repository-specific convention |
| `jira-to-speckit` | modified, `0.2.0 → 0.3.0` | Adds an optional `xray-read` mode. Remains a pure reader |

### 1.1 `jira-to-speckit` change

A new optional input `xray_tests` (default `false`). When true, after the existing brief is
produced:

1. Resolve `XRAY_CLIENT_ID` / `XRAY_CLIENT_SECRET` from `.env`. Absent → report `xray: unavailable`
   and continue; this is a warning, never a stop, because the brief is still valid without it.
2. Find Test issues linked to the story (Jira issue links / `issuetype = Test` referencing the key).
3. `GET /api/v1/export/cucumber?keys=…`, unzip, concatenate into the caller-supplied
   `xray_output_path`.

Contract change, stated precisely: the skill now writes **at most two files**, both named by the
caller — `ticket_output_path` and `xray_output_path`. It still performs no write to any remote
system, runs no pipeline stage, and performs no git operation. `speckit-auto` calls it without
`xray_tests` and observes byte-identical behaviour to `0.2.0`.

## 2. Repo Profile Discovery

`speckit-qa-auto` carries no knowledge of any repository. Stage 01 resolves a **repo profile** by
searching, stopping at the first source that answers:

1. A repo-local automation skill — `.github/skills/*auto-testing*/SKILL.md`, `.claude/skills/*/SKILL.md`
2. `AGENTS.md` / `CLAUDE.md`
3. `docs/` guideline files
4. Inference — `package.json` scripts, `playwright.config.ts`, and one existing
   `.feature` / `.steps.ts` pair read as a worked example

Fields resolved:

| Field | Example (reference repo) |
|---|---|
| `test_root` | `src/tests` |
| `feature_path` | `src/tests/{domain}/{domain}-{aspect}.feature` |
| `steps_path` | `src/tests/{domain}/{domain}-{aspect}.steps.ts` |
| `page_path` | `src/pages/{domain}/{DomainAspect}Page.ts` |
| `selectors_path` | `src/pages/{domain}/{DomainAspect}Selectors.ts` |
| `testdata_path` | `src/support/{domain}/fixtures/{name}.json` |
| `generate_cmd` | `npm run bddgen` |
| `scoped_run_cmd` | `npm run test:headed -- --grep "<tag>" --project chromium` |
| `frontend_source_root` | `om-mom-frontend` (submodule) |
| `selector_attribute` | `data-testid` |
| `existing_tags` | `@Automation`, `@Regression_Test`, `@{Domain}` |
| `xray_project_key` | `MOM` |
| `branch_prefix` | `test/` |
| `artifact_root` | `docs/qa` |

Fields that no source can answer — typically `xray_project_key` and `frontend_source_root` — are
asked **once**, then cached at `<artifact_root>/.repo-profile.json` and committed. This is a cache
of what discovery found, not a configuration file the user is expected to author; later runs
revalidate it cheaply (do the paths still exist?) and re-derive it when stale.

## 3. Artifact Layout

```
docs/qa/
├── .repo-profile.json                 discovery cache, shared by every ticket
└── <jira-key>-<slug>/
    ├── ticket.md                      Jira snapshot (from jira-to-speckit)
    ├── existing-tests.feature         exported from Xray — read-only reference
    ├── <domain>-<aspect>.feature      AUTHORED HERE — source of truth (D8)
    ├── test-design.md                 analysis, coverage matrix, selector map, plan
    └── execution-report.md            run state, per-scenario status, blockers
```

The test tree (`src/tests/…`) holds a **derived copy** of the `.feature`, materialized in Stage 03.

**Anti-drift rule.** The materialized copy may *omit* scenarios (see §6.3), but every scenario it
contains must be byte-identical to the artifact version. Subset yes; modification never. Stage 03
re-checks this on entry and overwrites the copy from the artifact when they differ.

## 4. Stage 01 — Intake

No human gate. Ends by entering Stage 02 in the same turn.

```
worktree + branch + submodules → repo profile → Jira intake → Xray existing tests
→ artifact folder init → Stage 02
```

1. **Worktree gate.** Adopted from `speckit-auto` operating rule 1: base branch priority
   `develop → main → master` (local, then remote-tracking), best-effort sync, linked worktree at
   `<repo-root>/.worktrees/<branch>`, `.worktrees/` git-ignored. Branch name
   `<branch_prefix><jira-key>-<slug>`, resolved after intake and renamed in place with
   `git branch -m` when a provisional name was used.
2. **Frontend source initialization is a hard requirement, not best-effort.** When
   `frontend_source_root` names a submodule, `git submodule update --init` for that path must
   succeed. This differs deliberately from `speckit-auto`, where the same failure only logs a
   warning: Stage 02's selector gate reads frontend source, and an empty submodule directory makes
   that gate unsatisfiable. Failure stops the run with the git error quoted.

   No general multi-submodule handling exists (D10). The pipeline expects at most one submodule,
   the frontend, and treats it as **read-only** — Stage 02's selector gate is report-only, and
   approved frontend edits go to a separate frontend branch, never to the test branch. The §7.1
   baseline is what enforces that read-only status.
3. **Repo profile** — §2.
4. **Jira intake** — `jira-to-speckit`, default mode, writing `ticket.md`.
5. **Xray existing tests** — `jira-to-speckit` with `xray_tests: true`, writing
   `existing-tests.feature`. Unavailable credentials degrade to a warning; Stage 02 then records
   every scenario as `NEW` and notes that dedup could not run.
6. **Resume.** An existing `<jira-key>-*` artifact folder is reused, never duplicated with a new
   slug. `execution-report.md` names the stage to resume from.

## 5. Stage 02 — Test Design ◀ HUMAN GATE

| Step | Action |
|---|---|
| 2.1 | **Requirement analysis** — acceptance criteria to a list of testable behaviours. A blocking ambiguity is asked **once**; a non-blocking one is recorded under Open Questions and the run continues |
| 2.2 | **Dedup against Xray** — every behaviour labelled `NEW`, `UPDATE <TEST-key>`, or `SKIP (covered by <TEST-key>)`, against `existing-tests.feature` |
| 2.3 | **Scenario design** — Gherkin, one behaviour per scenario, negative and boundary cases included. Coverage matrix: acceptance criterion → scenarios |
| 2.4 | **Selector gate (hard)** — §Constraint 3. Report-only by default. Frontend edits require explicit approval and land on a separate frontend branch inside the submodule, never mixed into the test branch |
| 2.5 | **Write `.feature`** into `docs/qa/<key>/`. Tags: `@REQ_<story>` at Feature level; `@TEST_<key>` at Scenario level only for `UPDATE` rows; plus the profile's `existing_tags` |
| 2.6 | **Write `test-design.md`** — scenarios, coverage matrix, selector map, page objects to create or modify, test data and mock plan, dedup decisions, open questions |
| 2.7 | **Self-review gate** — every acceptance criterion covered · no `TODO`/`TBD`/placeholder · every element in the selector map resolved · every behaviour carries a dedup label. Fix at source and re-verify. The same check failing 3 consecutive times stops the run |
| 2.8 | **Human gate** — present the summary, take approval or revisions, commit the artifacts, take the single start-automation confirmation, enter Stage 03 in the same turn |

`--yolo` skips 2.8 but **not** 2.4 and **not** 2.7.

## 6. Stage 03 — Automate ◀ NO-STOP ZONE

| Step | Action |
|---|---|
| 3.0 | **Materialize** — copy `.feature` from the artifact folder to `feature_path`. On any difference the artifact wins; the copy is overwritten and the overwrite is logged |
| 3.1 | **Partition** — work one scenario package at a time, in dependency order. Pass each package only the slices it needs; never forward whole prior-stage prose |
| 3.2 | **Generate** — `*.steps.ts`, `*Page.ts`, `*Selectors.ts`, fixtures and mocks, following the repo profile. Only selectors present in the approved selector map may be used |
| 3.3 | **Verify** — `generate_cmd`, then `scoped_run_cmd` filtered to the scenario's tag. Capture the output |
| 3.4 | **Fix loop** — at most 3 attempts per scenario (§6.2) |
| 3.5 | **Coverage review loop** — once scenarios are green: every acceptance criterion has at least one passing scenario · every selector map entry is used · repo conventions hold (page objects via `BasePage`, selectors centralized, no hardcoded test data in steps, no `waitForTimeout`). A failure feeds the next fix iteration, never a stop |

### 6.1 Scope of the test run

Default: only the affected domain's tests plus the new scenarios. A full-suite run is the explicit
`--full-suite` flag, because a full suite is slow and is rarely what a single ticket needs.

### 6.2 Fix loop rules

**Permitted edits:** selectors, waits and synchronization, page objects, step definitions, test
data, mocks.

**Forbidden, without exception:**

- editing any `.feature` file — the artifact version or the materialized copy
- weakening, removing, or commenting out an assertion
- adding `waitForTimeout`
- adding `.skip`, `@fixme`, or any tag whose effect is to stop the scenario running
- narrowing `scoped_run_cmd` so a red scenario is no longer selected

These exist because a fix loop with write access to its own success criteria will make every test
pass and prove nothing.

### 6.3 Blocked scenarios

When passing a scenario would require changing its Gherkin, the scenario is not fixed. It is
marked `blocked: needs-design-change` in `execution-report.md`, **omitted from the materialized
copy** (so the committed test tree stays green), and reported at Stage 04. The run continues with
the remaining scenarios. Changing the Gherkin requires returning to the Stage 02 human gate.

### 6.4 Infrastructure failure is not test failure

Browser binaries missing, environment variables absent, the application under test unreachable, a
`bddgen` compilation error caused by the repo rather than by generated code: these stop the run
immediately with the error quoted, and **do not consume a fix attempt**. Spending three iterations
"fixing" a correct test because the environment is broken is the failure mode this rule prevents.

### 6.5 Circuit breaker

Abort Stage 03 when the identical failure repeats 5 consecutive iterations with no file change in
between, or when a git or filesystem error prevents writing. A differing failure, or one followed
by any file edit, does not count. Report the stuck state and stop.

## 7. Stage 04 — Finish ◀ HUMAN GATE

1. Update `execution-report.md`: scenarios passing, scenarios blocked with reasons, run output
   summary, coverage matrix status.
2. **Human review** — files created and changed, test results, blocked scenarios with reasons,
   proposed `data-testid` additions for the frontend (each with file and line), open questions.
3. **Verify the workspace baseline (§7.1).** A violation stops the run before any commit.
4. Commit and push. Adopted from `speckit-auto`'s commit procedure: every commit is conditional on
   `git status --porcelain` in the worktree — an already-clean tree is a success path, not a
   failure — then `git pull --rebase origin <branch>` and push.

   Note: `speckit-auto/references/shared/commit.md` as of `5b73276` contains **no** workspace or
   submodule guard. The mechanism in §7.1 is new to this design, not inherited.
5. Push the branch and print a ready-to-use PR title and body. **Do not open the PR** unless
   `--pr` is passed.
6. Mark the artifact `completed` and make the follow-up commit for that status change.

### 7.1 Workspace Baseline (Content-Aware)

All pipeline work happens inside `<repo-root>/.worktrees/<branch>`. The source checkout is the
developer's own working tree and must come out of the run untouched. Two layers enforce that.

**Prevention (primary).** Every git command carries an explicit `git -C <worktree_path>`, and every
file path is resolved against `worktree_path`. A bare `git` invocation or a repo-relative path that
resolves against the process working directory is a defect, not a style preference.

**Detection (backstop).** Prevention fails silently when it fails at all, so Stage 01 records a
baseline of the source checkout and Stage 04 re-computes it before committing.

`git status --porcelain` is **not** sufficient for this. Its output is a status letter plus a path,
so it is blind to any change that does not alter the letter:

| Baseline state | Agent action | `status` output | Detected? |
|---|---|---|---|
| `src/foo.ts` already modified | adds 50 more lines | unchanged: ` M src/foo.ts` | **no** |
| `notes.txt` already untracked | rewrites its contents | unchanged: `?? notes.txt` | **no** |
| `src/bar.ts` clean | modifies it | `""` → ` M src/bar.ts` | yes |
| no such file | creates it | `""` → `?? new.txt` | yes |

The blind spot is exactly the case worth protecting: paths that were already dirty before the run,
which is the normal state of a developer's checkout mid-task.

The baseline is therefore content-addressed. Field name `workspace_baseline` — not
`*_baseline_status`, since it no longer holds status strings:

```
workspace_baseline:
  path:                  <source checkout root>
  head_sha:              git -C <path> rev-parse HEAD
  worktree_diff_sha256:  sha256( git -C <path> diff --binary HEAD )
  index_diff_sha256:     sha256( git -C <path> diff --cached --binary HEAD )
  untracked:             [ {path, size, sha256}, ... ]   # git ls-files --others --exclude-standard
```

- `diff --binary HEAD` captures every tracked change, staged or not, byte for byte.
- `diff --cached --binary HEAD` is kept separately so a pure staging change — `git add` with no
  content edit, which leaves `diff HEAD` identical — is still detected.
- `untracked` needs its own fingerprint because no `git diff` form covers untracked files.
  `--exclude-standard` keeps ignored trees such as `node_modules/` out. If the untracked set
  exceeds 2000 files or 50 MB, fingerprint paths and sizes only, and record
  `untracked_fingerprint: degraded` in `execution-report.md` — a stated limitation beats an
  unbounded hashing pass.

Any difference at Stage 04 stops the run before committing and reports the differing paths, with
the baseline and current hashes. The run does not attempt to revert the source checkout: undoing a
developer's working tree without asking is worse than the leak.

**Known limits, stated rather than hidden.** Gitignored files — `.env` above all — appear in
neither `git diff` nor `ls-files --others --exclude-standard`, so a write to one is not detected.
Detection also runs only at Stage 04, so it reports a leak rather than preventing it; prevention is
the `-C <worktree_path>` discipline above.

## 8. Turn-Ending Conditions

Exhaustive. Any other reason to stop is invalid.

1. A concrete tool or runtime error, with the error text quoted
2. A genuinely missing required input, after one ask
3. The Stage 02 human gate (default mode)
4. Stage 02 self-review failing the same check 3 consecutive times
5. Stage 01 frontend-source initialization failure, or Stage 02 selector gate with no frontend
   source
6. Stage 03 infrastructure failure (§6.4) or circuit breaker (§6.5)
7. A Stage 04 workspace baseline violation (§7.1)
8. Stage 04 (default mode), or pipeline completion in `--yolo`

## 9. Invocation, Modes And Flags

**Required input: a Jira issue key or browse URL.** Free-text requirements are not supported in
v1. Three parts of the pipeline depend on the Jira key and have no defined behaviour without it:
the artifact folder identity `<jira-key>-<slug>`, the `@REQ_<STORY-KEY>` tag that binds the feature
file to its requirement in Xray, and the Stage 02 dedup pass against tests already linked to the
story.

```
/speckit-qa-auto --issue <jira-url-or-key> [--yolo] [--full-suite] [--pr]
```

| Flag | Effect |
|---|---|
| *(none)* | Default: human gates at Stage 02 and Stage 04 |
| `--yolo` | Skips the Stage 02 approval and Stage 04 review. Does **not** skip the selector gate or the self-review gate |
| `--full-suite` | Stage 03 runs the whole suite instead of the affected domain |
| `--pr` | Stage 04 opens the pull request after pushing |

## 10. Handoff To CI (Out Of Scope For The Skill)

The skill never writes to Xray. Because every `.feature` carries `@REQ_` and `@TEST_` tags, a merge
job needs only:

```bash
token=$(curl -s -H "Content-Type: application/json" -X POST \
  --data "{\"client_id\":\"$XRAY_CLIENT_ID\",\"client_secret\":\"$XRAY_CLIENT_SECRET\"}" \
  https://xray.cloud.getxray.app/api/v2/authenticate | tr -d '"')

zip -r features.zip src/tests -i \*.feature
curl -H "Authorization: Bearer $token" -F "file=@features.zip" \
  "https://xray.cloud.getxray.app/api/v2/import/feature?projectKey=$XRAY_PROJECT_KEY"
```

Scenarios tagged `@TEST_<key>` update in place; untagged scenarios create new Test issues. Writing
the resulting keys back into the `.feature` files closes the loop and is a v2 concern.

## 11. Skill File Layout

```
speckit-qa-auto/
├── SKILL.md                                    entry dispatch + stage router
├── README.md                                   human documentation (500–1000 words)
└── references/
    ├── pipeline/
    │   ├── stage-01-intake.md
    │   ├── stage-02-test-design.md
    │   ├── stage-03-automate.md
    │   └── stage-04-finish.md
    └── shared/
        ├── operating-rules.md                  §6.2, §6.4, §6.5, §8
        ├── repo-profile.md                     §2 discovery procedure and field list
        ├── selector-verification.md            Constraint 3, generalized
        ├── gherkin-conventions.md              tags, scenario granularity, Xray binding
        ├── workspace-guard.md                  §7.1 baseline capture and verification
        ├── host-adaptation.md                  adopted from speckit-auto
        └── commit.md                           adopted from speckit-auto (conditional commit,
                                                pull-rebase, push); no guard of its own
```

Each file is loaded on demand; `SKILL.md` stays a small router, matching `speckit-auto`'s shape.
Per `SKILL_SPEC.md`, no link may point outside the skill folder — files adopted from `speckit-auto`
are **copied**, and other skills are referred to by name in prose.

## 12. Acceptance Criteria

1. `python3 tools/validate_skills.py` exits `0`.
2. `README.md` carries a `speckit-qa-auto` row whose version matches its `SKILL.md`, and the
   `jira-to-speckit` row reads `v0.3.0`.
3. `speckit-auto` invoking `jira-to-speckit` without `xray_tests` shows no behavioural change:
   no Xray endpoint is contacted, exactly one file is written (the ticket snapshot), and the brief
   follows the same output template as `0.2.0`.
4. `test-case/speckit-qa-auto/test-cases.md` exists, following the shape of
   `test-case/speckit-auto/test-cases.md`.
5. Workspace baseline regression test: with the source checkout holding one already-modified
   tracked file and one already-present untracked file, append to each, then run Stage 04
   verification. Both must be reported as violations. This is the case `git status` comparison
   misses.
6. A dry run against a real Jira story in the reference repository reaches the Stage 02 human gate
   with: a coverage matrix over every acceptance criterion, a selector map in which every element
   is resolved, and dedup labels against existing Xray tests.

## 13. Out Of Scope (v2 Candidates)

- Importing tests or test-run results into Xray from the skill (§10 hands this to CI).
- Writing Xray-assigned Test keys back into `.feature` files after import.
- Test frameworks other than Playwright-BDD + TypeScript (D4).
- Creating test executions or test plans in Xray.
- Modifying CI workflow files.
- General multi-submodule support and ordered submodule commits (D10).
- Detecting writes to gitignored files in the source checkout (§7.1 known limits).
- Reverting a leaked change in the source checkout — the run reports, never rewrites.
- Automatically applying proposed `data-testid` attributes to frontend source without approval.
