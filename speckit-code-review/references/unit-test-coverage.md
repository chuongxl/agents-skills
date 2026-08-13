# Unit Test Coverage Review — `TEST-*`

Run the project's test suite against the changed code and verify new code is covered at ≥ 80%.

## Step 1 — Detect Test Runner

First match wins:

| Tool | Detection signal | Coverage command |
|---|---|---|
| Jest | `jest.config.*`, `"jest"` in package.json | `npx jest --coverage --coverageReporters=json-summary` |
| Vitest | `vitest.config.*`, `"vitest"` in package.json | `npx vitest run --coverage` |
| pytest | `pytest.ini`, `pyproject.toml [pytest]`, `setup.cfg [tool:pytest]` | `pytest --cov --cov-report=json` |
| Go | `go.mod` | `go test ./... -coverprofile=coverage.out && go tool cover -func=coverage.out` |
| Maven | `pom.xml` with jacoco | `mvn test jacoco:report` |
| Gradle | `build.gradle` | `./gradlew test jacocoTestReport` |
| .NET | `*.csproj` | `dotnet test --collect:"XPlat Code Coverage"` |

No runner detected → set `unit-test-coverage` to `"N/A (no test runner detected)"`, emit no `TEST-*`
fixes, and skip the remaining steps (`N/A` counts as passing).

## Step 2 — Run Against Changed Files Only

Take changed files from `git status --porcelain` and `git diff --name-only HEAD`. Scope coverage to
those source files/modules where possible, excluding generated, migration, config, and vendor files.

## Step 3 — Compute Coverage

Parse **line coverage %** for the changed files. If reported per file, use the weighted average
`sum(covered lines) / sum(total lines) * 100`. Round to one decimal place.

## Step 4 — Identify Uncovered Areas

For each changed file below 100%, record every uncovered class/method as
`{file, class_or_method, lines, reason}` in the detail file, where `reason` names the untested
scenario (e.g. `"No test covers the case where password validation fails"`). Emit a matching `TEST-*`
fix whose `action` states the test to add; use `lines: "new"` when the test file or case
does not exist yet.

## Step 5 — Threshold

- ≥ 80% — passes; may still emit `TEST-*` fixes to guide improvement.
- < 80% — `status` must be `failed`.

## Detail File — `unit-tests.json`

Per-method coverage gap analysis plus the raw coverage summary.

> Discard this file from context after the Unit Test Coverage review area is complete.
