---
name: job-security-scan
description: >
  Free, report-only security scan of a team's repos, configured by one repository.md file. Runs Gitleaks
  (secrets in git history), Trivy (CVEs, Dockerfile misconfig), Semgrep (SAST), Hadolint, OSV-Scanner,
  TruffleHog (live credential check), vendor advisories and an offline Shai-Hulud worm check (repos and,
  with --host, this computer). Optional deep audit (--audit): an agent-driven, coverage-led review for
  logic flaws scanners miss (authorization, tenant isolation, CI trust, injection); every finding is
  independently re-verified. Every run writes md/json/html reports with file:line, what is new or fixed since
  earlier runs, verifier verdicts, and a baseline for accepted findings. Use to scan for vulnerabilities,
  secrets, malware or misconfigurations, for a security audit or pen-test of code, to set up a CI security
  pipeline, or to check for Shai-Hulud. Supports --repo, --scanner, --profile quick|standard|deep, --since.
compatibility: >
  Requires bash, git, Python 3.8+ (pre-installed on most systems — used
  only to parse repository.md, no pip packages needed). Security tools
  auto-installed via Homebrew (macOS) or curl/apt (Linux) on first run.
  Network access required for tool install and CVE DB download on first run.
  Subsequent runs use cached DB and installed binaries.
license: MIT
metadata:
  author: one-om-ddm-team
  version: "3.3.1"
  config-file: assets/repository.md
allowed-tools: bash glob grep view create edit ask_user
---

# Job Security Scan

Generic, config-driven security scanner for any multi-repo workspace.

> **Report only.** This skill finds and reports problems; it never fixes them. Never modify, patch, upgrade,
> delete or commit anything in a scanned repo, and never offer, ask or attempt to fix findings. Remediation
> appears only as guidance text in the report (`references/remediation.md`). End after presenting the report and
> asking whether the user wants to import it into DefectDojo.

## Modes

- **Guidance** — a security question, a focused review of one file or lead, or triage: answer from the
  references (`references/audit/ATTACK-CLASSES.md` and its companion files for code-level questions). Do not
  run the scan or write files.
- **Scan** — "scan", "check for secrets/vulnerabilities/Shai-Hulud", CI setup: run `run-scan.sh`
  (Phases 1–8), then Phase 9 verification.
- **Deep audit** — "audit / pen-test this code", "full / deep security review": run the scan with `--audit`
  (or `--scanner audit` alone), then follow `references/audit/WORKFLOW.md` (Phase 10).

If a request could be either guidance or a full run, ask one short question first.

## Configuration — `assets/repository.md`

**All team and repo details live in one file.** Before running, verify or
edit `assets/repository.md` in this skill folder. See the file itself for
full documentation of each field.

Key fields:

| Field | Purpose | Example |
|-------|---------|---------|
| `team` | Team identifier (display only) | `ddm` |
| `org` | GitHub organisation | `ocean-network-express` |
| `monorepo-root` | Path to workspace root | `.` |
| `ci-runner` | GitHub Actions runner label | `om-ddm-runner` |
| `package-manager` | *Deprecated* - lockfiles are auto-detected | - |
| `stack` | *Deprecated* - languages are auto-detected | - |
| `repos[].name` | Repo directory name | `om-ddm-backend` |
| `repos[].active` | Include in scan | `true` / `false` |
| `repos[].has-dockerfile` | Run Hadolint | `true` / `false` |
| `fail-on-severity` | Build failure threshold | `HIGH` |
| `secret-allowlist-paths` | Paths exempt from secret scan | `**/.env.example` |
| `cache-dir` | Shared caches (vendor advisories, indicator refresh). Optional | `~/.cache/job-security-scan` |
| `output-dir` | *Deprecated* - now only the cache folder; reports go to `security-run-<datetime>/` | - |

To adapt this skill for a **different team**, create a new `repository.md`
at their workspace root and pass it with `--config`:

```bash
bash .github/skills/job-security-scan/scripts/run-scan.sh \
  --config /path/to/other-team/repository.md
```

## Input Flags

