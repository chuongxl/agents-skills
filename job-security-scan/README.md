# Job Security Scan

## Overview

Job Security Scan is a comprehensive, zero-cost security scanning skill for multi-repository workspaces. It combines six industry-standard security tools into a single, configurable pipeline:

- **Gitleaks** — Detects secrets in git history
- **Trivy** — Scans dependencies for CVEs and Docker misconfigurations
- **Semgrep** — Performs static analysis for TypeScript/NestJS/OWASP vulnerabilities
- **Hadolint** — Validates Docker best practices
- **OSV-Scanner** — Checks Google's transitive vulnerability database
- **TruffleHog** — Performs live credential verification

All tools are free, open-source, and configurable. Security findings are organized by severity and repo, with structured JSON output for programmatic processing.

### When to Use

- Initial security audit across a team's repositories
- Pre-deployment security validation
- CI/CD integration for continuous security monitoring
- Compliance scanning for specific tech stacks
- Investigation of security incidents or suspected leaks

### Key Features

1. **Config-Driven** — All team and repo details in a single `repository.md` file
2. **Selective Scanning** — Scan all repos, one specific repo, or one specific scanner
3. **Free Tools** — No vendor lock-in or licensing costs
4. **Stack-Aware** — Enables only relevant tools based on tech stack (TypeScript, Python, Go, etc.)
5. **Structured Output** — JSON results for easy CI/CD integration
6. **Auto-Install** — Security tools auto-install on first run via Homebrew (macOS) or apt/curl (Linux)
7. **Allowlist Support** — Exclude false positives and intentional secrets from scanning
8. **Verified Findings** — Serious findings are re-checked by an independent verifier agent: confirmed (with
   calibrated severity), needs validation (with the exact missing fact), or dismissed (with the reason)
9. **Changes Since Last Run** — Each report marks findings new or unchanged and lists what was fixed
10. **Profiles and Scope** — `--profile quick|standard|deep` and `--since <git-ref>` for fast PR checks
11. **Deep Audit (opt-in)** — `--audit`: agent-driven, coverage-led review for logic flaws scanners cannot see, every finding independently re-verified
12. **Baseline** — Accept known findings with a reason and an expiry date

Diagrams (open in a browser): [architecture](docs/diagrams/job-security-scan-architecture.html) ·
[run flow](docs/diagrams/job-security-scan-run-flow.html).
What each scanner does and why it is in the set: [references/scanners.md](references/scanners.md).

## Quick Start

### 1. Install

Copy the skill to your workspace:

```bash
# For GitHub Copilot in a repository
cp -r job-security-scan .github/skills/

# For Claude local usage
cp -r job-security-scan ~/.claude/skills/

# For local/central skills location
cp -r job-security-scan ~/.agents/skills/
```

### 2. Configure

Edit the configuration file in the skill folder:

```bash
# Edit repository.md to add your repos
nano job-security-scan/assets/repository.md
```

Key configuration:
- `team` — Team identifier for reporting
- `org` — GitHub organization name
- `repos[]` — List of repositories to scan (with `active: true/false`)
- Languages and lockfiles are detected automatically (`ecosystems/*.json`); `stack` and `package-manager` are deprecated
- `fail-on-severity` — Build failure threshold (CRITICAL, HIGH, MEDIUM, LOW)

### 3. Run Scan

From the skill directory or a parent that contains it:

```bash
# Full scan: all tools, all active repos
bash job-security-scan/scripts/run-scan.sh

# Single repo only
bash job-security-scan/scripts/run-scan.sh --repo my-backend

# Single scanner only
bash job-security-scan/scripts/run-scan.sh --scanner trivy
```

### 4. Review Results

Every run creates its own folder in the workspace folder, so earlier runs are never overwritten:

```
security-run-20261102-153600/
├── SUMMARY.md             # short summary to read first (under 20 KB)
├── security-report.md     # CRITICAL/HIGH with file:line and the line of code; lower severities counted
├── security-report.json   # index (run info, counts, shard list), machine-readable
├── findings/              # every finding, in compact JSON shards
├── security-report.html   # interactive report
├── .gitignore             # "*" - never committed by accident
└── <repo-name>/           # raw tool output: gitleaks.json, trivy.json, semgrep.json, osv.json, shai-hulud.json ...
```

Secrets are reported with file and line only, never the value. The skill only reports — it never changes code.

Caches (vendor advisories, refreshed indicators) live in `~/.cache/job-security-scan`, not in the workspace;
set `cache-dir:` in `repository.md` or `JOB_SECURITY_SCAN_CACHE` to move them. An old `.security-scan-results/`
folder from earlier versions is no longer used and can be deleted.

