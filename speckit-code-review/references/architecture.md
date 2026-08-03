# Architecture Review

Load this file when performing the Architecture review area.

## Goal

Detect violations of layering rules, DDD invariants, dependency direction, and structural contracts defined or implied by the spec and the project's established architecture.

## Step-by-Step

1. Identify the architecture style in use (Clean Architecture, Hexagonal, Layered MVC, DDD, etc.) from existing project structure and spec constraints.
2. Review the git change set for violations of that style's rules.
3. For each issue: record `file`, `class/module`, `line range`, violation type, and description.

## Checklist

- **Layer dependency violations** — e.g., domain layer importing infrastructure types; application layer bypassing domain
- **Boundary leaks** — UI reaching into domain directly; data layer exposing persistence models to outer layers
- **DDD aggregate / root rule violations** — aggregate invariants bypassed, sensitive data leaked through aggregate boundary, entities mutated outside their aggregate root
- **Repository / service ownership violations** — wrong layer handling persistence logic or business rules
- **Circular dependencies** — modules/packages depending on each other creating cycles
- **Cross-context leakage in bounded contexts** — one bounded context directly referencing internal types of another instead of using published interfaces
- **Architecture drift from spec** — spec states architectural constraints (e.g., "no direct DB access from controllers") and code violates them

## Severity Guidance

| Severity | Examples |
|----------|----------|
| `high`   | Domain layer depends on infrastructure; aggregate root exposes mutable internals externally |
| `medium` | Service layer bypasses repository abstraction; circular dependency between two modules |
| `low`    | Minor naming inconsistency that weakens conceptual boundary |

## Output Fields Produced

Populate these JSON fields from this review:

- `architecture` → `[]` if clean
- `architecture` → array of issue objects if any found

Each issue object format:
```json
{ "<Issue type label>": "<Concise description of violation and impact>" }
```

> Discard this file from context after the Architecture review area is complete.
