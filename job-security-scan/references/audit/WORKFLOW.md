# Deep audit (Phase 10) — how to run it in job-security-scan

The scanners and verification (Phases 1–9) find known-bad things: leaked secrets, vulnerable packages, misconfigurations,
known malware. They cannot see logic flaws such as a missing owner check, a cross-tenant read or a CI
workflow that runs pull-request code with secrets. The deep audit finds those. It is an agent-driven method,
copied from [cloudflare/security-audit-skill](https://github.com/cloudflare/security-audit-skill) (MIT, see
[NOTICE.md](NOTICE.md)), with this skill's rules layered on top.

This file is the entry point. The method itself is in [METHOD.md](METHOD.md) and the phase files it links
to; read them as written, then apply the substitutions below. Where this file and an upstream file differ,
**this file wins**.

## Operating modes

- **Guidance mode** (default for a security *question*, a focused review, or triage of one lead): use only
  the relevant parts of [ATTACK-CLASSES.md](ATTACK-CLASSES.md) and the companion files. Do not run
  `run-scan.sh`, do not create a run folder, and do not write audit files.
- **Full audit mode**: the user asks to audit or pen-test a repo, asks for a full / deep / end-to-end
  security review, runs `run-scan.sh --audit` or `--scanner audit`, or asks for report files. Run every phase
  below.

If the request could be either, ask one short question before creating anything.

## Start: let the script do the deterministic part

```bash
# deep audit only
bash scripts/run-scan.sh --scanner audit [--repo NAME] [--profile quick|standard|deep] [--since origin/main] [--budget 40]
# all scanners, then the deep audit
bash scripts/run-scan.sh --audit [--profile ...]
```

For each repo the script writes `security-run-<datetime>/<repo>/audit/`:

| File | Written by | Purpose |
|---|---|---|
| `run-metadata.json` | script, then parent | run id, target, commit + dirty flag, profile, scope, budget, execution policy, prior runs, `run_status` |
| `recon-hints.json` | script | grep hits grouped by companion file — places to start reading, **not** findings and **not** coverage |
| `AGENT-TASK.md` | script | the resolved values and commands for this repo |
| `architecture.md`, `coverage-ledger.json`, `findings.json` | parent | upstream Phases 1–5 |
| `REPORT.md`, `FINDINGS-DETAIL.md`, `NEEDS-VALIDATION.md` | parent | upstream Phase 6 |
| `agents/<agent-id>/scratch/`, `agents/<agent-id>/artifacts/` | parent creates | per-agent write isolation |

The run folder holds a `.gitignore` of `*`, so audit files never get committed even when the run folder
sits inside the scanned repository. That satisfies the upstream rule for an in-target output directory.

## Substitutions for the upstream method

| Upstream says | In this skill |
|---|---|
| Output directory `~/security-audit-skill/<repo-name>/run-<N>` | `security-run-<datetime>/<repo>/audit/` (prepared by the script) |
| Write `run-metadata.json` before delegation | Already written. Update only `run_status`, `incomplete_reason`, `selected_companions`, and facts that change |
| `report-schema.json` | `assets/audit/findings.schema.json` (unchanged copy) |
| `node <skill-dir>/validate-findings.cjs <file>` | `python3 -I <skill-dir>/scripts/validate-audit.py findings <file>` |
| `node <skill-dir>/validate-coverage-ledger.cjs <file>` | `python3 -I <skill-dir>/scripts/validate-audit.py ledger <file>` |
| Deriving `coverage_id` by hand | `python3 -I <skill-dir>/scripts/audit-ledger.py id ...` for one unit; `audit-ledger.py seed units.json --out coverage-ledger.json [--merge]` to build or extend the ledger |
| The OS-enforced sandbox | `python3 -I <skill-dir>/scripts/audit-sandbox.py --scratch <audit>/agents/<id>/scratch [--record <file outside scratch>] -- CMD`; only when `execution_policy` is `sandboxed-source-and-local-only` |
| The artifact promotion procedure (trusted parent-side code) | `python3 -I <skill-dir>/scripts/audit-promote.py --agent-dir <audit>/agents/<id> --file <scratch-relative> ...` |
| Prior `coverage-ledger.json` / `findings.json` | listed in `run-metadata.json` → `prior_runs` |
| Hunter `hardening` notes kept in ledger bookkeeping | store them as a `hardening` array of strings on the relevant ledger unit — the unified report shows them |
| "Reject malformed hunter results" / "discard a malformed or prose-wrapped verifier result" | `python3 -I <skill-dir>/scripts/validate-audit.py hunter <result.json> --assigned <id> ...` and `validate-audit.py verifier <result.json> --fingerprint <fp>` — save the agent's final message unmodified first; anything that is not exactly one JSON object is discarded, never repaired |
| Task tool, `research` / `general` agents | the platform's sub-agent tool (for Claude Code: the Agent tool). Each hunter and verifier is a fresh agent |

