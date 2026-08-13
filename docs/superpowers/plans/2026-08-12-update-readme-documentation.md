# Update README and Create Comprehensive Skill Documentation

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Completely overhaul the README.md with comprehensive skill listings and create detailed README documentation for each skill (job-security-scan, speckit-auto, speckit-code-review, jira-to-speckit).

**Architecture:** 
1. Replace the main README.md with a structured layout: intro, install guide, comprehensive skills table, contributing section
2. Create detailed README.md files alongside each SKILL.md with comprehensive documentation (500-1000 words per skill)
3. Each skill README covers: overview, quick start, detailed features, installation/setup, compatibility matrix, usage examples, configuration, and troubleshooting

**Tech Stack:** Markdown, bash scripting

## Global Constraints

- Preserve all existing SKILL.md files — they are the source of truth
- Do not modify any existing functionality or references in SKILL.md files
- Compatibility notes must be accurate for: GitHub Copilot CLI, Claude Code, local usage
- Installation paths must be precise for all platforms
- Each skill README must be 500-1000 words to provide comprehensive guidance

---

### Task 1: Extract and Organize Skill Information

**Files:**
- Read: `/Users/chuongnd/github-me/agents-skills/job-security-scan/SKILL.md`
- Read: `/Users/chuongnd/github-me/agents-skills/speckit-auto/SKILL.md`
- Read: `/Users/chuongnd/github-me/agents-skills/speckit-code-review/SKILL.md`
- Read: `/Users/chuongnd/github-me/agents-skills/jira-to-speckit/SKILL.md`
- Output: Structured analysis of each skill in session memory

**Interfaces:**
- Consumes: SKILL.md frontmatter (name, description, compatibility, metadata)
- Produces: Skill summary objects with: name, description, location (folder path), compatibility modes, key capabilities

- [ ] **Step 1: Read job-security-scan full SKILL.md**

Command: `view /Users/chuongnd/github-me/agents-skills/job-security-scan/SKILL.md`

- [ ] **Step 2: Read speckit-auto full SKILL.md**

Command: `view /Users/chuongnd/github-me/agents-skills/speckit-auto/SKILL.md`

- [ ] **Step 3: Read speckit-code-review full SKILL.md**

Command: `view /Users/chuongnd/github-me/agents-skills/speckit-code-review/SKILL.md`

- [ ] **Step 4: Read jira-to-speckit full SKILL.md**

Command: `view /Users/chuongnd/github-me/agents-skills/jira-to-speckit/SKILL.md`

- [ ] **Step 5: Create skill information summary**

Create a structured summary of all four skills with: name, description, install paths, key triggers/capabilities, compatibility, and key features. Store this information for use in creating the main README and individual skill READMEs.

---

### Task 2: Create Main README.md

**Files:**
- Create: `/Users/chuongnd/github-me/agents-skills/README.md` (replace existing)
- Reference: All four SKILL.md files (read-only)

**Interfaces:**
- Consumes: Skill summaries from Task 1
- Produces: Comprehensive README.md with intro, install guide, skills table, and contributing section

- [ ] **Step 1: Write new README.md with introduction section**

Create the top section with a brief intro paragraph explaining that this repo contains a collection of reusable skills for software engineering tasks. Example:

```markdown
# agents-skills

A collection of reusable, production-grade skills for software engineering workflows. These skills provide consistent, efficient task execution across development, testing, security, and documentation workflows.

## Purpose

This repository contains skill definitions for common engineering tasks:
- **Security scanning** — comprehensive vulnerability and secret detection
- **Spec-driven delivery** — end-to-end pipeline from requirements to implementation
- **Code review** — deep line-by-line review against specifications
- **Jira integration** — fetch and convert Jira tickets to Speckit-ready specs

Each skill is designed to work across multiple platforms and coding agents.
```

- [ ] **Step 2: Add installation guide section**

Add a "Quick Install" section with clear instructions for each platform:

```markdown
## Quick Install

Copy the skill folder you need into your agent's skill location:

| Platform | Location | Example |
|----------|----------|---------|
| GitHub Copilot | `.github/skills/` (in your repo) | `cp -r job-security-scan .github/skills/` |
| Claude Local | `~/.claude/skills/` | `cp -r job-security-scan ~/.claude/skills/` |
| Local/Git Storage | `~/.agents/skills/` | `cp -r job-security-scan ~/.agents/skills/` |

After copying, restart your IDE or agent session to discover the skill.
```