| Flag | Example | Behavior |
|------|---------|----------|
| `--config PATH` | `--config ./repo.md` | Use a custom config file |
| `--repo NAME` | `--repo om-ddm-backend` | Scan one repo only |
| `--scanner NAME` | `--scanner trivy` | Run one scanner only (`audit` = the deep audit alone; `all` does not include it) |
| `--host` | `--host` | Also check this computer for Shai-Hulud; alone, only the host check runs |
| `--profile P` | `--profile quick` | `quick`: Gitleaks (working tree), OSV, Shai-Hulud, no verification. `standard` (default): every scanner, verify CRITICAL+HIGH. `deep`: also Trivy LOW, verify MEDIUM too |
| `--since REF` | `--since origin/main` | Report only files changed since `REF` (plus uncommitted changes). Partial run: no "fixed" list |
| `--audit` | `--audit` | Also prepare the deep audit (Phase 10) for each repo; `--profile` and `--since` scope it too |
| `--budget N` | `--budget 40` | Deep audit: cap on agent invocations |
| `--baseline FILE` | `--baseline ./security-baseline.json` | Accepted findings (default: `security-baseline.json` next to the config, if present) |
| *(none)* | | Full scan — all scanners, all active repos from config |

Short aliases: `-r` for `--repo`, `-s` for `--scanner`

What each scanner finds, how it maps severity and where it overlaps with the others: `references/scanners.md`.

## Phase 0 — Parse Config & Install Tools

Load team/repo config from `repository.md`, then install any missing tools:

```bash
# Parse config (Python 3 std-lib only — no pip needed)
eval "$(python3 -I scripts/parse-config.py assets/repository.md)"   # values are shell-quoted

# Install missing tools based on stack + repo config
bash scripts/install-tools.sh
```

`install-tools.sh` reads the config to skip irrelevant tools:
- **Hadolint** only installed if any repo has `has-dockerfile: true`
- **Semgrep** only installed if stack includes TypeScript/JavaScript
- **OSV-Scanner** always installed (lockfiles of every supported ecosystem are detected per repo)

Every tool is **pinned to an exact version** (Trivy `0.69.3`, the immutable release after the March 2026
compromise; Gitleaks, TruffleHog, Hadolint, OSV-Scanner, Semgrep likewise) and on Linux each download is
**checked against the release's SHA-256 sums** before it is installed. Nothing is piped into a shell.
`INSTALL_DIR=~/.local/bin` installs without sudo. See "Security of the skill itself" below.

## Phase 1 — Secret Detection (Gitleaks)

Scans full git history of every active repo using DDM-specific allowlists
from `assets/gitleaks.toml`. Any finding is **CRITICAL** — secrets have no
severity ladder.

## Phase 2 — CVE + Dockerfile + Misconfig (Trivy)

Scans `yarn.lock` / `package.json` for CVEs against NVD + GitHub Advisory DB.
Checks Dockerfiles against CIS benchmarks. Severity threshold from config
`fail-on-severity`. Uploads SARIF to GitHub Security tab when run in CI.

## Phase 3 — SAST (Semgrep)

Semgrep rulesets are derived automatically from the languages detected in each repo
(`ecosystems/*.json`; see `references/ecosystems.md`). The deprecated `stack` field, if present, adds to them. Legacy `stack` mapping:

| Stack entry | Semgrep ruleset |
|-------------|----------------|
| `typescript` | `p/typescript` |
| `nodejs` | `p/nodejs` |
| `nestjs` | `p/nestjs` |
| `nextjs` | `p/typescript` |
| *(all)* | `p/owasp-top-ten`, `p/secrets` always included |

Extra per-repo rulesets can be added via `repos[].semgrep-extra` in config.

## Phase 4 — Dockerfile Lint (Hadolint)

Runs only on repos where `has-dockerfile: true` in `repository.md`. Uses
`assets/hadolint.yaml` for rule overrides.

## Phase 5 — Transitive CVE Scan (OSV-Scanner)

Google's OSV-Scanner checks every detected lockfile (npm, yarn, pnpm, Maven, Gradle, pip, Poetry, Go, Composer, Bundler, Cargo, NuGet) against the OSV.dev DB — catches
transitive dependencies that Trivy sometimes misses. Repos with no recognised
ecosystem (or an ecosystem without a lockfile) get an SBOM fallback: Trivy writes a
CycloneDX SBOM and OSV-Scanner matches it (`sbom.cdx.json`, `osv-sbom.json`).

## Phase 6 — Verified Secret Detection (TruffleHog)

Scans git history and **actively verifies** whether found credentials are
still valid via live API calls. Reports `VERIFIED ACTIVE` vs `unverified`.

## Phase 7 — Vendor Advisories (any language or runtime)

