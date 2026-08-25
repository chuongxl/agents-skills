# speckit-qa-auto test cases

Scope: regression contract for the modular `speckit-qa-auto` architecture introduced in version
`0.4.0`. The suite tests the installed skill as one entrypoint with a framework-neutral core,
required QA brainstorming, required QA review, machine-readable `run.json` state, resume-first
routing, and optional repository-driven automation.

These cases supersede the Stage 01-04 cases from the former prose pipeline. No case may depend on
`references/pipeline/`, `references/shared/`, `execution-report.md`, selector maps, page objects, or
framework-specific automation rules in `speckit-qa-auto`.

Status values used while recording a run: `PASS`, `FAIL`, `BLOCKED`, `NOT RUN`.

## Repository and packaging

| ID | Scenario | Preconditions | Steps | Expected result |
|---|---|---|---|---|
| PKG-01 | Skill validation passes | Repository checkout contains the complete change | Run `python3 tools/validate_skills.py` | Exit `0`; every skill reports `PASS`; `speckit-qa-auto` has 0 errors and 0 warnings |
| PKG-02 | Validator self-tests pass | None | Run `python3 tools/test_validate_skills.py` | Exit `0`; output ends with `all self-tests passed` |
| PKG-03 | Modular coupling passes | `speckit-qa-auto/SKILL.md` routes every direct reference | Run `python3 tools/validate_coupling.py speckit-qa-auto`, then `python3 tools/test_validate_coupling.py` | Both exit `0`; the first prints `speckit-qa-auto: ok`; the self-test proves unrouted modules and forbidden cross-module links are rejected by the validator |
| PKG-04 | Helper-script regression passes | Python 3 available | Run `python3 tools/test_speckit_qa_auto_scripts.py` | Exit `0`; state validation and Gherkin dedup checks pass |
| PKG-05 | Version is consistent | None | Compare `metadata.version` in `speckit-qa-auto/SKILL.md`, `**Version**` in its README, and the root README badge | All three are `0.4.0` |
| PKG-06 | Skill installs as one self-contained folder | Empty temporary agent skill directory | Copy only `speckit-qa-auto/` into the directory; inspect all relative links; invoke it with a prepared resumable artifact folder | Every relative link resolves inside the copied folder; the entrypoint loads routed core references from that folder; no deleted pipeline/shared file is requested |

## Resume-first routing

| ID | Scenario | Preconditions | Steps | Expected result |
|---|---|---|---|---|
| RES-01 | Existing issue resumes instead of restarting | Valid `docs/qa/MOM-1234/run.json` with `resume_target: automation`; invoke with `--issue MOM-1234` | Start `speckit-qa-auto` and record the first route after state validation | The existing state is selected and automation routing starts; Jira intake is not rerun merely because the issue was supplied |
| RES-02 | One implicit run resumes without an issue argument | Exactly one valid `docs/qa/**/run.json` has a resumable target | Invoke `speckit-qa-auto` without `--issue` | The run is validated and routed from `resume_target`; no issue-key question is asked |
| RES-03 | Multiple implicit runs require a choice | Two valid resumable `run.json` files exist; no `--issue` | Invoke the skill | It lists or identifies the candidate runs and asks which one to resume; it does not choose by modification time |
| RES-04 | Broken state blocks restart | A matching `run.json` has invalid JSON, an invalid enum, or an artifact path outside its run folder | Invoke with the matching issue | The skill stops with the validator error and names the invalid field/path; it does not restart intake or overwrite state |
| RES-05 | `resume_target` controls routing | Valid state has `stage: automation-complete` and `resume_target: finish` | Invoke the skill | It reads the finish route; `stage` is reported only as audit context |
| RES-06 | Completed run is read-only by default | Valid state has `resume_target: done` or `null` | Invoke without requesting a new action | Current artifacts are reported and no artifact is rewritten |
| RES-07 | New issue routes to intake | No matching run exists; invoke with `--issue MOM-1234` | Start the skill | It enters intake after the resume search; no design or automation reference is loaded first |
| RES-08 | No issue and no run stops cleanly | No `docs/qa/**/run.json`; invoke without `--issue` | Start the skill | It asks for an issue key and creates no artifact folder |
| RES-09 | Changed Jira ticket routes back to design | Valid run and `ticket.md` snapshot exist; Jira `updated` is later than the snapshot | Resume the run through its next Jira read | `ticket.md` is refreshed, the delta is recorded in `test-design.md`, and `resume_target` routes to design review before automation |
| RES-10 | Unchanged Jira ticket causes no artifact churn | Same setup as RES-09, but Jira `updated` is not later | Resume and compare artifact hashes before/after freshness checking | Existing artifacts are unchanged solely because resume ran; routing continues from stored `resume_target` |
| RES-11 | Brainstorm route is first-class | Valid state has `stage: discovered`, `resume_target: brainstorm`, and `brainstorm.status: pending` | Invoke the skill | It reads the brainstorm route; no design artifact is written before the approach is approved |
| RES-12 | Review route is first-class | Valid state has `stage: design-approved`, `resume_target: review`, approved brainstorm, and `review.status: pending` | Invoke the skill | It reads the review route; automation does not start before review passes |