## Detailed Features

### 1. Gitleaks — Secret Detection

Scans the entire git history for secrets (API keys, tokens, credentials). Uses `assets/gitleaks.toml` for:
- Pattern-based detection
- Team-specific allowlists (e.g., `.env.example` files)
- False positive suppression

Any secret finding is **CRITICAL** — there is no severity ladder for leaks.

**Output:** `gitleaks.json` with full commit history, file paths, and secret types

### 2. Trivy — Vulnerability & Misconfig Scan

Scans dependency files (`yarn.lock`, `package.json`, `go.sum`, `requirements.txt`, etc.) and Docker images:
- Checks against NVD (National Vulnerability Database) and GitHub Advisory Database
- Identifies Dockerfile misconfigurations (exposed secrets, root user, etc.)
- Reports CVE details with CVSS scores and remediation links

**Stack-Aware:** Only activates for repos with the matching package manager

**Output:** `trivy.json` with CVE details, severity, and affected versions

### 3. Semgrep — Static Analysis

Language-specific code analysis (SAST) for security and quality issues:
- TypeScript/JavaScript: React best practices, dependency vulnerabilities
- NestJS: Authentication, validation, injection vulnerabilities
- General: OWASP Top 10 patterns (SQL injection, XSS, etc.)

Rulesets follow the languages detected in each repo (see `references/ecosystems.md`).

**Output:** `semgrep.json` with issue type, severity, code snippet, and fix guidance

### 4. Hadolint — Docker Best Practices

Validates Dockerfile syntax and best practices:
- Base image recommendations
- Security concerns (privileged containers, root user)
- Efficiency patterns (layer caching, multi-stage builds)

Only runs on repos with `has-dockerfile: true` in configuration.

**Output:** `hadolint.json` with line-by-line issues and recommendations

### 5. OSV-Scanner — Transitive Vulnerabilities

Google's database for supply-chain vulnerabilities:
- Detects vulnerable transitive dependencies
- Covers npm, pip, Go, Rust, and Java ecosystems
- Often catches issues missed by direct scanners

**Output:** `osv-scanner.json` with affected transitive paths

### 6. TruffleHog — Live Credential Verification

Different from Gitleaks (which scans git history), TruffleHog verifies live credentials:
- Detects if an exposed secret is currently valid
- Prioritizes urgent remediation for active credentials
- Supports multiple credential types

**Output:** `trufflehog.json` with verified/unverified status

### 7. Shai-Hulud — Supply-Chain Worm Check (repo and laptop)

A fast, offline answer to "were we hit by the Shai-Hulud npm/PyPI worm?":
- **Affected** (CRITICAL): a known compromised release (lockfiles, `node_modules`, PyPI pins, global
  installs, npm cache), the worm's payload/stager file in a package, a planted workflow or persistence
  file, or a worm marker string
- **Suspicious** (HIGH/MEDIUM): an install hook that reads credentials *and* sends data out, pipes a
  download into a shell, runs heavily obfuscated code, or downloads `bun`/TruffleHog
- **Laptop mode** (`--host`): projects under your home directory, global installs, the npm cache, and a
  list of credential stores to rotate if affected (values are never read or printed)
- Never runs npm/node/pip; benign hooks (`node-gyp`, `husky`, esbuild...) are allowlisted

