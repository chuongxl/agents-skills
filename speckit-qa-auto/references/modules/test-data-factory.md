# Dynamic Test Data & Factory Module

Read this module **only when generating step definitions requiring dynamic fixtures**.

## 1. Core Rule: No Hardcoded Test Data

Never hardcode static emails, usernames, or database IDs in test definitions. Hardcoded data causes test pollution and prevents parallel execution.

## 2. Data Factory Pattern (`@faker-js/faker`)

### Setup
```bash
npm install -D @faker-js/faker
```

### Example Fixture Factory
```typescript
import { faker } from '@faker-js/faker';

export function createTestUser() {
  return {
    email: faker.internet.email({ provider: 'qa-test.internal' }),
    username: faker.internet.username(),
    fullName: faker.person.fullName(),
    phone: faker.phone.number(),
  };
}
```

## 3. Cleanup & Isolation
- Ensure tests cleanup created resources or scope them to unique tenant/session namespaces.
