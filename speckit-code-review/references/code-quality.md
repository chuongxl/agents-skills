# Code Quality Review

Load this file when performing the Code Quality review area.

## Goal

Detect logic errors, dead/redundant code, maintainability risks, performance problems, and test gaps in the git change set.

## Step-by-Step

1. Fetch the git change set (staged + unstaged, renamed/moved/deleted files) as the review scope.
2. Check whether SonarQube MCP configuration is available for this repository/workspace.
3. If SonarQube MCP configuration exists, run SonarQube scan and collect code-quality findings from SonarQube.
4. If SonarQube MCP configuration does not exist or SonarQube scan cannot run, continue with manual code-quality review (do not fail the review process because of missing SonarQube configuration).
5. Review every changed file line-by-line and every changed class/method body.
6. Merge findings from SonarQube (if available) and manual review into one consolidated code-quality result.
7. For each issue found, record: `file`, `class/service`, `method`, `line range`, issue type, description, and source (`sonarqube` or `manual`).

## SonarQube MCP Behavior

- SonarQube scan is **conditional** on existing MCP configuration.
- The skill must always perform the SonarQube-check step, even when configuration is absent.
- Missing SonarQube config is not a failure condition for the skill; continue manual review.
- If SonarQube runs successfully, prioritize high-severity SonarQube findings in `code issues`.

## Mandatory: Dead / Redundant Code Detection

This check is required on every run.

- Detect **classes** that are not instantiated, imported, extended, or used anywhere in the repository.
- Detect **methods/functions** that are never called or referenced anywhere.
- Detect **services/modules** registered or declared but never consumed.
- Validate usage through repository-wide references — not just local file scope.
- For each finding report: exact symbol name, file, line range, and reason it is dead.
- **Exception**: Do not flag as dead when framework-driven usage exists (DI containers, reflection, annotations, routing decorators, ORM lifecycle hooks). Only report when no runtime registration or reference evidence exists.

## Checklist

- Logic errors (off-by-one, incorrect conditionals, wrong operators, faulty boolean logic)
- High complexity (deep nesting, long functions/methods, high cyclomatic complexity)
- Maintainability risks (duplicated code, magic numbers, poor naming, missing/misleading comments, tight coupling, missing abstractions)
- Dead/redundant code (see mandatory section above)
- Performance issues (N+1 queries, unnecessary loops, unbounded data loading, missing pagination, inefficient algorithms, memory leaks, blocking I/O on hot paths, missing caching)
- Error handling (swallowed exceptions, missing error handling, overly broad catches, unhandled edge cases, null/undefined handling)
- Concurrency issues (race conditions, deadlocks, non-atomic operations, shared mutable state)
- Resource management (unclosed connections/files/streams, connection pool exhaustion)
- Test coverage gaps (missing unit tests, untested edge cases, missing negative-path tests)
- Style/consistency (violations of project conventions, linter/formatter deviations)
- Dependency issues (outdated, unused, or redundant dependencies)

## Output Fields Produced

Populate these JSON fields from this review:

- `code issue` → `"none"` if clean
- `code issues` → array of issue objects if any found
