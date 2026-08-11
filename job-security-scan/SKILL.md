---
name: job-security-scan
description: >
  Run a comprehensive, 100% free security scan across any team's service
  repos. Team identity, repo list, tech stack, CI runner, and allowlists
  are all read from a single repository.md config file — no hardcoded values
  in the skill itself. Combines Gitleaks (secrets in git history), Trivy
  (CVE + Dockerfile misconfig), Semgrep (SAST for TypeScript/NestJS/OWASP),
  Hadolint (Dockerfile best practices), OSV-Scanner (Google transitive CVE
  DB), and TruffleHog (live credential verification). Produces a structured
  security report per repo. Use when asked to scan for vulnerabilities,
  secrets, malware, misconfigurations, supply chain issues, or to set up a
  CI security pipeline. Supports --repo for single-repo scope and --scanner
  for single-tool runs.
compatibility: >
  Requires bash, git, Python 3.8+ (pre-installed on most systems — used
  only to parse repository.md, no pip packages needed). Security tools
  auto-installed via Homebrew (macOS) or curl/apt (Linux) on first run.
  Network access required for tool install and CVE DB download on first run.
  Subsequent runs use cached DB and installed binaries.
license: MIT
metadata:
  author: one-om-ddm-team
  version: "2.0"
  config-file: assets/repository.md
allowed-tools: bash glob grep view create edit
---

# Job Security Scan

Generic, config-driven security scanner for any multi-repo workspace.

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
| `package-manager` | Determines lockfile type | `yarn` |
| `stack` | Controls Semgrep rulesets | `[typescript, nodejs, nestjs]` |
| `repos[].name` | Repo directory name | `om-ddm-backend` |
| `repos[].active` | Include in scan | `true` / `false` |
| `repos[].has-dockerfile` | Run Hadolint | `true` / `false` |
| `fail-on-severity` | Build failure threshold | `HIGH` |
| `secret-allowlist-paths` | Paths exempt from secret scan | `**/.env.example` |
| `output-dir` | Where to write scan results | `.security-scan-results` |

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
| *(none)* | | Full scan — all scanners, all active repos from config |

Short aliases: `-r` for `--repo`, `-s` for `--scanner`

## Phase 0 — Parse Config & Install Tools

Load team/repo config from `repository.md`, then install any missing tools:

```bash
# Parse config (Python 3 std-lib only — no pip needed)
eval "$(python3 scripts/parse-config.py assets/repository.md)"

# Install missing tools based on stack + repo config
bash scripts/install-tools.sh
```

`install-tools.sh` reads the config to skip irrelevant tools:
- **Hadolint** only installed if any repo has `has-dockerfile: true`
- **Semgrep** only installed if stack includes TypeScript/JavaScript
- **OSV-Scanner** only installed if `package-manager` is yarn/npm/pnpm

## Phase 1 — Secret Detection (Gitleaks)

Scans full git history of every active repo using DDM-specific allowlists
from `assets/gitleaks.toml`. Any finding is **CRITICAL** — secrets have no
severity ladder.

## Phase 2 — CVE + Dockerfile + Misconfig (Trivy)

Scans `yarn.lock` / `package.json` for CVEs against NVD + GitHub Advisory DB.
Checks Dockerfiles against CIS benchmarks. Severity threshold from config
`fail-on-severity`. Uploads SARIF to GitHub Security tab when run in CI.

## Phase 3 — SAST (Semgrep)

Semgrep rulesets are derived automatically from the `stack` field in
`repository.md`. Ruleset mapping:

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

Google's OSV-Scanner checks `yarn.lock` against the OSV.dev DB — catches
transitive dependencies that Trivy sometimes misses.

## Phase 6 — Verified Secret Detection (TruffleHog)

Scans git history and **actively verifies** whether found credentials are
still valid via live API calls. Reports `VERIFIED ACTIVE` vs `unverified`.

## HTML Report

After all scanners complete, `run-scan.sh` automatically calls
`scripts/generate-report.py` to produce a self-contained HTML file:

```
{output-dir}/security-report.html
```

On macOS the report opens in the default browser automatically.

**Report features:**
- **Summary cards** — CRITICAL / HIGH / MEDIUM / LOW counts at a glance
- **Filter bar** — filter by severity, repo, scanner, type (live, no reload)
- **VS Code deep-links** — every `📄 file:line` entry is a `vscode://file/...` link that opens the exact line in VS Code when clicked
- **Package details** — installed version + available fix version per CVE
- **CVE links** — every CVE ID links to NVD or the advisory URL
- **Dark mode** — respects `prefers-color-scheme`
- **Print-friendly** — safe to save as PDF

You can also regenerate the report from cached JSON results without re-scanning:

```bash
python3 .github/skills/job-security-scan/scripts/generate-report.py \
  --results-dir .security-scan-results \
  --config .github/skills/job-security-scan/assets/repository.md \
  --output security-report.html \
  --workspace .
```

## How to Run

```bash
# Step 1 — install tools (once per machine)
bash .github/skills/job-security-scan/scripts/install-tools.sh

# Step 2 — full scan + HTML report (auto-opens on macOS)
bash .github/skills/job-security-scan/scripts/run-scan.sh

# Scope to one repo
bash .github/skills/job-security-scan/scripts/run-scan.sh --repo om-ddm-backend

# Run one scanner across all repos
bash .github/skills/job-security-scan/scripts/run-scan.sh --scanner trivy

# Use a different team's config
bash .github/skills/job-security-scan/scripts/run-scan.sh \
  --config /path/to/other-team/repository.md

# Regenerate HTML only (no re-scan)
python3 .github/skills/job-security-scan/scripts/generate-report.py \
  --results-dir .security-scan-results \
  --config .github/skills/job-security-scan/assets/repository.md
```

## Output Format

The agent must produce this report after all phases:

```markdown
# Security Scan Report — {team} / {org}

**Date:** {date}
**Config:** {config path}
**Repos scanned:** {count active repos}
**Scanners:** {list}

---

## Summary

| Repo | Secrets | CVE Critical | CVE High | SAST | Dockerfile | Status |
|------|:-------:|:------------:|:--------:|:----:|:----------:|--------|
| {repo} | {n} | {n} | {n} | {n} | {n} | 🔴/🟡/🟢 |

---

## 🔴 Critical Findings
## 🟠 High Findings
## 🟡 Medium Findings
## 🐳 Dockerfile Issues
## 🔑 Secrets (values NEVER shown)
## ⏭️ Skipped Repos
## 📋 Remediation → see references/remediation.md
```

## CI Integration

See [references/ci-workflow.md](references/ci-workflow.md) for a ready-to-paste
GitHub Actions workflow that reads `repository.md` automatically.

## Adding This Skill to a New Team

1. Copy `.github/skills/job-security-scan/` to the new team's repo
2. Edit `assets/repository.md` — update `team`, `org`, `ci-runner`, and `repos`
3. Commit — the skill is self-contained and works immediately
