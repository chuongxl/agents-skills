# CI Matrix Sharding & Allure Reporting Module

Read this module **only during Stage 04 finish when configuring CI execution workflows**.

## 1. Matrix Sharding in GitHub Actions

Run E2E test suites in parallel across matrix nodes:
```yaml
name: QA E2E Tests
on: [push, pull_request]

jobs:
  test:
    runs-on: ubuntu-latest
    strategy:
      fail-fast: false
      matrix:
        shard: [1/4, 2/4, 3/4, 4/4]
    steps:
      - uses: actions/checkout@v4
      - uses: actions/setup-node@v4
        with:
          node-version: 20
      - run: npm ci
      - run: npx playwright install --with-deps
      - run: npx playwright test --shard=${{ matrix.shard }}
      - uses: actions/upload-artifact@v4
        if: always()
        with:
          name: playwright-report-${{ strategy.job-index }}
          path: playwright-report/
```

## 2. Allure Report Integration

If Allure reporting is configured in the repository:
```bash
npx playwright test --reporter=line,allure-playwright
npx allure generate allure-results --clean -o allure-report
```