- [ ] **Step 3: Create comprehensive skills comparison table**

Add a detailed table with columns: Skill Name, Description, Install Path, Compatibility, Triggers, Status

The table should list all 4 skills (job-security-scan, speckit-auto, speckit-code-review, jira-to-speckit) with:
- Link to detailed README for each skill
- Brief 1-2 line description
- Installation path format
- Supported platforms (GitHub Copilot, Claude, Local)
- Primary use cases/triggers
- Version and author info

Example row:
```markdown
| [job-security-scan](./job-security-scan/README.md) | Comprehensive multi-tool security scanner for repos. Combines Gitleaks, Trivy, Semgrep, Hadolint, OSV-Scanner, TruffleHog. | `<repo>/.github/skills/job-security-scan` or `~/.agents/skills/job-security-scan` | GitHub Copilot, Claude, Local | Security scan, vulnerability detection, secret detection | v2.0 |
```

- [ ] **Step 4: Add skills overview section**

Create a section that briefly explains what each skill category does:

```markdown
## Skills Overview

### Security & Compliance
- **job-security-scan** — Scan repositories for vulnerabilities, secrets, and misconfigurations using industry-standard tools

### Spec-Driven Delivery
- **speckit-auto** — End-to-end delivery pipeline from requirements to implementation with automatic code review
- **speckit-code-review** — Deep code review comparing implementation against specifications
- **jira-to-speckit** — Convert Jira tickets into Speckit-ready feature specifications
```

- [ ] **Step 5: Add contributing section**

Add a "Contributing" section with guidelines for adding new skills:

```markdown
## Contributing

When adding or updating skills:

1. **Create a `SKILL.md` file** in the skill directory with frontmatter (name, description, compatibility, metadata)
2. **Create a `README.md` file** alongside SKILL.md with comprehensive documentation (500-1000 words)
3. **Structure your README** with: Overview, Quick Start, Features, Installation, Compatibility, Examples, Configuration, Troubleshooting
4. **Test the skill** across intended platforms (GitHub Copilot, Claude, local)
5. **Document all triggers and use cases** for discoverability
6. **Keep SKILL.md as the source of truth** — README expands on it

For new security skills, add test configurations to prevent false positives.
For new spec-delivery skills, ensure compatibility with all supported integration providers.
```

- [ ] **Step 6: Verify README structure and commit**

Review the new README.md to ensure:
- Clear, concise introduction
- Accurate installation instructions for all platforms
- Comprehensive skills table with all required columns
- Clear contributing guidelines

Then commit with message:
```bash
git add README.md
git commit -m "docs: replace README with comprehensive skills documentation

- Add concise introduction explaining repo purpose
- Include installation guide for all platforms
- Create comprehensive skills comparison table
- Add skills overview by category
- Add updated contributing guidelines

Co-authored-by: Copilot <223556219+Copilot@users.noreply.github.com>"
```

---

### Task 3: Create job-security-scan README.md

**Files:**
- Create: `/Users/chuongnd/github-me/agents-skills/job-security-scan/README.md`
- Reference: `/Users/chuongnd/github-me/agents-skills/job-security-scan/SKILL.md` (read-only)
- Reference: `/Users/chuongnd/github-me/agents-skills/job-security-scan/assets/repository.md`

**Interfaces:**
- Consumes: job-security-scan SKILL.md content and asset files
- Produces: Comprehensive 500-1000 word README covering all aspects of the skill

- [ ] **Step 1: Write Overview and Quick Start sections**

```markdown
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

---

## Version History

- **v2.0** (current) — Multi-tool unified pipeline, config-driven, zero-install for free tools
- **v1.0** — Gitleaks-only security scan

## License & Attribution

MIT License. Maintained by the security-focused engineering team.
```

- [ ] **Step 2: Commit the job-security-scan README**

