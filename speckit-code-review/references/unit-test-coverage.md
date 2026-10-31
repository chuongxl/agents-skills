# Unit Test Coverage Review — `TEST-*`

Run the project's test suite against the changed code and verify new code is covered at ≥ 80%.

## Step 1 — Detect Test Runner(s)

Detect once per distinct workspace root touched by the review scope: the repo root, plus each
submodule path from the Submodule Expansion step (SKILL.md § Inputs) that has changed files. A
submodule commonly has its own manifest and test runner independent of the parent repo's.

First match wins, per workspace root:

| Tool | Detection signal | Coverage command |
|---|---|---|
| Jest | `jest.config.*`, `"jest"` in package.json | `npx jest --coverage --coverageReporters=json-summary` |
| Vitest | `vitest.config.*`, `"vitest"` in package.json | `npx vitest run --coverage` |
| pytest | `pytest.ini`, `pyproject.toml [pytest]`, `setup.cfg [tool:pytest]` | `pytest --cov --cov-report=json` |
| Go | `go.mod` | `go test ./... -coverprofile=coverage.out && go tool cover -func=coverage.out` |
| Maven | `pom.xml` with jacoco | `mvn test jacoco:report` |
| Gradle | `build.gradle` | `./gradlew test jacocoTestReport` |
| .NET | `*.csproj` | `dotnet test --collect:"XPlat Code Coverage"` |

Run each workspace root's command from inside that root (`cd <path> && <command>` for submodules).
A workspace root with no runner detected contributes `"N/A"` for its own files only — it never
blanks out coverage for files in a sibling workspace that does have a runner. If **every** touched
workspace root has no runner, set `unit-test-coverage` to `"N/A (no test runner detected)"`, emit
no `TEST-*` fixes, and skip the remaining steps (`N/A` counts as passing).

## Step 2 — Scope to Changed Files

Use the review scope resolved in SKILL.md § Procedure step 2 (already submodule-expanded — never
re-derive it here with a fresh `git status`/`git diff` call, which would only see gitlink entries
for submodule paths). Scope coverage to those source files/modules where possible, excluding
generated, migration, config, and vendor files.

## Step 3 — Compute Coverage

Parse **line coverage %** for the changed files, per workspace root's coverage report. Combine
across all touched workspace roots with one weighted average:
`sum(covered lines across all roots) / sum(total lines across all roots) * 100`. A root reporting
`"N/A"` contributes zero to both sums, it never drags the combined percentage down. Round to one
decimal place.

## Step 4 — Identify Uncovered Areas

For each changed file below 100%, record every uncovered class/method as
`{file, class_or_method, lines, reason, blocking}` in the detail file, where `reason` names the
untested scenario (e.g. `"No test covers the case where password validation fails"`).

`blocking` is set from the **overall** combined coverage computed in Step 3, never per-file:

- Overall coverage **< 80%** (the review is already failing on the Step 5 threshold): `blocking:
  true`. Emit a matching `TEST-*` fix whose `action` states the test to add; these feed into
  SKILL.md's `fixes` array and count toward `status`. Use `lines: "new"` when the test file or case
  does not exist yet.
- Overall coverage **≥ 80%**: `blocking: false`. Still record the gap in `unit-tests.json` for
  visibility and future improvement, but do **not** emit a `TEST-*` fix for it and do **not** let it
  enter SKILL.md's `fixes` array or count toward `status` — a file below 100% inside an already
  ≥ 80% overall result is not a review failure, it is backlog. Never re-derive `blocking` from a
  per-file percentage; the 80% line only ever applies to the overall figure.

## Step 5 — Threshold

- ≥ 80% — passes. Per-file gaps recorded in Step 4 stay advisory (`blocking: false`); they never
  turn this into a `failed` result.
- < 80% — `status` must be `failed`, and every gap recorded in Step 4 is blocking.

## Detail File — `unit-tests.json`

Per-method coverage gap analysis plus the raw coverage summary.

> Discard this file from context after the Unit Test Coverage review area is complete.