## Intake and evidence

| ID | Scenario | Preconditions | Steps | Expected result |
|---|---|---|---|---|
| INT-01 | Missing Jira credentials stop intake safely | Remove one of `JIRA_URL`, `JIRA_USERNAME`, or `JIRA_API_TOKEN` from a temporary `.env` | Start a new run | Intake stops before calling Jira; output names the missing variable but prints no credential value; no valid run is claimed |
| INT-02 | Missing Xray credentials degrade to unavailable | Valid Jira credentials; omit `XRAY_CLIENT_ID` and `XRAY_CLIENT_SECRET` | Start a new run through intake | `ticket.md` is written; the run continues with `coverage.xray: unavailable`; absence of Xray is reported as a warning, not a blocker |
| INT-03 | Available Xray coverage is exported read-only | Valid Jira and Xray credentials; issue has Cucumber and Manual/Generic tests | Run intake | `xray-to-speckit` writes `existing-tests.feature` and `existing-tests-manual.md`; `coverage.xray: available`; no Xray import, mutation, or result upload occurs |
| INT-04 | Repository features join dedup inputs | Repository contains `.feature` files outside the active `docs/qa/<issue>/` folder | Run intake and inspect recorded evidence | Existing repository feature paths are retained as dedup inputs; generated files in the active run folder are excluded from the existing corpus |
| INT-05 | Declared related and impact values remain evidence | Invoke with `--related MOM-1200 --impact "invoice refresh"` | Run intake and continue to the brainstorm gate | Both hints are visible as declared evidence/assumptions; neither is silently promoted to a requirement or dedup verdict |
| INT-06 | Automation request does not change core intake | Invoke with `--automation` in a repository with an existing test stack | Run intake only | `run.json.automation.requested` is `true` and `automation.status` is `pending`; intake still produces only framework-neutral evidence and state; no test-tree file, selector, page object, or runner command is created/run |
| INT-07 | Pre-design state is valid | Intake has written `ticket.md`, but no `test-design.md` or authored `.feature` exists yet | Validate the newly created `run.json` with `validate-run-state.py` | Exit `0` for `stage: discovered`, `resume_target: brainstorm`, and `brainstorm.status: pending`; design artifacts are required only once the run reaches a stage that claims they exist |

## QA brainstorming