```bash
git add job-security-scan/README.md
git commit -m "docs: add comprehensive job-security-scan README

- Add detailed overview and use cases
- Include quick start installation and configuration
- Document all 6 security tools and their capabilities
- Add platform-specific setup instructions
- Include compatibility matrix
- Provide real-world usage examples
- Add configuration and troubleshooting sections

Co-authored-by: Copilot <223556219+Copilot@users.noreply.github.com>"
```

---

### Task 4: Create speckit-auto README.md

**Files:**
- Create: `/Users/chuongnd/github-me/agents-skills/speckit-auto/README.md`
- Reference: `/Users/chuongnd/github-me/agents-skills/speckit-auto/SKILL.md` (read-only)

**Interfaces:**
- Consumes: speckit-auto SKILL.md and stage reference files
- Produces: Comprehensive 500-1000 word README covering the end-to-end pipeline

- [ ] **Step 1: Create speckit-auto README.md with full content**

Write a comprehensive README covering overview, quick start, features, compatibility, examples, and configuration. The README should explain:
- What speckit-auto does (end-to-end spec-driven delivery)
- How it integrates with different providers (github-speckit, superpowers)
- The 6-stage pipeline (intake, spec, implement, review, commit, completion)
- YOLO mode vs default mode
- How to invoke it on different platforms
- Real-world workflow examples
- Troubleshooting common issues

File path: `/Users/chuongnd/github-me/agents-skills/speckit-auto/README.md`

- [ ] **Step 2: Commit the speckit-auto README**

```bash
git add speckit-auto/README.md
git commit -m "docs: add comprehensive speckit-auto README

- Add detailed pipeline overview (6 stages)
- Explain provider selection and setup
- Document YOLO mode vs default mode
- Include quick start for both modes
- Add compatibility matrix for all platforms
- Provide full workflow examples
- Include sub-skill dependencies (jira-to-speckit, speckit-code-review)
- Add troubleshooting and best practices

Co-authored-by: Copilot <223556219+Copilot@users.noreply.github.com>"
```

---

### Task 5: Create speckit-code-review README.md

**Files:**
- Create: `/Users/chuongnd/github-me/agents-skills/speckit-code-review/README.md`
- Reference: `/Users/chuongnd/github-me/agents-skills/speckit-code-review/SKILL.md` (read-only)

**Interfaces:**
- Consumes: speckit-code-review SKILL.md and review procedure
- Produces: Comprehensive 500-1000 word README covering deep code review process

- [ ] **Step 1: Create speckit-code-review README.md with full content**

Write a comprehensive README covering:
- What speckit-code-review does (deep spec compliance review)
- The 5-category review framework (business gap, code quality, security, architecture, unit tests)
- How to use it standalone vs as part of speckit-auto
- Requirement ID synthesis for specs without pre-numbered requirements
- JSON output contract and detail files
- Compatibility across platforms
- Real-world review workflow examples
- Common issues and solutions

File path: `/Users/chuongnd/github-me/agents-skills/speckit-code-review/README.md`

- [ ] **Step 2: Commit the speckit-code-review README**

```bash
git add speckit-code-review/README.md
git commit -m "docs: add comprehensive speckit-code-review README

- Add overview of deep code review methodology
- Explain 5-category review framework
- Document requirement ID synthesis for unstructured specs
- Explain JSON output contract (compact vs detail tiers)
- Add standalone vs integrated usage patterns
- Include compatibility matrix for all platforms
- Provide realistic code review examples
- Document detail file structure and content
- Add troubleshooting and best practices

Co-authored-by: Copilot <223556219+Copilot@users.noreply.github.com>"
```

---

### Task 6: Create jira-to-speckit README.md

**Files:**
- Create: `/Users/chuongnd/github-me/agents-skills/jira-to-speckit/README.md`
- Reference: `/Users/chuongnd/github-me/agents-skills/jira-to-speckit/SKILL.md` (read-only)

**Interfaces:**
- Consumes: jira-to-speckit SKILL.md and workflow documentation
- Produces: Comprehensive 500-1000 word README covering Jira-to-spec workflow

- [ ] **Step 1: Create jira-to-speckit README.md with full content**

