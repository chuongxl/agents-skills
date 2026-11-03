---
name: job-security-scan
description: >
  Free, report-only security scan of a team's repos, configured by one repository.md file. Runs Gitleaks
  (secrets in git history), Trivy (CVEs, Dockerfile misconfig), Semgrep (SAST), Hadolint, OSV-Scanner,
  TruffleHog (live credential check), vendor advisories and an offline Shai-Hulud worm check (repos and,
  with --host, this computer). Optional deep audit (--audit): an agent-driven, coverage-led review for
  logic flaws scanners miss (authorization, tenant isolation, CI trust, injection), where every finding is
  independently re-verified and leads that need an outside fact stay "needs validation". Every run writes
  md/json/html reports with file:line, what is new or fixed since earlier runs, and a baseline for
  accepted findings. Use to scan for vulnerabilities, secrets, malware or misconfigurations, for a security
  audit or pen-test of code, to set up a CI security pipeline, or to check for Shai-Hulud.
compatibility: >
  Requires bash, git, Python 3.8+ (pre-installed on most systems — used
  only to parse repository.md, no pip packages needed). Security tools
  auto-installed via Homebrew (macOS) or curl/apt (Linux) on first run.
  Network access required for tool install and CVE DB download on first run.
  Subsequent runs use cached DB and installed binaries.
license: MIT
metadata:
  author: one-om-ddm-team
  version: "3.0"
  config-file: assets/repository.md
allowed-tools: bash glob grep view create edit
---

# Job Security Scan

Generic, config-driven security scanner for any multi-repo workspace.

> **Report only.** This skill finds and reports problems; it never fixes them. Never modify, patch, upgrade,
> delete or commit anything in a scanned repo, and never offer, ask or attempt to fix findings. Remediation
> appears only as guidance text in the report (`references/remediation.md`). End after presenting the report.

## Modes

- **Guidance** — a security question, a focused review of one file or lead, or triage: answer from the
  references (`references/audit/ATTACK-CLASSES.md` and its companions for code-level questions). Do not run
  the scan or write files.
- **Scan** — "scan", "check for secrets/vulnerabilities/Shai-Hulud", CI setup: run `run-scan.sh` (Phases 1–8).
- **Deep audit** — "audit / pen-test this code", "full / deep security review": run the scan with `--audit`
  (or `--scanner audit` alone), then follow `references/audit/WORKFLOW.md` (Phase 9).

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
| `--scanner NAME` | `--scanner trivy` | Run one scanner only |
| `--host` | `--host` | Also check this computer for Shai-Hulud; alone, only the host check runs |
| `--audit` | `--audit` | Also prepare the deep audit (Phase 9) for each repo |
| `--profile` | `--profile quick` | Deep-audit breadth: `quick`, `standard` (default), `deep` |
| `--since REF` | `--since origin/main` | Deep audit only the files changed since a git ref |
| `--budget N` | `--budget 40` | Deep-audit cap on agent invocations |
| `--baseline FILE` | `--baseline ./security-baseline.json` | Accepted findings (default: `security-baseline.json` next to the config, if present) |
| *(none)* | | Full scan — all scanners, all active repos from config |

Short aliases: `-r` for `--repo`, `-s` for `--scanner`

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

## Phase 9 — Deep Audit (agent-driven, opt-in)