Catches issues the CVE databases lag on, such as a runtime security release announced by its vendor.
`run-scan.sh --scanner advisories` fetches vendor bulletins first, then GHSA/OSV, then CISA KEV and endoflife.date
enrichment into the advisory cache (`~/.cache/job-security-scan/advisories`), and matches them against the repository's runtimes, images and dependencies
(`scripts/fetch-advisories.py`, `scripts/match.py`). Results appear in the report as "Vendor advisories".
It also checks the runtime itself: Dockerfile base images (probed with `node -v` and equivalents **only when
`JOB_SECURITY_SCAN_PROBE_IMAGES=1`** - the probe pulls and runs the image the scanned repo names, in a sandbox:
no network, read-only, no capabilities, `nobody` user, resource limits), compose files, CI `setup-*` actions and version files; end-of-life lines and unpinned tags (`node:22-alpine`, `latest`) are reported.
Set `ADVISORY_OFFLINE=1` to skip the fetch and use the cache. Details: `references/advisory-data.md`.

To ingest a new bulletin: `python3 -I scripts/fetch-advisories.py --advisory <url> --out assets/advisories/<name>.json`,
complete the drafted JSON from the saved page text, and set `source.approved_by` after human review;
unapproved LLM-assisted data is ignored by the matcher.

## Phase 8 — Shai-Hulud Worm Check (repo and laptop)

Answers "has this repo, or this computer, been hit by the Shai-Hulud npm/PyPI worm?" Offline, seconds,
never runs npm/node/pip. `run-scan.sh --scanner shai-hulud` (also part of `all`) writes
`<repo>/shai-hulud.json`; `--host` writes `_host/shai-hulud.json` and shows as "this machine" in the report.

| Verdict | Means | Run exit |
|---|---|---|
| **AFFECTED** (CRITICAL) | Known indicator: a compromised release in a lockfile / `node_modules` / PyPI pin / global install / npm cache, a payload or stager file in a package, a planted workflow or persistence file, or a worm marker string | 🔴 |
| **SUSPICIOUS** (HIGH/MEDIUM) | No known indicator, but an install hook reads credentials *and* sends data out, pipes a download into a shell, runs heavy obfuscated code, or downloads `bun`/TruffleHog | 🟡 |
| clean | Neither; host mode still lists credential stores to rotate *if* affected (values never read out) | ✅ |

