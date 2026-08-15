# Business Gap Review — `FR-*` / `NFR-*`

Validate that every requirement in the checklist is fully implemented in the changed code.

## Steps

1. Take the checklist from SKILL.md **Requirement Checklist**. If it was synthesized (spec had no
   IDs), review against it exactly as if the IDs were declared.
2. For each requirement, review the implementation line-by-line and map it to concrete evidence:
   `file`, `method/function`, `line range`, and a short explanation of how the code satisfies it.
3. Classify each requirement:
   - `covered` — fully implemented with clear evidence
   - `partially_covered` — some logic exists but incomplete
   - `missing` — no implementation evidence found
   - `conflicting` — implementation contradicts the requirement
4. For every non-`covered` requirement, record in the detail file: `requirement_id`,
   `missing_behavior` (exact required behavior that is absent), `suggested_fix_area`
   (file + method + line range), and `why_missing` (concrete reason, e.g. method exists but the
   validation branch is absent). Emit a matching `fixes` entry.

## Functional Checklist

- Missing requirements (specified behavior not implemented)
- Conflicting requirements (contradicts spec or another requirement)
- Incorrect business logic (wrong calculations, rules, or workflow order)
- Edge cases and boundary conditions not handled per spec
- Data integrity — invalid state transitions, unvalidated business invariants
- Backward compatibility — API contract changes, data migration risks
- Acceptance criteria not met
- Scope creep — changes beyond the stated requirements

## Non-Functional Checklist

- Performance — latency, throughput, pagination, caching
- Reliability — retries, circuit breakers, fallback behaviour
- Scalability — sharding, partitioning, horizontal scaling
- Maintainability — observability hooks, structured logging
- Compliance — GDPR, HIPAA, audit trail, data retention
- UX — response time, accessibility, error message clarity

## Detail File — `business-gap.json`

Beyond the standard finding fields, include:

- `Business cover`, `requirements checklist summary`, and the per-requirement classification
- `requirements_source` — `declared` or `synthesized`
- `synthesized_requirements` — only when synthesized; each `{id, statement, spec_anchor}`

## Edge Cases

- No evidence found → `missing`. Never assume covered.
- Ambiguous wording → treat as not covered and document the missing evidence.
- A high-impact non-functional violation still forces `failed`.
- A design-style spec with no IDs is **never** grounds for 100% coverage — synthesize first; if
  nothing testable exists, emit `FR-000` per SKILL.md.

> Discard this file from context after the Business Gap review area is complete.
