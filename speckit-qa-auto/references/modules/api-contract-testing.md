# API Contract Validation Module

Read this module **only when validating API payloads or backend contracts** in test steps.

## 1. Hybrid E2E / API Testing Pattern

Use Playwright's `request` context alongside `page` to validate backend state directly:
```typescript
import { expect } from '@playwright/test';

// Verify API contract before/after UI action
const response = await request.get('/api/v1/users/me');
expect(response.status()).toBe(200);

const body = await response.json();
expect(body).toMatchObject({
  id: expect.any(String),
  email: expect.stringMatching(/^[^\s@]+@[^\s@]+\.[^\s@]+$/),
  roles: expect.arrayContaining(['user']),
});
```

## 2. Schema Validation with Zod or Ajv

If OpenAPI or JSON schema files exist in the project (`/schemas/`), validate response bodies:
```typescript
import { z } from 'zod';

const UserSchema = z.object({
  id: z.string().uuid(),
  email: z.string().email(),
  active: z.boolean(),
});

UserSchema.parse(await response.json()); // Throws if contract is broken
```
