# Evidence-Based Flaky & Failure Diagnosis Module

Read this module **only when test execution fails in Stage 03** during inline verification.

## 1. Diagnostic Process

Never classify a failure from the stack trace alone. Gather all artifacts before forming a hypothesis:
- **Playwright Trace**: Inspect `trace.zip` or JSON report (`npx playwright show-trace test-results/.../trace.zip`).
- **Rerun History**: Execute up to 3 reruns on the same commit to test determinism.
- **Artifacts**: Inspection of screenshots, DOM snapshot at failure, and console/page error logs.

## 2. Failure Classification Taxonomy

Classify every failure into one of 5 root causes:

1. **Product Bug**: Application returned HTTP 5xx, uncaught JS exception in page context, or incorrect business logic response.
2. **Test Bug**: Stale CSS selector, missing `await`, hardcoded delay instead of web-first locator assertion.
3. **Environment Issue**: Mock service offline, API rate limit, invalid test token, or network latency timeout.
4. **Data Pollution**: Non-unique database constraint violation, dirty state left by prior execution.
5. **Flaky / Race Condition**: Non-deterministic DOM rendering delay, animation timing clash, hydration mismatch.

## 3. Remediation Protocol

- **Product Bug**: Log defect in test run report, stop test modification, notify human.
- **Test Bug / Flaky**: Refactor locator to auto-waiting `expect(locator).toBeVisible()`, avoid `page.waitForTimeout()`.
- **Data Pollution**: Refactor fixture to use dynamic `test-data-factory.md`.
