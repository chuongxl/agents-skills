# Architecture Review — `ARCH-*`

Detect violations of layering rules, DDD invariants, dependency direction, and structural contracts
defined or implied by the spec and the project's established architecture.

## Steps

1. Identify the architecture style in use (Clean, Hexagonal, Layered MVC, DDD, …) from the existing
   project structure and any spec constraints.
2. Review the git change set for violations of that style's rules.
3. Record per issue: `file`, `class/module`, `line range`, violation type, description, and severity
   (scale in SKILL.md — `high` covers domain depending on infrastructure or an aggregate root
   exposing mutable internals).

## Checklist

- **Layer dependency violations** — domain importing infrastructure types; application bypassing domain
- **Boundary leaks** — UI reaching into domain; data layer exposing persistence models outward
- **DDD aggregate / root violations** — invariants bypassed, sensitive data leaked across the
  aggregate boundary, entities mutated outside their root
- **Ownership violations** — the wrong layer handling persistence logic or business rules
- **Circular dependencies** between modules or packages
- **Cross-context leakage** — a bounded context referencing another's internal types instead of its
  published interface
- **Drift from spec** — code violating an architectural constraint the spec states (e.g. "no direct
  DB access from controllers")

## Detail File — `architecture.json`

Full violation descriptions and their impact for `ARCH-*` findings.

> Discard this file from context after the Architecture review area is complete.
