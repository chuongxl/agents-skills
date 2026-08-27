# Accessibility (A11y) Automated Testing Module

Read this module **only when accessibility scanning is required or requested** for E2E scenarios.

## 1. Integration Setup

Install `@axe-core/playwright` if accessibility assertions are part of the target test scope:
```bash
npm install -D @axe-core/playwright
```

## 2. Gherkin & Playwright Integration Pattern

### Scenario Step Definition
```gherkin
Then the page should satisfy accessibility WCAG2.1 AA standards
```

### TypeScript Step Definition Implementation
```typescript
import { expect } from '@playwright/test';
import AxeBuilder from '@axe-core/playwright';

Then('the page should satisfy accessibility WCAG2.1 AA standards', async function () {
  const accessibilityScanResults = await new AxeBuilder({ page: this.page })
    .withTags(['wcag2a', 'wcag2aa', 'wcag21a', 'wcag21aa'])
    .analyze();

  expect(accessibilityScanResults.violations).toEqual([]);
});
```

## 3. Reporting Rules
- Include accessibility violation counts (impact: critical, serious, moderate) in stage completion summaries.