| ID | Scenario | Preconditions | Steps | Expected result |
|---|---|---|---|---|
| BRN-01 | Brainstorming is mandatory after intake | Intake has produced `ticket.md`, existing coverage exports when available, and valid pending state | Continue the run | The skill loads `references/brainstorm.md`, summarizes evidence, and asks for or obtains approval before routing to design |
| BRN-02 | Simple ticket still needs approach approval | Ticket has one clear acceptance criterion and no meaningful ambiguity | Continue through brainstorming | The skill presents a short recommended approach and records approval; it does not skip brainstorming because the ticket is small |
| BRN-03 | Meaningful choices are proposed explicitly | Ticket has UI, API, regression, or manual trade-offs | Run brainstorming | The skill proposes 2-3 approaches with recommendation and trade-offs, then waits for human approval before design |
| BRN-04 | Only design-changing questions are asked | Evidence has missing facts that do not affect scenario design | Run brainstorming | The skill does not ask irrelevant questions; when a question is needed, it asks one at a time |
| BRN-05 | Related issue rules remain hypotheses | `--related` issue contains a rule absent from the anchor ticket | Run brainstorming | The rule is listed as a hypothesis and becomes a confirmed assumption only if the human confirms it |
| BRN-06 | Automation context stays framework-neutral | Automation was requested and a project automation skill is available | Run brainstorming | Automation appears only as an execution trade-off; no framework-specific rule is copied into source design and no selectors, glue, waits, or framework commands enter the core design |
| BRN-07 | Approved brainstorm unlocks design | Human approves an approach | Inspect `run.json` | `brainstorm.status: approved`, non-empty `brainstorm.approach`, list fields are present, and `resume_target: design`; validator exits `0` |

## State and artifact protocol

| ID | Scenario | Preconditions | Steps | Expected result |
|---|---|---|---|---|
| STA-01 | Approved state validates | Create `docs/qa/MOM-1234/` with valid `run.json`, approved `brainstorm`, passed `review`, `ticket.md`, `test-design.md`, and one referenced `.feature` | Run `python3 speckit-qa-auto/scripts/validate-run-state.py docs/qa/MOM-1234/run.json` | Exit `0`; stdout is JSON with `"ok": true` |
| STA-02 | Invalid enum is rejected | Copy STA-01 and set `stage: stage-02`, invalid `resume_target`, or invalid coverage value | Run the validator for each mutation | Each exits `1` and stderr names the invalid field and allowed contract |
| STA-03 | Artifact path cannot escape the run folder | Copy STA-01 and point `test_design` or a feature path to another issue folder or `../` target | Run the validator | Exit `1`; stderr reports that the artifact escapes the run folder |
| STA-04 | Claimed design artifact must exist | Approved state references a missing design or feature file | Run the validator | Exit `1`; stderr names the missing path |
| STA-05 | Finish requires the core artifact set | A run reaches finish without `ticket.md`, `test-design.md`, any authored feature, or passed QA review | Run finish validation | Finish stops and reports each missing required artifact/state; it does not mark the run `finished` |

## Framework-neutral design

| ID | Scenario | Preconditions | Steps | Expected result |
|---|---|---|---|---|
| DES-01 | Design covers Jira acceptance criteria | Intake and approved brainstorm artifacts contain a story with multiple acceptance criteria and existing coverage | Run design to its human gate | `test-design.md` maps each criterion to one or more scenarios or an explicit open gap; approved approach, existing coverage, and dedup rationale are visible |
| DES-02 | Source Gherkin contains business behavior only | Design includes UI and API scenarios; automation was requested | Inspect every `.feature` under the active run folder | Files contain requirement tags, stable scenario names, context, and business outcomes; they contain no selectors, locator syntax, page/helper names, waits, runner commands, or glue code |
| DES-03 | Borrowed rules stay assumptions until confirmed | Related issue states a rule absent from the anchor ticket and brainstorming did not confirm it | Run design | The rule remains in Open Questions and any dependent scenario is marked unconfirmed with its source; no plain `Then` presents it as established fact |
| DES-04 | Human approval is required before automation | Draft design artifacts exist but no approval was given | Attempt to continue to automation | The skill presents coverage, NEW/SKIP/REVIEW decisions, risks, and automation availability; automation does not start until approval |
| DES-05 | Approval establishes review handoff state | Human approves a complete design | Inspect state after the gate | `stage: design-approved`, `resume_target: review`, `review.status: pending`, and `artifacts.feature_files`/`test_design` point to approved source artifacts |
| DES-06 | Design-only stops with a reviewed resumable handoff | Invoke a new run with `--design-only`; approve the design and pass QA review | Observe the next action and state | No automation runs in this invocation; reviewed artifacts remain in place and `resume_target: automation` allows a later resume when requested |
| DES-07 | Core completes without automation | Automation is not requested | Approve design, pass QA review, and continue | Core artifacts and report are completed; automation is recorded as not requested; no framework is installed or bootstrapped |

