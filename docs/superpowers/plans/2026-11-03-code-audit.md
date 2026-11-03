# Agent-driven code audit by attack class — Plan (approved 2026-11-03)

**Goal:** find what pattern scanners cannot (missing authorization, cross-user access, path traversal through a
renamed field, logic errors) by having read-only agents audit the code one attack class at a time. Adapted from
Cloudflare's security-audit skill (MIT, attributed). Report-only: nothing is run or changed. Version 2.6 → 2.7.

**Decisions (Alex, 2026-11-03):** runs with `--profile deep` or when the user asks for a code audit, never by
default in quick/standard. Budget: 12 units (standard, on request) / 24 (deep); the rest are recorded as deferred.

## Flow
1. `audit.py plan RUN` — coverage list of units (repo × attack class; repos over 300 source files split by
   top-level folder), starting paths from detected entry points, known scanner findings per repo, budget →
   planned / deferred. `audit.py prompt RUN UNIT` prints the exact hunter prompt.
2. One fresh read-only hunter per planned unit → one JSON result (covered / candidate / blocked, files read,
   checks, candidates with an entry→sink trace, hardening notes, uncovered areas).
3. One coverage critic (`audit.py critic-prompt`) → `audit.py add-units` (within budget; one extra wave).
4. `audit.py collect RUN RESULTS_DIR` — each result checked whole (pure JSON, known planned unit, repo-relative
   paths that exist, trace lines inside the file, capped + redacted text); candidates → `code-audit` findings
   (raw `<repo>/code-audit.json`, ledger `triage/audit-ledger.json`), reports regenerated, verdicts kept.
5. Phase "Verify findings" always queues code-audit candidates; they count only once verified
   (confirmed / needs validation); until then listed as "pending verification". Never marked "fixed".
6. Report: "🔎 Code audit" section (units and their result, classes, deferred units, hardening notes, pending
   candidates); JSON `code_audit` block checked by the validator.

**Classes:** standard — injection, access control, files & resources, crypto & secrets, business logic, obvious
exposures; deep adds — feature abuse & data leakage, chained trust gaps, wildcard. Domain companions and
Cloudflare's sandboxed execution of target code are out of scope.

## Tasks
- [x] T1 `audit.py plan` / `prompt` / `critic-prompt` / `add-units` + `references/code-audit.md` (prompts, classes)
- [x] T2 `audit.py collect`, `report_audit.py`, pending-verification counting, triage queue with trace
- [x] T3 report section (MD/HTML/JSON), schema + validator, generate-report regeneration
- [x] T4 SKILL.md phase, README, CI step, v2.7, attribution
- [x] T5 verify: tests on 3.8 / 3.13, real run with seeded bugs (real hunters, critic, verifiers), PR