`run_status` values are `awaiting_agent` (set by the script), `in_progress`, `complete` and `incomplete`.
`execution_policy` is `source-only` or `sandboxed-source-and-local-only`.

## Scheduling and resuming a multi-repo run

`run-scan.sh` only prepares Phase 10. A regenerated, valid scanner report does not execute or complete
the code audit. The parent owns both Phase 9 and Phase 10 until their completion checks pass.

1. List the prepared `audit/AGENT-TASK.md` paths from the scanner output. Keep a per-repo checklist of
   reconnaissance, hunting, candidate validation, final verification, reports and completion checks.
   Start reconnaissance and seed a validated ledger for every requested repo before draining the
   scanner-verification queue. Do not treat recon hints as coverage or create empty placeholder ledgers.
2. Rotate through repos. Advance one audit wave or validation/reporting phase, then process at most
   one Phase 9 batch for that repo before moving to the next. Do not drain thousands of scanner
   findings while other repos still have no audit ledger. Finish a ready audit's validation and
   reports before starting more hunting. Agents return isolated results; only the parent writes shared
   files or regenerates the unified report.
3. After every agent result, update the ledger and findings when applicable, validate the files that
   exist, and checkpoint `agent_invocations` and `next_action` in that repo's `run-metadata.json`.
   Persist the count before every launch, including failed agents and retries.
   Preserve the profile's critic and verifier reserves in [METHOD.md](METHOD.md).
   `--budget` is the maximum audit-agent invocations for each repo, as prepared in its metadata.
   It does not cap Phase 9. An unset budget is not permission to invent a silent cutoff.
4. On a context or session limit, retain completed artifacts and the exact next action for each repo.
   Set unfinished audits to `incomplete` with the concrete reason. Write partial Phase 6 reports
   from the evidence already collected, including unresolved candidate fingerprints and uncovered
   units. Do not abandon all 27 audits because the scanner queue is large.
5. To resume, reuse the existing run directory, `AGENT-TASK.md`, metadata, ledger, agent results and
   findings. Do not rerun `run-scan.sh` or `audit-prepare.py`, which creates a new run or overwrites
   preparation metadata. Verify the relevant source still matches the recorded evidence, including
   dirty and untracked files. Revalidate changed paths instead of carrying stale coverage.
   Read the persisted invocation count; never reset a strict budget on resume. If older metadata has
   no count, reconstruct it from retained launch records before spending a strict budget.
   Use `triage.py status <run>` to apply saved verdicts or resume the active batch without losing groups.
6. Continue until Phase 9's run-wide check and every requested repo's Phase 10 check pass. If a real
   blocker prevents that, report partial completion, exact remaining work and the same-run resume
   action. Report validation alone is never the stopping condition.

## Rules of this skill that tighten the method

1. **Report only.** Never edit, patch, commit or delete anything in the target, and never offer, ask or
   attempt to fix findings. `remediation` and `code_changes` are text for the reader.
2. **Nothing from the target runs by default.** Unless `run-metadata.json` says
   `execution_policy: sandboxed-source-and-local-only` (the user set `JOB_SECURITY_SCAN_AUDIT_EXEC=1` and
   the sandbox self-test passed), the audit is **source-only**: do not execute target code at all. A
   candidate that needs a local result to be confirmed stays `needs_validation`, with the blocker
   `local execution disabled (JOB_SECURITY_SCAN_AUDIT_EXEC is not 1)` and a `validation_plan.local` that
   names the exact harness to run.
3. **With execution enabled, only through `audit-sandbox.py`.** Never run target code any other way. Exit
   code 97 means a sandbox control is unavailable: nothing ran; record the printed blocker as
   `needs_validation`. Pass `--record` with a path outside scratch so the command, limits and environment
   names are captured by the parent; promote evidence with `audit-promote.py` only after the sandboxed
   process has exited, and cite the printed `agents/<id>/artifacts/...` path in the ledger check.
   Write a harness into the agent's own scratch first (it is visible inside; the target is readable,
   read-only, at its absolute path). Scratch is a size-limited tmpfs during the check (`--disk-mb`,
   default 64), copied back afterwards. `--loopback` needs the `ip` tool; without it, call the handler
   in-process.