## QA review

| ID | Scenario | Preconditions | Steps | Expected result |
|---|---|---|---|---|
| REV-01 | Review is mandatory before automation | Approved design artifacts exist with dedup labels, but `review.status: pending` | Attempt to continue to automation | Validator rejects or routing stops; `review.md` is loaded before `automation.md` |
| REV-02 | Review receives packaged context only | Review starts after design/dedup | Inspect review prompt or transcript | It uses `ticket.md`, `run.json.brainstorm`, `test-design.md`, source `.feature` files, existing coverage, and dedup inputs; it does not rely on session history |
| REV-03 | Review is read-only | Source artifacts exist before review | Run review and compare artifact hashes before/after | Review does not mutate `test-design.md` or source `.feature` files while collecting findings |
| REV-04 | Critical and Important findings route back to design | Review finds a missing AC, unconfirmed related-story rule, or framework-specific Gherkin | Complete receiving-review handling | `review.status: changes-requested`, finding is recorded, and `resume_target: design`; automation does not run |
| REV-05 | Findings are verified before changes | Review returns a questionable finding | Handle the finding | The skill checks artifact/codebase reality, records accepted or rejected decision with evidence, and does not blindly edit |
| REV-06 | Passed review unlocks next route | Review has no blocking findings or only accepted Minor notes | Inspect `run.json` | `review.status: passed`; `resume_target: automation` when automation was requested, otherwise `finish`; validator exits `0` |
| REV-07 | Minor findings do not block finish | Review finds only wording/reporting polish | Complete review | Minor notes are recorded in `review.findings` or `review.decisions`; automation/finish can proceed if coverage correctness is intact |
| REV-08 | Review prefers isolation with inline fallback | Host supports subagents in one run and lacks them in another | Run QA review in both hosts | Capable host delegates a read-only reviewer with packaged context; fallback host runs the same checklist inline; both record the review mode and main agent handles receiving findings |

## Mechanical dedup

| ID | Scenario | Preconditions | Steps | Expected result |
|---|---|---|---|---|
| MEC-01 | Exact normalized scenario is `SKIP` | Existing and candidate scenarios differ only in case/punctuation and have the same normalized steps | Run `dedup-gherkin.py` | Candidate label is `SKIP`; result names the matched existing source |
| MEC-02 | Same title with changed steps is `REVIEW` | Existing and candidate titles normalize equally; one or more normalized steps differ | Run `dedup-gherkin.py` | Candidate label is `REVIEW`, not `SKIP` |
| MEC-03 | Unmatched scenario is `NEW` | Candidate title has no normalized title match across existing files | Run `dedup-gherkin.py` | Candidate label is `NEW` and `matched_existing` is empty |
| MEC-04 | Dedup is deterministic across multiple inputs | Two existing feature files and one candidate file are fixed | Run the same command twice with the same ordered inputs and compare JSON | Outputs are byte-identical; counts and labels do not depend on repository scan timing |
## Generic automation

