# playwright-bdd-automation test cases

Scope: regression contract for the standalone Playwright-BDD automation skill. It is a
framework-specific automation extension that can consume reviewed `speckit-qa-auto` artifacts, but
it must also work for direct Playwright-BDD test automation requests.

Status values used while recording a run: `PASS`, `FAIL`, `BLOCKED`, `NOT RUN`.

## Packaging

| ID | Scenario | Preconditions | Steps | Expected result |
|---|---|---|---|---|
| PKG-01 | Skill validation passes | Repository checkout contains the complete skill | Run `python3 tools/validate_skills.py --skill playwright-bdd-automation` | Exit `0`; skill reports `PASS` |
| PKG-02 | Root README version is consistent | None | Compare `metadata.version` in `playwright-bdd-automation/SKILL.md` with the root README row | Both are `0.1.0` |
| PKG-03 | Skill installs as one self-contained folder | Empty temporary agent skill directory | Copy only `playwright-bdd-automation/`; inspect relative links | Every relative link resolves inside the copied folder |

## Repo Profile

| ID | Scenario | Preconditions | Steps | Expected result |
|---|---|---|---|---|
| PROF-01 | Existing Playwright-BDD setup is required | Repository has no `playwright-bdd` dependency, BDD config, or existing BDD tests | Invoke the skill for automation | It stops or records `blocked/not-run`; it does not install or scaffold Playwright-BDD |
| PROF-02 | Repo conventions drive layout | Repository has existing feature, steps, fixtures, page object, and selector patterns | Build the repo profile | New files follow the profiled layout rather than a hardcoded MOM layout |
| PROF-03 | No project-specific automation skill is required | Repository uses `playwright-bdd` but has no `mom-auto-testing` or equivalent local skill | Run automation | The skill still profiles conventions and authors code using its built-in Playwright-BDD playbook |
| PROF-04 | Project docs may refine details | Repository has local docs or domain skills for backend/BFF/data conventions | Build the repo profile | Local context is used as supporting evidence, but the skill does not depend on a project-specific automation skill |

## Automation Code

| ID | Scenario | Preconditions | Steps | Expected result |
|---|---|---|---|---|
| CODE-01 | Source QA artifacts are preserved | Reviewed `docs/qa/<issue>/*.feature` and `test-design.md` exist | Run automation and compare hashes before/after | Source QA artifact hashes are unchanged |
| CODE-02 | Feature materialization preserves business meaning | Reviewed Gherkin is copied or split into the test tree | Inspect materialized features | Scenario titles, tags, and business Given/When/Then meaning remain aligned with source artifacts |
| CODE-03 | Steps are thin and awaited | Scenario requires page interactions and assertions | Inspect generated `*.steps.ts` | Steps use `createBdd(test)`, await async work, delegate UI behavior to helpers/page objects, and assert observable outcomes |
| CODE-04 | Selectors stay outside source Gherkin | UI scenario requires new selectors | Inspect source and test-tree files | Source Gherkin has no selectors; selectors live in repo-conventional selector/helper files |
| CODE-05 | Test data follows repository conventions | Scenario needs fixtures, mocks, or domain data | Inspect generated support files | Data uses existing fixture/builder/mock patterns; credentials and rotating values are not hardcoded in step definitions |
| CODE-06 | Missing environment is reported honestly | Required app, credentials, product code, or data are unavailable | Run automation | Scenario is recorded as `blocked` or `not-run` with reason; automation does not fake a pass |
| CODE-07 | Default Playwright-BDD conventions are available | Repo has minimal Playwright-BDD structure but no detailed docs | Author a new domain scenario | Feature, steps, selectors, page object, data fixtures, and mocks use the skill's built-in conventions rather than requiring another skill |

## Runner Evidence

| ID | Scenario | Preconditions | Steps | Expected result |
|---|---|---|---|---|
| RUN-01 | Runner command is narrow and meaningful | Automation code changed | Run BDD generation and the smallest relevant Playwright command | Commands run from the correct repo root and results are recorded |
| RUN-02 | Result artifact is truthful | Automation passes, fails, blocks, or is skipped | Inspect `automation-result.json` | It records tool, skill, generated/changed paths, commands, scenario statuses, blocked reasons, and source preservation |

## Quality Check

| ID | Scenario | Preconditions | Steps | Expected result |
|---|---|---|---|---|
| QC-01 | Quality check is required after automation changes | Automation generated or changed files | Attempt finish without quality check | Finish is not claimed until automation quality check passes |
| QC-02 | Quality check catches false confidence | Automation uses arbitrary waits, over-mocking, missing assertions, or broad command scope | Run the quality check | Critical/Important finding is recorded and fixed or blocked |
| QC-03 | Design defects return to QA design | Automation reveals reviewed Gherkin is wrong | Complete quality check handling | The result reports `resume_target: design`; source scenarios are not silently patched in automation |
