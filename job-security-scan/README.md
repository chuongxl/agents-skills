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
- `stack` — Tech stack (typescript, nodejs, python, go, java, etc.)
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

Results are saved to `.security-scan-results/` by default:

```
.security-scan-results/
├── report.json           # Structured full report
├── summary.txt           # Human-readable summary
└── <repo-name>/
    ├── gitleaks.json
    ├── trivy.json
    ├── semgrep.json
    └── hadolint.json
```

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

Rulesets are controlled by the `stack` field in `repository.md`.

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
package-manager: yarn
stack:
  - typescript
  - nodejs
  - docker

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
output-dir: .security-scan-results
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

# Results in .security-scan-results/report.json
cat .security-scan-results/summary.txt
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
      - name: Run security scan
        run: bash .github/skills/job-security-scan/scripts/run-scan.sh
      - name: Upload results
        uses: actions/upload-artifact@v3
        with:
          name: security-results
          path: .security-scan-results/
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

## Version History

- **v2.0** (current) — Multi-tool unified pipeline, config-driven, zero-install for free tools
- **v1.0** — Gitleaks-only security scan

## License & Attribution

MIT License. Maintained by the security-focused engineering team.