**Output:** `shai-hulud.json` per repo, `_host/shai-hulud.json` for this computer (report: "this machine").
Every report has a **🪱 Shai-Hulud check** section: one row per repo and for this machine with the verdict
(AFFECTED / SUSPICIOUS / CLEAN / ERROR / not run), what was checked (dependency files, packages, install hooks,
workflows; projects, global installs and npm cache for the host), the indicator data version and a link to the raw
output, so a clean result can be checked and a failed check is never silent.
Indicator data and sources: [references/ioc-data.md](references/ioc-data.md). If affected:
[references/remediation.md](references/remediation.md#-shai-hulud-if-affected).

### 8. Independent Verification, Run-to-Run Changes, Report Schema

- **Verification (agent step, Phase 9):** `scripts/triage.py queue` lists the findings to check (`standard`:
  CRITICAL + HIGH, `deep`: also MEDIUM) with a redacted ±15-line context, one item per root cause (same advisory
  + package + version, or same misconfig rule, in one repo), most severe first, capped at `--limit 25` with the
  pending count reported (`--all`, `--repo NAME`, `--no-group`); each item goes to a fresh verifier agent
  that tries to disprove it from source only (no edits, no running repo code, no network). `triage.py next` hands
  out one item at a time, `triage.py record` saves each verdict, and `triage.py apply`
  merges them all-or-nothing and regenerates the reports plus `NEEDS-VALIDATION.md`. Prompt, verdict
  format and severity anchors: [references/verification.md](references/verification.md).
- **Changes:** every finding has a fingerprint that survives code moving within a file; reports compare with
  the previous `security-run-*` folder (new / unchanged / fixed), and verdicts carry over while code is unchanged.
- **Schema:** `security-report.json` is a `schema_version` 3 index with the findings in `findings/` shards
  ([assets/report.schema.json](assets/report.schema.json)); `python3 -I scripts/validate-report.py <run>` checks
  the index and every shard (exit 0 valid, 1 invalid, 2 unreadable). v2 single-file reports are still read.

### 9. Deep Audit — Logic Flaws Scanners Miss (opt-in, Phase 10)

Scanners match known-bad patterns. They cannot see that one route checks the note's owner and its
sibling does not, that a tenant ID comes from the request body, or that a CI workflow runs pull-request code
with a publish token. The deep audit is the method of
[cloudflare/security-audit-skill](https://github.com/cloudflare/security-audit-skill) (MIT), adapted to
this skill (provenance: [references/audit/NOTICE.md](references/audit/NOTICE.md)):

- **Reconnaissance** maps trust boundaries and builds a deterministic **coverage ledger** of entry surface ×
  boundary × subsystem × attack class.
- **Hunting** assigns isolated agents to ledger units with attack-class prompts (web/auth, AI/LLM,
  client-side, supply chain/CI, cloud, RPC/messaging, data isolation, resource exhaustion, desktop/IPC,
  memory safety); coverage critics look for gaps.
- **Validation**: a fresh agent tries to disprove every candidate; a second fresh agent re-checks every
  final record.
- **Verdicts**: *confirmed* (with severity), *needs validation* (no severity; names the missing fact and
  the check that settles it), *rejected* (kept so later runs do not repeat it).
- **Report**: confirmed findings join the scanner findings as ordinary findings (scanner `audit`, already
  verified); a Deep audit section lists coverage, gaps, leads and hardening notes. An unfinished audit merges
  nothing.

```bash
bash job-security-scan/scripts/run-scan.sh --audit                       # scanners + deep audit
bash job-security-scan/scripts/run-scan.sh --scanner audit --profile quick --since origin/main
```

The script prepares the audit; the agent then follows
[references/audit/WORKFLOW.md](references/audit/WORKFLOW.md). Source-only by default. Sandboxed local checks
need `JOB_SECURITY_SCAN_AUDIT_EXEC=1` and run only through `scripts/audit-sandbox.py` (Linux namespaces:
no network, read-only filesystem except scratch, empty environment, resource limits — it refuses to run
if any control is missing).

### 10. Baseline (accepted findings)

Known, accepted findings go in `security-baseline.json` next to `repository.md` (or `--baseline FILE`):
`{"version": 1, "entries": [{"fingerprint": "<16 hex from security-report.json>", "reason": "...",
"expires": "YYYY-MM-DD", "owner": "..."}]}`. They are listed in their own report section with the reason and
left out of the counts; expired entries stop applying; entries matching nothing are flagged. If every
CRITICAL/HIGH finding is accepted, the run exits 1 (warning) instead of 2.

## Installation & Setup

### Platform-Specific Setup

#### macOS (Homebrew)

```bash
# Manual install (if auto-install doesn't work)
brew install gitleaks trivy semgrep hadolint osv-scanner trufflehog

# Verify installation
gitleaks version
trivy version
```

#### Linux (Ubuntu/Debian)

```bash
# Auto-install runs via apt and curl
# Manual install:
sudo apt-get install -y gitleaks trivy semgrep hadolint

# For OSV-Scanner and TruffleHog, curl is used:
curl -sSfL https://raw.githubusercontent.com/google/osv-scanner/main/scripts/install.sh | sh
```

#### Docker

```bash
docker run -v $(pwd):/workspace aquasec/trivy fs /workspace
docker run -v $(pwd):/repo zricethezav/gitleaks detect --source /repo -v
```

### Configuration Requirements

Before running, create/edit `job-security-scan/assets/repository.md`:

```markdown
# Team Configuration

team: my-team
org: my-github-org
monorepo-root: .
ci-runner: ubuntu-latest
repos:
  - name: api-backend
    active: true
    has-dockerfile: true
  - name: web-frontend
    active: true
    has-dockerfile: false
  - name: deprecated-service
    active: false

fail-on-severity: HIGH
# cache-dir: .scan-cache          # optional; default ~/.cache/job-security-scan
secret-allowlist-paths:
  - '**/.env.example'
  - '**/example/**'
```

## Compatibility Matrix

| Platform | Supported | Notes |
|----------|-----------|-------|
| GitHub Copilot CLI | ✅ Yes | Skill auto-discovered from `~/.agents/skills/` |
| Claude Code | ✅ Yes | Register SKILL.md as `.claude/commands/job-security-scan.md` |
| Local Usage | ✅ Yes | Direct bash invocation via `scripts/run-scan.sh` |
| OpenCode | ✅ Yes | Place SKILL.md in `.opencode/instructions/job-security-scan.md` |
| GitHub Actions | ✅ Yes | Copy to `.github/skills/` and invoke from workflow |
| GitLab CI | ✅ Yes | Requires bash, git, Python 3.8+ (no agent framework needed) |

### System Requirements

- **OS:** macOS, Linux (Ubuntu, Debian, CentOS)
- **Runtime:** Bash 4.0+, Python 3.8+ (for config parsing only — no pip packages)
- **Network:** Required on first run for tool install and CVE DB download
- **Disk:** ~500 MB for tools and cached databases (reused on subsequent runs)

## Usage Examples

### Example 1: Full Security Audit

```bash
cd my-workspace
bash job-security-scan/scripts/run-scan.sh

# Reports in the newest security-run-<datetime>/ folder
cat "$(ls -1d security-run-* | tail -1)/security-report.md"
```

### Example 2: CI/CD Integration

```yaml
# .github/workflows/security-scan.yml
name: Security Scan
on: [push, pull_request]

jobs:
  security:
    runs-on: ubuntu-latest
    steps:
      - uses: actions/checkout@v3
      - uses: actions/cache@v4            # optional: reuse vendor advisories between runs
        with:
          path: .scan-cache
          key: job-security-scan-${{ github.run_id }}
          restore-keys: job-security-scan-
      - name: Run security scan
        env:
          JOB_SECURITY_SCAN_CACHE: .scan-cache
        run: bash .github/skills/job-security-scan/scripts/run-scan.sh
      - name: Upload reports
        if: always()
        uses: actions/upload-artifact@v4
        with:
          name: security-reports
          path: security-run-*/
```

### Example 3: Single-Repo Scan

```bash
# Scan only the backend repository
bash job-security-scan/scripts/run-scan.sh --repo backend-api
```

### Example 4: Specific Scanner

```bash
# Run only Semgrep (fast SAST) without full dependency scan
bash job-security-scan/scripts/run-scan.sh --scanner semgrep
```

### Example 5: Was This Repo or Laptop Hit by Shai-Hulud?

```bash
# This computer only (no repository.md needed)
bash job-security-scan/scripts/run-scan.sh --host

# Every configured repo plus this computer
bash job-security-scan/scripts/run-scan.sh --scanner shai-hulud --host

# Standalone, any folder; exit 0 clean, 1 suspicious, 2 affected
python3 -I job-security-scan/scripts/shai-hulud-scan.py --repo ./my-service

# Refresh indicators from the published lists (optional; used automatically)
python3 -I job-security-scan/scripts/fetch-iocs.py --out ~/.cache/job-security-scan/ioc
```

In CI, add a step before `npm ci` so a compromised release fails the build before its install hook runs:

```yaml
- name: Shai-Hulud check
  run: python3 -I .github/skills/job-security-scan/scripts/shai-hulud-scan.py --repo . --format text
```

### Example 6: Fast PR Check and Deep Audit

```bash
# Only files changed since main; Gitleaks on the working tree, OSV, Shai-Hulud; no verification queue
bash job-security-scan/scripts/run-scan.sh --profile quick --since origin/main

# Scanners plus the deep audit of changed code only
bash job-security-scan/scripts/run-scan.sh --audit --since origin/main

# Everything, Trivy down to LOW, MEDIUM findings queued for verification too
bash job-security-scan/scripts/run-scan.sh --profile deep
python3 -I job-security-scan/scripts/triage.py queue security-run-<datetime>
```

## Configuration

### Environment Variables

```bash
# Optional tuning (if tools need custom paths)
export GITLEAKS_CONFIG_PATH=/path/to/gitleaks.toml
export TRIVY_OFFLINE_DB_PATH=/path/to/trivy.db
export SEMGREP_CONFIG_PATH=/path/to/semgrep.yml
```

### Custom Allowlists

Edit `job-security-scan/assets/gitleaks.toml` to add team-specific false positives:

```toml
[allowlist]
paths = [
  "assets/example-secrets.md",
  "docs/integration-examples.md",
]
commits = [
  "badc0ffee",  # Commit hash to exclude
]
```

## Troubleshooting

### Issue: "tools not found" on first run

**Solution:** Ensure network access is available and run with sufficient privileges:

```bash
sudo bash job-security-scan/scripts/install-tools.sh
```

### Issue: Gitleaks takes too long on large repos

**Solution:** Limit history depth or use shallow clones:

```bash
git clone --depth=50 <repo-url>
bash job-security-scan/scripts/run-scan.sh
```

### Issue: False positives in Semgrep

**Solution:** Create a `.semgrep.yml` allowlist in the repo root:

```yaml
rules:
  - id: allowlist-test-secret
    pattern: test_secret
    severity: INFO  # Don't fail builds
```

### Issue: Trivy database is stale

**Solution:** Clear cache and update:

```bash
rm -rf ~/.cache/trivy
bash job-security-scan/scripts/run-scan.sh  # Re-downloads DB
```

### Issue: Too many findings to verify on a large multi-repo scan

**Solution:** `triage.py queue` already groups repeated root causes and stops at 25 items. Work in batches:
apply the verdicts, queue again, and use `--repo NAME` to finish one repository at a time. The pending count
in the summary is the work left; pending findings are not clean.

## Version History

- **v3.2** (current) — Large reports no longer break: `security-report.json` is a schema v3 index with the
  findings in sha256-checked `findings/` shards (v2 reports still read; no single file has to hold every
  finding); a bounded `SUMMARY.md` (under 20 KB); `security-report.md` lists CRITICAL/HIGH in full and counts
  lower severities; Phase 9 runs one item at a time (`triage.py next` / `record`, `apply` without a file) over
  the grouped, `--limit`-bounded queue; an unreadable previous report is reported as "Change tracking
  unavailable" instead of making every finding new, and `--keep-verdicts` fails loudly
- **v3.1** — Large scans: report size limit raised from 5 MiB to 64 MiB to match the 20,000-finding
  schema cap (a 7,000-finding scan no longer breaks triage, validation and verdict carry-over), and an oversize
  report is now an error instead of a silent skip; `triage.py queue` groups one root cause per repo into one
  verifier item, orders by severity, enforces the 25-item budget (`--limit`, `--all`), filters with `--repo`
  and reports the pending count; `apply` shares a group verdict with its members
- **v3.0** — Deep audit (Phase 10, `--audit`) adapted from cloudflare/security-audit-skill: coverage
  ledger, isolated hunters, adversarial validation, confirmed / needs-validation / rejected verdicts, Python
  validators, optional sandbox and evidence promotion; confirmed audit findings join the report as verified
  findings; baseline of accepted findings (`security-baseline.json`); commit and dirty flag per repo
  (`run-metadata.json`); a semgrep run that writes no output is reported as not scanned instead of clean
- **v2.6** — Shai-Hulud check section in every report (per-target verdict, what was checked,
  indicator version, raw-output link, error / not-run states); the scanner records what it checked
- **v2.5** — Independent verification of findings (confirmed / needs validation / dismissed, calibrated
  severity, `triage.py`), changes since the last run (fingerprints, fixed list, carried verdicts), `--profile`
  and `--since`, report schema v2 with `validate-report.py`; ideas adapted from Cloudflare's security-audit skill (MIT)
- **v2.4** — Security hardening of the skill itself: pinned and checksum-verified tool installs, SHA-pinned CI actions (template moved off hijacked `trivy-action` tags), config/repo-name injection fixed, secret values stripped from raw output, opt-in sandboxed image probe, verified TruffleHog secrets fail the scan
- **v2.3** — Per-run `security-run-<datetime>/` folder with Markdown, JSON and HTML reports; every finding located to file, line and code; caches moved out of the workspace; report-only rule
- **v2.2** — Shai-Hulud supply-chain worm check (`--scanner shai-hulud`, `--host` laptop mode)
- **v2.1** — Runtime and image checks
- **v2.0** — Multi-tool unified pipeline, config-driven, zero-install for free tools
- **v1.0** — Gitleaks-only security scan

## License & Attribution

MIT License. Maintained by the security-focused engineering team.

The verification contract, verifier prompt and severity anchors in `references/verification.md` are adapted from
Cloudflare's [security-audit skill](https://github.com/cloudflare/security-audit-skill), MIT License,
Copyright (c) 2025-2026 Cloudflare, Inc. The deep-audit method in `references/audit/` and
`assets/audit/findings.schema.json` is copied from the same project (provenance:
[references/audit/NOTICE.md](references/audit/NOTICE.md)). License text in
[references/third-party/cloudflare-security-audit-LICENSE](references/third-party/cloudflare-security-audit-LICENSE).
