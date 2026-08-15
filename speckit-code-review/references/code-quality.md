# Code Quality Review — `CODE-*`

Detect logic errors, dead/redundant code, maintainability risks, and performance problems in the git
change set.

## Steps

1. Scope = the git change set (staged + unstaged, incl. renamed/moved/deleted files).
2. Check for SonarQube MCP configuration. If present, run the scan and prioritize its high-severity
   findings. If absent or the scan fails, continue with manual review — **never** a failure condition.
3. Review every changed file line-by-line and every changed class/method body.
4. Merge SonarQube and manual findings into one consolidated result.
5. Record per issue: `file`, `class/service`, `method`, `line range`, issue type, description, and
   `source` (`sonarqube` or `manual`).

## Mandatory: Dead / Redundant Code Detection

Required on every run. Validate usage repository-wide, not just within the changed file.

- Classes never instantiated, imported, or extended
- Methods/functions never called or referenced
- Services/modules registered or declared but never consumed

Report the exact symbol, file, line range, and why it is dead.
**Exception:** do not flag framework-driven usage (DI containers, reflection, annotations, routing
decorators, ORM lifecycle hooks) — report only when no registration or reference evidence exists.

## Checklist

- Logic errors — off-by-one, wrong conditionals/operators, faulty boolean logic
- Complexity — deep nesting, long methods, high cyclomatic complexity
- Maintainability — duplication, magic numbers, poor naming, misleading comments, tight coupling,
  missing abstractions
- Dead/redundant code (see above)
- Performance — N+1 queries, unbounded loading, missing pagination, inefficient algorithms, memory
  leaks, blocking I/O on hot paths, missing caching
- Error handling — swallowed exceptions, overly broad catches, unhandled null/undefined and edge cases
- Concurrency — race conditions, deadlocks, non-atomic operations, shared mutable state
- Resource management — unclosed connections/files/streams, pool exhaustion
- Test gaps — missing unit tests, untested edge and negative paths
- Style/consistency — project convention, linter, or formatter deviations
- Dependencies — outdated, unused, or redundant

## Detail File — `code-quality.json`

Full descriptions, SonarQube results, and complexity metrics for `CODE-*` findings.

> Discard this file from context after the Code Quality review area is complete.