Write a comprehensive README covering:
- What jira-to-speckit does (bridges Jira and Speckit workflow)
- Setup requirements (.env configuration, Jira credentials)
- The 8-phase workflow (intake through implementation)
- How to invoke with Jira issue keys vs URLs
- Execution report tracking and updates
- Compaction pipeline for large tickets
- Configuration tuning for different Jira sizes
- Guardrails and security practices
- Real-world workflow examples
- Troubleshooting and common issues

File path: `/Users/chuongnd/github-me/agents-skills/jira-to-speckit/README.md`

- [ ] **Step 2: Commit the jira-to-speckit README**

```bash
git add jira-to-speckit/README.md
git commit -m "docs: add comprehensive jira-to-speckit README

- Add detailed workflow overview (8 phases)
- Document .env setup and Jira credentials
- Explain Jira compaction pipeline for large tickets
- Add quick start examples (issue keys, URLs)
- Document execution report tracking
- Include configuration tuning for ticket sizes
- List guardrails and security practices
- Add compatibility matrix for all platforms
- Provide real-world Jira-to-spec workflow examples
- Document sub-skill integration with speckit-auto
- Add troubleshooting and best practices

Co-authored-by: Copilot <223556219+Copilot@users.noreply.github.com>"
```

---

### Task 7: Final Verification and Integration

**Files:**
- Verify: `README.md` (main)
- Verify: `job-security-scan/README.md`
- Verify: `speckit-auto/README.md`
- Verify: `speckit-code-review/README.md`
- Verify: `jira-to-speckit/README.md`

**Interfaces:**
- Consumes: All README files and links between them
- Produces: Verified, internally-consistent documentation set

- [ ] **Step 1: Verify main README links to all skill READMEs**

Check that the main README.md has functioning links to each skill's README:
- `[job-security-scan](./job-security-scan/README.md)`
- `[speckit-auto](./speckit-auto/README.md)`
- `[speckit-code-review](./speckit-code-review/README.md)`
- `[jira-to-speckit](./jira-to-speckit/README.md)`

- [ ] **Step 2: Verify consistency across all READMEs**

Ensure:
- All installation paths are consistent across documents
- Compatibility information matches in all files
- Feature descriptions don't contradict between main README and skill READMEs
- All code examples are syntactically correct
- Links between skills (e.g., speckit-auto → speckit-code-review integration) are accurate

- [ ] **Step 3: Test that documentation renders properly**

```bash
# Check markdown syntax
cd /Users/chuongnd/github-me/agents-skills
find . -name "README.md" -type f | head -10
```

- [ ] **Step 4: Final commit with all changes**

```bash
git add -A
git commit -m "docs: complete comprehensive skill documentation overhaul

Summary of changes:
- Replaced main README.md with improved structure and navigation
- Added comprehensive README.md for job-security-scan (security scanning)
- Added comprehensive README.md for speckit-auto (end-to-end delivery pipeline)
- Added comprehensive README.md for speckit-code-review (spec compliance review)
- Added comprehensive README.md for jira-to-speckit (Jira integration)

Each skill README includes:
- Detailed overview and use cases
- Quick start guide with installation
- In-depth feature documentation
- Platform-specific setup instructions
- Compatibility matrix
- Real-world usage examples
- Configuration and troubleshooting

The main README provides:
- Clear introduction to the skills repository
- Installation guide for all platforms
- Comprehensive skills comparison table
- Categorized overview of all skills
- Updated contributing guidelines

Co-authored-by: Copilot <223556219+Copilot@users.noreply.github.com>"
```

- [ ] **Step 5: Push changes (if applicable)**

If working in a git repository, push the changes:

```bash
git push origin main
```

---

## Notes for Implementation

- **Focus on comprehensiveness:** Each skill README should be 500-1000 words with actual examples, not placeholder text
- **Preserve SKILL.md files:** Never modify SKILL.md — these are the source of truth for agent discovery
- **Accuracy is critical:** Installation paths, compatibility information, and platform details must be exact
- **Consistency:** Terminology and descriptions should match across all documents
- **Readability:** Use tables, code blocks, and clear headings to break up content
- **Real examples:** Include concrete bash commands, configuration snippets, and workflow scenarios
- **Link between skills:** Document how skills work together (e.g., speckit-auto calls speckit-code-review)
