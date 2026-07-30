# Unit Test Coverage Review

Load this file only when executing the unit test coverage step.

## Goal

Run the project's test suite against the changed code and verify new code is covered at ≥ 80%.

## Step 1: Detect Test Runner and Coverage Tool

Check the project root for the following in priority order:

| Tool | Detection Signal | Coverage Command |
|------|-----------------|-----------------|
| Jest (JS/TS) | `jest.config.*`, `"jest"` in package.json | `npx jest --coverage --coverageReporters=json-summary` |
| Vitest (JS/TS) | `vitest.config.*`, `"vitest"` in package.json | `npx vitest run --coverage` |
| pytest (Python) | `pytest.ini`, `pyproject.toml [pytest]`, `setup.cfg [tool:pytest]` | `pytest --cov --cov-report=json` |
| Go test | `go.mod` present | `go test ./... -coverprofile=coverage.out && go tool cover -func=coverage.out` |
| Maven/JUnit | `pom.xml` with jacoco plugin | `mvn test jacoco:report` |
| Gradle/JUnit | `build.gradle` | `./gradlew test jacocoTestReport` |
| .NET | `*.csproj` | `dotnet test --collect:"XPlat Code Coverage"` |

If no test runner is detected, skip this step and set:
```json
{
  "unit-test-coverage": "N/A (no test runner detected)",
  "unit-test-missings": []
}
```

## Step 2: Run Tests Against Changed Files Only

1. Retrieve changed files from `git status --porcelain` and `git diff --name-only HEAD`.
2. Run coverage scoped to the changed source files/modules where possible.
3. Exclude auto-generated, migration, config, and vendor files from the coverage scope.

## Step 3: Extract Coverage Percentage for New Code

- Parse the coverage output to get the **line coverage %** for changed files.
- If the tool reports per-file, compute weighted average: `(sum of covered lines) / (sum of total lines) * 100`.
- Round to one decimal place.

## Step 4: Identify Uncovered Areas (unit-test-missings)

For each file in the changed set where coverage < 100%:

- Identify uncovered classes, methods, and line ranges.
- For each uncovered item, record:
  - `file`: relative file path
  - `class_or_method`: name of the class or method
  - `lines`: line range (e.g. `"88-120"`)
  - `reason`: brief description of what scenario is not covered

Example uncovered item:
```json
{
  "file": "src/account/service.ts",
  "class_or_method": "AccountService::createAccount",
  "lines": "88-120",
  "reason": "No test covers the case where password validation fails"
}
```

## Step 5: Apply Coverage Threshold

- If **coverage ≥ 80%**: coverage check passes — include in result but does not block `pass` status alone.
- If **coverage < 80%**: coverage check fails — status must be `failed`.

## Step 6: Output Fields

Populate in the final JSON result:

```json
"unit-test-coverage": "<percentage>%",
"unit-test-missings": [
  {
    "file": "src/account/service.ts",
    "class_or_method": "AccountService::createAccount",
    "lines": "88-120",
    "reason": "No test covers the case where password validation fails"
  }
]
```

- `unit-test-coverage`: string percent (e.g. `"85.3%"`) or `"N/A (no test runner detected)"`
- `unit-test-missings`: `[]` when coverage ≥ 80%; array of uncovered items when < 80% (may also be non-empty when coverage is adequate, to guide improvement)