| ID | Scenario | Preconditions | Steps | Expected result |
|---|---|---|---|---|
| AUT-01 | Automation uses repository conventions | Reviewed QA artifacts exist; `--automation` was requested; repository has an existing test stack | Run automation | The skill discovers local test layout/scripts and follows them; no new framework is installed or bootstrapped |
| AUT-02 | Injected project skill augments automation | A project/domain/framework automation skill is available in the session | Run automation | The skill uses that injected context together with the reviewed QA artifacts; `speckit-qa-auto` itself remains framework-neutral |
| AUT-03 | No suitable automation path is honest | Reviewed QA artifacts exist but repository has no usable test stack or required test data is absent | Run automation | Automation is recorded as `blocked` or `not-run` with reason; finish does not claim automated coverage |
| AUT-04 | Automation preserves source artifacts | Hash source `test-design.md` and `.feature` files before automation | Run automation and compare hashes | Source hashes are unchanged; generated/changed automation lives in the repository test tree or is recorded as blocked |
| AUT-05 | Automation writes protocol result | Automation runs, fails, blocks, or is skipped | Inspect `automation-result.json` | Result records actual tool/skill, generated paths, command summary, per-scenario status, blocked/not-run reasons, and source preservation |
| AUT-06 | Design defect routes back to design | Automation proves reviewed Gherkin itself must change, rather than automation code | Stop the fix loop and inspect state | The issue is reported and `resume_target` becomes `design`; automation does not silently change the source feature |

## Automation review

| ID | Scenario | Preconditions | Steps | Expected result |
|---|---|---|---|---|
| ARV-01 | Automation code changes require review | Automation creates or changes test-tree files | Attempt finish before automation review passes | Finish blocks or validator rejects a completed automation claim without `automation.review.status: passed` |
| ARV-02 | Automation review checks mapping fidelity | Automation result lists generated tests | Run automation review | Each generated scenario is checked against the reviewed source scenario for unchanged business meaning |
| ARV-03 | Automation review catches false confidence | Generated automation uses brittle waits, hidden mocks, broad command scope, or skipped assertions | Run automation review | Critical/Important finding is recorded and fixed in automation code or marked blocked before finish |
| ARV-04 | Automation review can route design defects back | Review proves the QA source design is wrong | Complete receiving-review handling | `resume_target: design`; source artifacts are fixed through design/dedup/QA-review, not patched inside automation |

## Finish, git, and reporting

| ID | Scenario | Preconditions | Steps | Expected result |
|---|---|---|---|---|
| FIN-01 | Finish summarizes the whole run | Valid core artifacts; dedup ran; automation passed, failed, blocked, was skipped, or was not requested | Run finish | Report names artifact folder, changed feature files, dedup and Xray status, automation tool/skill or reason skipped, and blocked scenarios retained in source |
| FIN-02 | Automation claim requires a result artifact | State claims automation completed but `automation-result.json` is absent | Run finish | Finish stops or downgrades the claim and reports the missing result; it does not report automation as passed |
| FIN-03 | Commit scope excludes unrelated work | Working tree contains reviewed QA outputs plus unrelated user edits | Request commit/finish | Only reviewed artifact and automation-output paths are staged; unrelated edits remain untouched; `git add -A` is not used |
| FIN-04 | PR describes the read-only Xray boundary | Validated and committed run; invoke with `--pr`; host can create a PR | Complete finish | PR summary describes generated QA/automation artifacts and states that the skill performs no Xray write/import/result upload |
| FIN-05 | Final state is resumable and valid | Finish succeeds | Inspect and validate `run.json` | State is `finished` with `resume_target: done` or `null`; validator exits `0`; a later invocation follows RES-06 |

## Minimum pass criteria

A release candidate passes when:

1. `PKG-01` through `PKG-05` pass in CI or locally.
2. All resume and state cases pass, including `RES-01`, `RES-04`, `RES-11`, `RES-12`, and `INT-07`.
3. Required brainstorming cases pass, especially `BRN-01`, `BRN-02`, and `BRN-07`.
4. Required review cases pass, especially `REV-01`, `REV-04`, and `REV-06`.
5. One core-only end-to-end run passes without automation (`DES-07`).
6. Generic automation cases pass, especially `AUT-01`, `AUT-03`, `AUT-04`, and `ARV-01`.
7. Credential cases use temporary credentials/configuration and never print secrets.

Record environment, issue/fixture, automation tool/skill, result, and evidence path for every manual run. A
blocked external dependency is `BLOCKED`, not `PASS` and not a reason to weaken the expected result.