Scanners match known-bad patterns; they cannot tell that `GET /notes/:id` forgot the owner check its
`DELETE` sibling has. The deep audit is the method of
[cloudflare/security-audit-skill](https://github.com/cloudflare/security-audit-skill) (MIT), copied into
`references/audit/` and adapted to this skill:

1. `run-scan.sh --audit` (or `--scanner audit`) prepares `security-run-<datetime>/<repo>/audit/`: run
   metadata with the commit and dirty flag, profile, scope (`--since`), budget, earlier audits of the repo,
   reconnaissance hints, and `AGENT-TASK.md`.
2. The agent then runs the six phases in `references/audit/WORKFLOW.md`: reconnaissance and a deterministic
   coverage ledger, coverage-led hunting with isolated agents and 11 attack-class files, independent
   validation of every candidate by a fresh agent that tries to disprove it, `findings.json`, fresh-eyes
   verification, and reports.
3. Verdicts: **confirmed** (complete source trace and an observed local result; only these get a severity,
   calibrated by likelihood × demonstrated impact), **needs validation** (a specific fact outside the source
   decides it; no severity, with the exact check that resolves it), **rejected** (disproved; kept so later
   runs do not repeat it). Missing best practice with no affected principal is a hardening note, not a finding.
4. `python3 -I scripts/validate-audit.py run <audit-dir>` checks the ledger and findings against
   `assets/audit/findings.schema.json` and the method's rules; regenerating the reports then merges the
   confirmed findings (🧠) into the run's reports, with coverage, gaps, leads and hardening notes.

Safety: source-only by default — nothing from the target runs. Sandboxed local checks need
`JOB_SECURITY_SCAN_AUDIT_EXEC=1` and go only through `scripts/audit-sandbox.py` (no network, read-only
filesystem except the agent's scratch folder, empty environment, CPU/memory/process/time limits; it refuses
to run if any control is missing). Evidence leaves scratch only through `scripts/audit-promote.py`.
Additive across runs: earlier audits of the same repo are used to target gaps and re-check changed code.

## Reports — one folder per run

Every run writes a new folder in the workspace folder (the folder `run-scan.sh` is run from); nothing is
overwritten:

```
security-run-YYYYMMDD-HHMMSS/
├── security-report.md     # summary + findings by severity, each with file:line and the line of code
├── security-report.json   # same data, machine-readable (schema_version 1)
├── security-report.html   # interactive report (filters, VS Code links)
├── run-metadata.json      # what ran, and each repo's commit + dirty flag
├── .gitignore             # "*" - the folder never gets committed
└── <repo>/ , _host/       # raw output of every tool for this run (+ <repo>/audit/ for the deep audit)
```

Every finding is located to **file + line + one line of code**. Secrets show file and line only — never the
value or the line. Caches (vendor advisories, refreshed indicators) live outside the workspace in
`~/.cache/job-security-scan` (`cache-dir:` or `JOB_SECURITY_SCAN_CACHE` to move them, e.g. for CI).
`SECURITY_RUN_ROOT` puts run folders somewhere else. On macOS the HTML report opens automatically.

**Across runs.** Every finding has a stable `fingerprint` (scanner, repo, rule, file, package, and the code
line for code findings — never the line number or version). Each report compares every repo × scanner pair
with the latest earlier run in which that pair ran, and marks findings 🆕 new or ⏳ still open and lists
✅ fixed ones; a narrower run never makes other scanners' findings look fixed.

**Baseline.** Accepted findings go in `security-baseline.json` next to the config (or `--baseline`):

```json
{"version": 1, "entries": [
  {"fingerprint": "semgrep:3f9c0a1b2c3d4e5f", "reason": "test fixture, never deployed", "expires": "2027-03-31", "owner": "alex"}
]}
```

A reason is required; expired entries stop applying. Accepted findings are listed in their own section and
left out of the counts; if every CRITICAL/HIGH finding is accepted, the run exits with a warning (1)
instead of a failure (2). Copy fingerprints from `security-report.json`.

`security-report.json` is `schema_version` 2: v1 fields plus `fingerprint`, `diff_status`, `first_seen`,
`verdict` and `details` per finding, and top-level `diff`, `baseline`, `audit` and `run_options`.

**HTML report features:**
- **Summary cards** — CRITICAL / HIGH / MEDIUM / LOW counts at a glance
- **Filter bar** — filter by severity, repo, scanner, type (live, no reload)
- **VS Code deep-links** — every `📄 file:line` entry is a `vscode://file/...` link that opens the exact line in VS Code when clicked
- **Package details** — installed version + available fix version per CVE
- **CVE links** — every CVE ID links to NVD or the advisory URL
- **Dark mode** — respects `prefers-color-scheme`
- **Print-friendly** — safe to save as PDF

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

# Was this computer hit by Shai-Hulud? (no config needed)
bash .github/skills/job-security-scan/scripts/run-scan.sh --host

# Scanners plus the deep audit of one repo, only code changed since main
bash .github/skills/job-security-scan/scripts/run-scan.sh --repo om-ddm-backend --audit --since origin/main

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

1. Read `security-run-<datetime>/security-report.md` (the last console line names the folder).
2. Reply with a short summary: the per-repo status table, how many findings are new and fixed since the
   last run, the Critical and High findings as `file:line` with their rule, and the paths of the three
   report files. If a deep audit was prepared, run it now (Phase 9) before replying, and add its confirmed
   findings and the number of needs-validation leads.
3. Stop there. Do not offer, propose or ask to fix anything, and do not edit any scanned file — the
   remediation guidance in the report is for the reader.

Secrets: never print secret values or the code line of a secret finding, only `file:line` and the rule.

## CI Integration

See [references/ci-workflow.md](references/ci-workflow.md) for a ready-to-paste
GitHub Actions workflow that reads `repository.md` automatically.

## Adding This Skill to a New Team

1. Copy `.github/skills/job-security-scan/` to the new team's repo
2. Edit `assets/repository.md` — update `team`, `org`, `ci-runner`, and `repos`
3. Commit — the skill is self-contained and works immediately
