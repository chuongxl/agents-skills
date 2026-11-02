# Verified Findings, Run-to-Run Changes, Profiles, Report Schema — Design and Plan

> **For agentic workers:** REQUIRED SUB-SKILL: superpowers:executing-plans. Test-first; checkbox steps.

**Goal:** Bring four ideas from Cloudflare's `security-audit` skill (MIT) into job-security-scan, staying a
report-only scanner: (1) independent verification of scanner findings with `confirmed` / `needs_validation` /
`rejected` verdicts and calibrated severity, (2) changes since the last run, (3) run profiles and scoped runs,
(5) a schema and validator for `security-report.json`. Item 4 (agent-driven code audit by attack class) is a
separate, later PR.

**Base:** branch `feat/verified-findings` on top of `fix/self-security-audit` (PR #53, open). The PR targets
that branch and is retargeted to `main` once #53 merges.

**Stack:** bash + Python 3.8 stdlib. Version `2.4` → `2.5`.

## Decisions (Alex approved 1, 2, 3, 5 on 2026-11-02)

- Verification is an **agent step after the scan**; the scan itself stays deterministic and offline-capable.
- Nothing is ever fixed or modified; verdicts and recalibrated severity are report content only.
- Text adapted from Cloudflare's skill carries their MIT notice (`references/third-party/cloudflare-security-audit-LICENSE`)
  and a source line in each adapted file.

## 1. Fingerprints (foundation for 1 and 2)

Every finding gets `fingerprint` = first 16 hex of SHA-256 over a **line-independent** key, so code moving down a
file keeps its identity, while changed code gets a new one:

| Kind | Key |
|---|---|
| dependency (Trivy vuln, OSV, advisories, Shai-Hulud known-package) | scanner, rule_id, repo, file, package, installed_version |
| secret (Gitleaks, TruffleHog, Trivy secret, Semgrep secret) | scanner, rule_id, repo, file, line (no code is ever stored) |
| everything else | scanner, rule_id, repo, file, whitespace-normalised code excerpt (line if no excerpt) |

## 2. Changes since the last run

- Previous run = the newest other `security-run-*` folder beside the current one whose JSON has `schema_version >= 2`.
- Each finding gets `change: "new" | "unchanged"`. `fixed[]` lists previous fingerprints not seen now — **only for
  repos and scanners that ran in both runs**, so a single-scanner or `--repo` run never marks the rest "fixed".
- Verdicts from the previous run are **carried over** to unchanged fingerprints (marked `carried: true`) so an
  agent does not re-verify unchanged findings; changed code has a new fingerprint and is verified again.
- Reports: "Changes since last run" section (new / fixed / unchanged counts + fixed list), `NEW` badge in HTML.

## 3. Profiles and scope

`run-scan.sh --profile quick|standard|deep` (default `standard` = today's behaviour) and `--since <git-ref>`:

| Profile | Scanners | Findings queued for verification |
|---|---|---|
| `quick` | Gitleaks (working tree only, no history), OSV, Shai-Hulud | none (fast PR check) |
| `standard` | everything (today's `all`) | CRITICAL + HIGH |
| `deep` | everything; Trivy also LOW | CRITICAL + HIGH + MEDIUM |

- `--scanner` still picks one scanner and overrides the profile's scanner list.
- `--since REF`: per repo, files changed in `REF...HEAD` (plus working-tree changes) via `git diff --name-only`;
  findings outside them are dropped from the report; dependency findings stay when the lockfile/manifest changed.
  The report states the scope and that it is a partial pass. Not a git repo / unknown ref → warning, full scope.
- Profile and scope are recorded in the JSON (`run.profile`, `run.since`, `run.partial`).

## 4. Independent verification (agent step)

Deterministic helper `scripts/triage.py`:

- `triage.py queue RUN_DIR` → `RUN_DIR/triage/queue.json`: the findings the profile queues, minus carried verdicts,
  each with fingerprint, finding fields and a **context window** (±15 lines around `file:line`; **none for secrets**).
- `triage.py apply RUN_DIR VERDICTS.json` → validates verdicts against `assets/verdict.schema.json` rules, merges
  them into `security-report.json`, regenerates the MD/HTML reports and writes `NEEDS-VALIDATION.md`.

Verdict record (adapted from Cloudflare's contract):

| Verdict | Required | Effect |
|---|---|---|
| `confirmed` | `evidence` (why it is real/reachable), `likelihood`, `impact`, `severity` ≤ impact | verified severity replaces the tool's |
| `needs_validation` | `blocker` (the exact unresolved fact), `validation_plan` | no verified severity; listed in NEEDS-VALIDATION.md |
| `rejected` | `reason` (e.g. test fixture, dev-only dependency, unreachable code, already mitigated) | moved to "Dismissed (with reason)"; out of counts |

`SKILL.md` gains "Phase 9 — Verify findings": after `run-scan.sh`, run `triage.py queue`; for each queued finding
use a **fresh sub-agent that did not see the scan summary** (or, without sub-agents, a separate pass per finding)
with the verifier prompt in `references/verification.md` — try to disprove it from the repository source and the
context only; no network, no executing repository code, no edits. Collect results into `verdicts.json`, run
`triage.py apply`. Severity anchors (critical/high/medium/low/info) and the high-vs-medium discriminator are copied
into `references/verification.md` with attribution.

## 5. Report schema and validator

- `security-report.json` → `schema_version: 2`, new fields: `run` (profile, since, partial, previous_run),
  per finding `fingerprint`, `change`, `verdict` (null until verified), `verified_severity`, `verdict_detail`;
  top-level `fixed[]`, `verification` (queued / confirmed / needs_validation / rejected / pending counts).
- `assets/report.schema.json` mirrors `scripts/validate-report.py` (stdlib; the enforced contract): types, enums,
  unique fingerprints, counts match findings, verdict rules (above), no code excerpt on secret rows, size limits.
- `run-scan.sh` and `triage.py apply` run the validator; failure → warning + non-zero exit.

## Tasks

- [x] **T1 Fingerprints + schema v2 + validator** — `report_formats.fingerprint()`, `scripts/validate-report.py`,
  `assets/report.schema.json`. Tests: stable across line moves, changes with code, secrets never hash code;
  validator rejects each broken rule (≥8 cases); a real generated report validates.
- [x] **T2 Changes since last run** — previous-run discovery, `change`, `fixed[]` scoped to common repos+scanners,
  verdict carry-over; MD/HTML sections. Tests: new/unchanged/fixed; single-scanner run marks nothing fixed;
  moved code stays unchanged; edited code is new; verdicts carried.
- [x] **T3 Profiles + `--since`** — run-scan flags, gitleaks `--no-git` for quick, Trivy severities for deep,
  changed-file filter in generate-report. Tests: scanner lists per profile (stubs), `--scanner` override,
  `--since` filters to changed files + lockfile rule, non-git fallback warns, report says partial.
- [x] **T4 Triage queue/apply + NEEDS-VALIDATION.md** — `scripts/triage.py`, verdict validation, report regen.
  Tests: queue by profile, no context for secrets, carried verdicts skipped, each verdict rule enforced,
  rejected leaves counts, confirmed severity cannot exceed impact, apply is idempotent.
- [x] **T5 Agent instructions + attribution + docs** — SKILL.md Phase 9, `references/verification.md` (verifier
  prompt + severity anchors, adapted, attributed), Cloudflare MIT notice, README, CI step for new tests, v2.5.
- [x] **T6 Verify end to end** — all suites on Python 3.8/3.12; e2e scripts; a real run on the sample workspace:
  scan → queue → **real independent verifier agents** on the queued findings → apply → second run shows
  changes; check every report validates and no secret appears. Then PR.

## Review focus

1. A secret's code line must never reach the triage queue, a verdict, or a report.
2. A partial run (`--scanner`, `--repo`, `--since`, `quick`) must never mark unscanned findings "fixed".
3. A carried verdict must never apply to changed code.
4. A malformed or prose-wrapped agent verdict is rejected by `apply`, never half-merged.
5. Existing users: v1 JSON from earlier runs is treated as "no previous run", not an error.
