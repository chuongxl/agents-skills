# Business Gap Review

Load this file when performing the Business Gap review area.

## Goal

Validate that every functional and non-functional requirement extracted from `spec.md` is fully implemented in the changed code.

## Step-by-Step

0. Obtain the requirement checklist from SKILL.md **Requirement Checklist Extraction**. If the spec
   carried no IDs (typical for `superpowers:brainstorming` design docs), the checklist is
   synthesized — review against it exactly as if the IDs were declared, and record
   `requirements_source` plus `synthesized_requirements` in this category's detail file.
1. For each requirement in the checklist (`FR-*` / `NFR-*`), review the implementation line-by-line and method-by-method.
2. Map each requirement to concrete code evidence:
   - `file`
   - `method/function`
   - `line range`
   - short explanation of how the code satisfies the requirement
3. Classify each requirement:
   - `covered` — fully implemented with clear evidence
   - `partially_covered` — some logic exists but incomplete
   - `missing` — no implementation evidence found
   - `conflicting` — implementation contradicts the requirement
4. For any `missing`, `partially_covered`, or `conflicting` requirement, produce a `Business missing details` entry:
   - `requirement_id` (`FR-*` / `NFR-*`)
   - `missing_behavior` — exact behavior the spec requires but is absent
   - `suggested_fix_area` — file + method/function + line range when possible
   - `why_missing` — concrete reason (e.g., method exists but validation branch absent)

## Checklist: Functional Issues

- Missing requirements (specified behavior not implemented)
- Conflicting requirements (implementation contradicts spec or other requirements)
- Incorrect business logic (wrong calculations, wrong rules, wrong workflow order)
- Edge cases and boundary conditions not handled per spec
- Data integrity (invalid state transitions, missing validation of business invariants)
- Backward compatibility / breaking changes (API contract changes, data migration risks)
- Acceptance criteria not met
- Scope creep (changes beyond stated requirements)

## Checklist: Non-Functional Issues

- Performance NFRs not met (latency, throughput, pagination, caching)
- Reliability NFRs not met (retries, circuit-breakers, fallback behaviour)
- Scalability NFRs not met (sharding, partitioning, horizontal scaling)
- Maintainability NFRs not met (observability hooks, structured logging)
- Compliance NFRs not met (GDPR, HIPAA, audit trail, data retention)
- UX NFRs not met (response time, accessibility, error message clarity)

## Output Fields Produced

Populate these JSON fields from this review:

- `Business cover`
- `requirements checklist summary`
- `requirements_source` — `declared` or `synthesized`
- `synthesized_requirements` — present only when `requirements_source` is `synthesized`
- `Business missing`
- `Business missing details`

## Edge Cases

- If no evidence can be found for a requirement, treat it as `missing` (never assume covered).
- If requirement wording is ambiguous, prefer `failed` and document the missing evidence.
- Non-functional violations still produce `failed` when impact is high.
- A design-style spec with no requirement IDs is **never** a reason to report 100% coverage —
  synthesize the checklist first; if nothing testable can be extracted, emit `FR-000` per SKILL.md.

> Discard this file from context after the Business Gap review area is complete.