Benign hooks (`node-gyp rebuild`, `prebuild-install`, `husky`, esbuild's installer...) are allowlisted in
`assets/ioc/hook-allowlist.json`. Indicators live in `assets/ioc/shai-hulud.json`; refresh with
`python3 -I scripts/fetch-iocs.py --out ~/.cache/job-security-scan/ioc` (used automatically when present).
Data provenance: `references/ioc-data.md`. If affected: the runbook in `references/remediation.md`.
Standalone: `python3 -I scripts/shai-hulud-scan.py --repo PATH` or `--host` (exit 0 clean / 1 suspicious / 2 affected).

**In the reports:** every report has a "🪱 Shai-Hulud check" section with one row per repo (and "this machine"
with `--host`): the verdict (AFFECTED / SUSPICIOUS / CLEAN / ERROR / not run), what the check looked at
(dependency files, packages compared, `package.json` files, install hooks, workflows; for the host: projects,
global installs, Python packages, npm cache entries, credential stores), the indicator data version and a link to
the raw output. A CLEAN row with "nothing to check" means the repo had no lockfile, requirements file or
`package.json`. A failed check shows as ERROR with its message and never marks earlier findings fixed.

## Phase 9 — Verify Findings (agent step)

After `run-scan.sh`, the serious findings are checked by **independent verifiers** before you report. Follow
`references/verification.md` exactly:

For `--audit` or `--scanner audit`, start Phase 10 before draining Phase 9. Follow the multi-repo
scheduling and resume rules in `references/audit/WORKFLOW.md`. Thousands of scanner findings must not
prevent the requested code audit from starting.

1. `python3 -I scripts/triage.py queue security-run-<datetime>` (prints how many are queued and how many stay
   pending; `quick` queues none). One root cause per repo (same advisory + package + version, same misconfig
   rule) is one item; at most `--limit 25` items per batch by default, not per run.
   Use `--repo NAME` to work a large scan repo by repo.
2. Loop: `triage.py next <run>` prints one item (or `{"done": true, "scope": "current_queue", "next_action": "status"}`);
   give it to one **fresh sub-agent** with
   the verifier prompt and the repo path — nothing else. Verifiers read source only: no edits, no running repo
   code, no network, never open a file holding a secret.
3. Keep only a reply that is a single JSON object and save it with `triage.py record <run> -` (object on stdin).
   Never open the queue, batch or report JSON files yourself; one item at a time keeps large runs in context.
4. `python3 -I scripts/triage.py apply security-run-<datetime>` merges every recorded verdict (a grouped item's
   verdict covers its group). Use `triage.py status <run>` to choose `apply`, `next`, `queue` or `done`.
   Continue batches until `triage.py status <run> --require-complete` exits 0, unless the user explicitly
   skips verification or a concrete blocker prevents progress. A batch ending or a report passing validation
   is not completion. Do not invent a total verification budget; `--budget` belongs to Phase 10.

Verdicts: **confirmed** (verified severity, never above demonstrated impact), **needs validation** (the exact
missing fact plus a safe check, listed in `NEEDS-VALIDATION.md`), **rejected** (moved to "Dismissed (with
reason)", out of the counts). Verdicts carry over to the next run while the code is unchanged.

## Phase 10 — Deep Audit (agent-driven, opt-in)

Scanners match known-bad patterns; they cannot tell that `GET /notes/:id` forgot the owner check its
`DELETE` sibling has. The deep audit is the method of
[cloudflare/security-audit-skill](https://github.com/cloudflare/security-audit-skill) (MIT, see
`references/audit/NOTICE.md`), copied into `references/audit/` and adapted to this skill. It adds to the
scanners and to Phase 9; it does not replace them.

1. `run-scan.sh --audit` (or `--scanner audit`) prepares `security-run-<datetime>/<repo>/audit/`: run
   metadata (commit + dirty flag, profile, scope from `--since`, budget, earlier audits of the repo),
   reconnaissance hints and `AGENT-TASK.md`.
2. The agent then runs the six phases in `references/audit/WORKFLOW.md`: reconnaissance and a deterministic
   coverage ledger, coverage-led hunting by isolated agents with the attack-class files, independent
   validation of every candidate by a fresh agent that tries to disprove it, `findings.json`, fresh-eyes
   verification, and reports. Profiles follow `--profile` (`quick` / `standard` / `deep`).
3. Verdicts: **confirmed** (complete source trace and an observed local result; only these get a severity,
   calibrated by likelihood × demonstrated impact), **needs validation** (a specific fact outside the source
   decides it; no severity, with the exact check that resolves it), **rejected** (disproved; kept so later
   runs do not repeat it). A missing best practice with no affected principal is a hardening note.
4. `python3 -I scripts/validate-audit.py run <audit-dir>` checks the ledger and findings during execution.
   Before declaring Phase 10 complete, `validate-audit.py complete <audit-dir>` must exit 0 for every repo.
   It also checks final status, report files, unfinished units and candidates missing from `findings.json`.
   Then run the
   `generate-report.py` command in `AGENT-TASK.md`: confirmed findings join the run's report as ordinary
   findings (scanner `audit`, already verified, so Phase 9 skips them) and the report gains a Deep audit
   section with coverage, leads that need validation, gaps and hardening notes. An unfinished or invalid audit
   is shown as such, merges nothing, and never makes an earlier audit finding look fixed.

Safety: source-only by default — nothing from the target runs. Sandboxed local checks need
`JOB_SECURITY_SCAN_AUDIT_EXEC=1` and go only through `scripts/audit-sandbox.py` (no network, read-only
filesystem except the agent's scratch folder, empty environment, CPU/memory/process/time limits; it refuses
to run if any control is missing). Evidence leaves scratch only through `scripts/audit-promote.py`.

## Reports — one folder per run

Every run writes a new folder in the workspace folder (the folder `run-scan.sh` is run from); nothing is
overwritten:

```
security-run-YYYYMMDD-HHMMSS/
├── SUMMARY.md             # what to read first: status, changes, top findings (always under 20 KB)
├── security-report.md     # CRITICAL/HIGH in full with file:line and code; MEDIUM and below counted per rule
├── security-report.json   # index: run info, counts, repos, shard list (schema_version 3,
│                          #   assets/report.schema.json; shai_hulud block = per-target verdict and checks)
├── findings/              # the findings, in compact JSON shards of at most 2,000 rows / 4 MB, sha256 in the index
├── security-report.html   # interactive report (filters, VS Code links, NEW badges, verdicts)
├── run-metadata.json      # what ran, and each repo's commit + dirty flag
├── NEEDS-VALIDATION.md    # after Phase 9: findings a person must settle, with the blocker and a plan
├── triage/                # Phase 9 queue-index.json, batch-NNN.json, verdicts/<fingerprint>.json
├── changed-files.json     # --since only: files in scope per repo
├── .gitignore             # "*" - the folder never gets committed
└── <repo>/ , _host/       # raw output of every tool for this run (+ <repo>/audit/ after --audit)
```

**Changes since last run.** Each report is compared with the newest earlier `security-run-*` folder beside it:
every finding is marked new or unchanged (by a fingerprint that survives code moving down a file), and findings
that disappeared are listed as fixed — only for repos and scanners that ran the same way both times, and never
for a `--since` run. Check any report with `python3 -I scripts/validate-report.py <run>` (every shard is checked
against the size and sha256 in the index). Runs written by v3.0 (`schema_version` 2, one file) are still read.
If the previous report cannot be read, the report says "Change tracking unavailable" and marks nothing fixed.

Every finding is located to **file + line + one line of code**. Secrets show file and line only — never the
value or the line. Caches (vendor advisories, refreshed indicators) live outside the workspace in
`~/.cache/job-security-scan` (`cache-dir:` or `JOB_SECURITY_SCAN_CACHE` to move them, e.g. for CI).
`SECURITY_RUN_ROOT` puts run folders somewhere else. On macOS the HTML report opens automatically.

**HTML report features:**
- **Summary cards** — CRITICAL / HIGH / MEDIUM / LOW counts at a glance
- **Filter bar** — filter by severity, repo, scanner, type (live, no reload)
- **VS Code deep-links** — every `📄 file:line` entry is a `vscode://file/...` link that opens the exact line in VS Code when clicked
- **Package details** — installed version + available fix version per CVE
- **CVE links** — every CVE ID links to NVD or the advisory URL
- **Dark mode** — respects `prefers-color-scheme`
- **Print-friendly** — safe to save as PDF

**Baseline.** Accepted findings go in `security-baseline.json` next to the config (or `--baseline`):

```json
{"version": 1, "entries": [
  {"fingerprint": "3f9c0a1b2c3d4e5f", "reason": "test fixture, never deployed", "expires": "2027-03-31", "owner": "alex"}
]}
```

A reason is required and the fingerprint is the 16-hex one from `security-report.json`; expired entries stop
applying. Accepted findings are listed in their own section with the reason and left out of the counts;
entries that match nothing are flagged. If every CRITICAL/HIGH finding is accepted, the run exits with a
warning (1) instead of a failure (2). A baseline hides nothing silently and never edits a scanned repo.

You can regenerate the three reports of a run without re-scanning:

```bash
python3 .github/skills/job-security-scan/scripts/generate-report.py \
  --results-dir security-run-20261102-153600 --out-dir security-run-20261102-153600 \
  --config .github/skills/job-security-scan/assets/repository.md --workspace .
```

## How to Run

```bash
# Step 1 — install tools (once per machine)
bash .github/skills/job-security-scan/scripts/install-tools.sh

# Step 2 — full scan; reports in ./security-run-<datetime>/ (HTML auto-opens on macOS)
bash .github/skills/job-security-scan/scripts/run-scan.sh

# Scope to one repo
bash .github/skills/job-security-scan/scripts/run-scan.sh --repo om-ddm-backend

# Run one scanner across all repos
bash .github/skills/job-security-scan/scripts/run-scan.sh --scanner trivy

# Fast PR check: only files changed since main, no verification queue
bash .github/skills/job-security-scan/scripts/run-scan.sh --profile quick --since origin/main

# Deepest pass (Trivy LOW, MEDIUM findings verified too)
bash .github/skills/job-security-scan/scripts/run-scan.sh --profile deep

# Was this computer hit by Shai-Hulud? (no config needed)
bash .github/skills/job-security-scan/scripts/run-scan.sh --host

# Shai-Hulud check on every repo plus this computer
bash .github/skills/job-security-scan/scripts/run-scan.sh --scanner shai-hulud --host

# Use a different team's config
bash .github/skills/job-security-scan/scripts/run-scan.sh \
  --config /path/to/other-team/repository.md

# Regenerate the reports of an earlier run (no re-scan)
python3 .github/skills/job-security-scan/scripts/generate-report.py \
  --results-dir security-run-20261102-153600 --out-dir security-run-20261102-153600 \
  --config .github/skills/job-security-scan/assets/repository.md
```

## Security of the skill itself

The scanner reads untrusted repositories, so it is built not to be an attack path:

- **Nothing from a scanned repo runs.** Install hooks, scripts and lockfiles are only read. Docker base images
  are probed only on opt-in (`JOB_SECURITY_SCAN_PROBE_IMAGES=1`) and then sandboxed.
- **Config is data, not code.** Values from `repository.md` are shell-quoted before `run-scan.sh` loads them;
  repo names may only use letters, digits, `.`, `_`, `-` (no `/`, no `..`), or the config is rejected.
- **No secret values are kept.** Gitleaks runs with `--redact`; TruffleHog's raw values are stripped from its
  output; secret findings (Gitleaks, TruffleHog, Trivy, Semgrep secret rules) show file and line only.
- **Network input is constrained.** Fetchers use HTTPS to allowlisted hosts only; advisory feeds with DTDs or
  entity declarations are refused; text copied into GitHub issues cannot @-mention people or inject HTML.
- **Deep audit is source-only by default.** Target code runs only with `JOB_SECURITY_SCAN_AUDIT_EXEC=1`,
  only via `scripts/audit-sandbox.py`, and only when every sandbox control can be enforced.
- **Pinned supply chain.** Installer and CI pin every tool and every GitHub Action (actions by commit SHA,
  checkouts without persisted credentials). `references/ci-workflow.md` uses `trivy-action` `0.35.0`; tags
  `0.0.1`-`0.34.2` were hijacked in March 2026 (GHSA-69fq-xp46-6x23) — if you copied an older version of that
  template, update it and rotate the CI secrets it could reach.

## Output Format

`run-scan.sh` writes the report itself; the agent does not compose one. After the run:

1. If a deep audit was prepared, use `references/audit/WORKFLOW.md` to schedule Phase 10 with Phase 9.
   Otherwise run Phase 9 unless the profile is `quick` or the user asked to skip it.
   Regenerate the report with `--keep-verdicts`, as `AGENT-TASK.md` says.
   Check Phase 9 with `triage.py status <run> --require-complete` and Phase 10 with
   `validate-audit.py complete <audit-dir>` for every requested repo. A valid report can describe an
   incomplete run. If either check fails, report the incomplete phase, exact blocker and resume action,
   not a completed deep audit. Never replace pending work with blanket `needs_validation` verdicts or
   empty findings merely to pass a check.
2. Read `security-run-<datetime>/SUMMARY.md` (the last console line names the folder). Do not open
   `security-report.json` or `findings/` directly; they can be many megabytes.
3. Reply with a short summary: the per-repo status table, the Shai-Hulud check row for every target (verdict
   and what was checked; say plainly if it errored or did not run), the changes since the last run, the confirmed
   Critical and High findings as `file:line` with their rule, how many need validation, were dismissed or are
   still pending, any deep-audit findings (`file:line`, severity) and leads, and the paths of the report files.
4. Stop after presenting the report and asking the optional DefectDojo question below. Do not offer, propose or ask
   to fix anything, and do not edit any scanned file — the remediation guidance in the report is for the reader.

Secrets: never print secret values or the code line of a secret finding, only `file:line` and the rule.

## DefectDojo export

After presenting each completed scan, ask whether the user wants to import its
report into DefectDojo. If they agree, ask for the exact DefectDojo base URL
before uploading. A direct upload request counts as consent, but still requires
the URL. Never assume localhost, `DEFECTDOJO_URL`, or a guessed address. Do not
upload until both consent and the URL are explicit.

If the user declines, stop. Otherwise use `scripts/import-defectdojo.py` with
the supplied URL; see [references/defectdojo.md](references/defectdojo.md) for
dry-run, authentication and upload commands. Import is opt-in and never part of
the scan itself. Recover full scanner metadata from adjacent JSON by default;
use `--update-existing` when repairing older imports. Include redacted
non-secret excerpts only with explicit user approval via `--include-code`.
Preserve verification status; never upload raw secret output or automatically
close absent findings.

## CI Integration

See [references/ci-workflow.md](references/ci-workflow.md) for a ready-to-paste
GitHub Actions workflow that reads `repository.md` automatically.

## Adding This Skill to a New Team

1. Copy `.github/skills/job-security-scan/` to the new team's repo
2. Edit `assets/repository.md` — update `team`, `org`, `ci-runner`, and `repos`
3. Commit — the skill is self-contained and works immediately