4. **No secret values.** Never copy a credential, token or key value into a record, artifact, prompt or
   report, even from a test fixture. Cite `file:line` only.
5. **No network.** Reconnaissance, hunting and verification read local source only. Do not install
   dependencies, fetch tools, or contact registries, deployed endpoints or cloud APIs.
6. **Independence is not optional.** Hunters, candidate verifiers and final verifiers must be separate fresh
   agents, as the method requires. If the platform cannot launch fresh sub-agents, do not emit `confirmed`
   records: keep candidates in the ledger, set `run_status: "incomplete"` with
   `incomplete_reason: "independent_verification_unavailable"`, and say so.

## Steps

1. Read `AGENT-TASK.md`, `run-metadata.json` and `recon-hints.json`. Set `run_status` to `in_progress`.
2. **Phase 1 — Reconnaissance** ([RECONNAISSANCE.md](RECONNAISSANCE.md)): launch the reconnaissance agents,
   write `architecture.md`, choose companion files from [ATTACK-CLASSES.md](ATTACK-CLASSES.md), and seed the
   ledger with `audit-ledger.py seed`. Respect `profile`, `scope_paths` (from `--since`) and `budget`
   exactly as [METHOD.md](METHOD.md) describes. Validate the ledger.
3. **Phase 2 — Hunting waves** ([HUNTING.md](HUNTING.md)): build every hunter prompt as specified, with the
   attack-class blocks copied verbatim. Add rules 1–5 above to each prompt. Check each result with
   `validate-audit.py hunter` before it touches the ledger (observed slips: `verdict` instead of
   `proposed_verdict`, unit paths no check owns, overall severity above impact). Update and validate the
   ledger after each wave; run the coverage critics.
4. **Phase 3 — Candidate validation**, **Phase 4 — `findings.json`**, **Phase 5 — fresh-eyes
   verification** ([VALIDATION-AND-REPORTING.md](VALIDATION-AND-REPORTING.md)). Check each verifier result with
   `validate-audit.py verifier`; a fenced or prose-wrapped answer is discarded and re-run with a fresh
   verifier while the budget allows. Validate both files after every change: `python3 -I <skill-dir>/scripts/validate-audit.py run <audit-dir>`.
5. **Phase 6 — Reports**: write `REPORT.md`, `FINDINGS-DETAIL.md` and `NEEDS-VALIDATION.md` in the audit
   folder, then set `run_status` to `complete` (or `incomplete` with `incomplete_reason`) and validate
   again. Before claiming completion, run `python3 -I <skill-dir>/scripts/validate-audit.py complete <audit-dir>`.
   It requires the architecture and report files, valid metadata/ledger/findings, `run_status: complete`,
   no planned, in-progress, blocked or deferred units, and a final finding record for every candidate
   fingerprint. `needs_validation` records with source evidence and independent verification are allowed;
   unvalidated candidates are not. Passing this check proves artifact consistency, not absence of bugs.
   If it fails, finish the named work or retain `incomplete` with the actual blocker. Never add empty
   findings, blanket blockers or fake coverage to satisfy the validator.
6. **Merge into the unified report**: run the `generate-report.py` command from `AGENT-TASK.md` (it keeps this run's profile, scope and baseline). Confirmed
   records join the scanner findings (scanner `audit`, already verified, with their own severity); `needs_validation` leads,
   coverage, gaps and hardening notes get their own section. The merge only happens when all three files
   validate and `run_status` is final; otherwise the report says why the audit was not merged.
7. Reply as in "Output Format" of `SKILL.md`, adding the confirmed audit findings (`file:line`, severity)
   and the number of needs-validation leads. Include completion-check failures and resume actions when
   either phase is unfinished. A source-only audit may complete with independently validated
   needs-validation leads; disabled local execution is not a reason to skip hunting or reporting.

## Severity

Only `confirmed` records have a severity. In the unified report `critical`/`high`/`medium`/`low` map to the
same scanner levels and `informational` to INFO. Use the calibration anchors in [METHOD.md](METHOD.md)
("Separate priority from certainty"); overall severity can never exceed demonstrated impact.
