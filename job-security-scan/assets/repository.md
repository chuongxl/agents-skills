---
# ──────────────────────────────────────────────────────────────
# repository.md — Security Scan Configuration
# Used by: .github/skills/job-security-scan
# Edit this file to configure the skill for your team & repos.
# ──────────────────────────────────────────────────────────────

team: your-team
org: your-org
monorepo-root: "."        # relative to workspace root; "." means repos are subdirs here
ci-runner: your-runner  # GitHub Actions runner label

# Languages, lockfiles and Semgrep rulesets are detected automatically per repo
# (see ecosystems/*.json). The old `package-manager:` and `stack:` fields are
# deprecated: they still work but print a warning. Remove them.

# CI branches — security scan triggers on push to these
ci-branches:
  - develop
  - main
  - staging
  - test

# Repos to scan. Fields:
#   name           — directory name (also used as display name)
#   active         — true = include in scan; false = skip (not yet designed)
#   has-dockerfile — true = run Hadolint on Dockerfile
#   semgrep-extra  — additional Semgrep rulesets beyond the detected languages (optional)
repos:
  - name: your-backend
    active: true
    has-dockerfile: false
    semgrep-extra: []

  - name: your-frontend
    active: true
    has-dockerfile: true
    semgrep-extra: []

  - name: your-configuration
    active: true
    has-dockerfile: false
    semgrep-extra: []

# Files allowlisted from secret scanning (relative glob patterns)
secret-allowlist-paths:
  - "**/.env.example"
  - "**/.env.sample"
  - "**/cypress.env.json"

# CVE severity threshold — findings below this are reported but don't fail the build
# Options: CRITICAL | HIGH | MEDIUM | LOW
fail-on-severity: HIGH

# Output directory for scan results (relative to workspace root)
output-dir: ".security-scan-results"
---

# Security Scan — Repository Configuration

This file is the **single source of truth** for the `job-security-scan` skill.
Update it when repos are added, renamed, or go out of scope.

## How to add a new repo

1. Add a new entry under `repos:` in the frontmatter above.
2. Set `active: true` to include it in scans immediately.
3. Set `has-dockerfile: true` if the repo ships a container image.

## How to skip a repo temporarily

Set `active: false`. The repo will appear in scan reports as `⏭️ skipped`.

## How to add custom Semgrep rules

Add rule IDs to `semgrep-extra` for that repo. For example:
```yaml
semgrep-extra:
  - p/sql-injection
  - p/jwt
```

## Languages and Semgrep rulesets

Each repo is inspected for manifests and lockfiles; the languages found decide the
Semgrep rulesets and which lockfiles OSV-Scanner reads. Run
`python3 -I scripts/detect-ecosystems.py <repo-dir>` to see what is detected, and see
`references/ecosystems.md` to add a language.

All repos additionally get: `p/owasp-top-ten`, `p/secrets`

The deprecated `stack:` field, if still present, adds its rulesets
(typescript, nodejs, nestjs, nextjs) on top of the detected ones.
