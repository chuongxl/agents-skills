# CI Workflow — job-security-scan

This workflow reads team/repo config from `repository.md` at the skill root.
**No hardcoded repo names or team values** — update `repository.md` to change scope.

Copy this file to each service repo as `.github/workflows/job-security-scan.yaml`.

---

```yaml
name: Security Scan

on:
  pull_request:
  push:
    branches:
      # Branches come from repository.md > ci-branches
      # Update repository.md — not this file — to change trigger branches
      - develop
      - main
      - staging
      - test
  schedule:
    - cron: '0 1 * * 1'  # Weekly Monday 01:00 — catch new CVEs on unchanged code
  workflow_dispatch:

env:
  SKILL_DIR: .github/skills/job-security-scan
  CONFIG:    .github/skills/job-security-scan/assets/repository.md

jobs:
  # ── Read config ───────────────────────────────────────────────────────────
  # All repo/team values are sourced from repository.md at runtime.
  # The jobs below reference $SKILL_DIR and $CONFIG — not hardcoded names.

  # ── 1. Secret Detection (Gitleaks) ────────────────────────────────────────
  secret-scan:
    name: "🔑 Gitleaks — ${{ github.repository }}"
    runs-on: ${{ fromJson(vars.CI_RUNNER || '["ubuntu-latest"]') }}
    steps:
      - uses: actions/checkout@v4
        with:
          fetch-depth: 0

      - uses: gitleaks/gitleaks-action@v2
        env:
          GITHUB_TOKEN: ${{ secrets.GITHUB_TOKEN }}
        with:
          config-path: ${{ env.SKILL_DIR }}/assets/gitleaks.toml

  # ── 2. CVE + Dockerfile + Misconfig (Trivy) ───────────────────────────────
  dependency-scan:
    name: "📦 Trivy — ${{ github.repository }}"
    runs-on: ${{ fromJson(vars.CI_RUNNER || '["ubuntu-latest"]') }}
    steps:
      - uses: actions/checkout@v4

      - name: Read fail-on-severity from repository.md
        id: cfg
        run: |
          SEV=$(python3 ${{ env.SKILL_DIR }}/scripts/parse-config.py \
                  ${{ env.CONFIG }} --key fail-on-severity)
          echo "severity=${SEV:-HIGH},CRITICAL" >> $GITHUB_OUTPUT

      - uses: aquasecurity/trivy-action@0.28.0
        with:
          scan-type: fs
          scan-ref: .
          scanners: vuln,secret,misconfig
          severity: ${{ steps.cfg.outputs.severity }}
          format: sarif
          output: trivy.sarif
          exit-code: '1'
          ignore-unfixed: true
          trivyignores: ${{ env.SKILL_DIR }}/assets/.trivyignore

      - uses: github/codeql-action/upload-sarif@v3
        if: always()
        with:
          sarif_file: trivy.sarif
          category: trivy

  # ── 3. SAST (Semgrep) ─────────────────────────────────────────────────────
  sast-scan:
    name: "🔍 Semgrep — ${{ github.repository }}"
    runs-on: ${{ fromJson(vars.CI_RUNNER || '["ubuntu-latest"]') }}
    container:
      image: semgrep/semgrep:latest
    steps:
      - uses: actions/checkout@v4

      - name: Build Semgrep config args from repository.md
        id: semgrep-cfg
        run: |
          RULESETS=$(python3 ${{ env.SKILL_DIR }}/scripts/parse-config.py \
                      ${{ env.CONFIG }} --key semgrep-rulesets | \
                      awk '{printf "--config %s ", $0}')
          echo "config_args=${RULESETS}" >> $GITHUB_OUTPUT

      - name: Run Semgrep
        run: |
          semgrep scan \
            ${{ steps.semgrep-cfg.outputs.config_args }} \
            --sarif --output semgrep.sarif \
            --error --quiet .

      - uses: github/codeql-action/upload-sarif@v3
        if: always()
        with:
          sarif_file: semgrep.sarif
          category: semgrep

  # ── 4. Dockerfile Lint (Hadolint) ─────────────────────────────────────────
  dockerfile-lint:
    name: "🐳 Hadolint — ${{ github.repository }}"
    runs-on: ${{ fromJson(vars.CI_RUNNER || '["ubuntu-latest"]') }}
    steps:
      - uses: actions/checkout@v4

      - name: Check if Dockerfile exists
        id: check
        run: |
          [[ -f Dockerfile ]] && echo "exists=true" >> $GITHUB_OUTPUT \
                               || echo "exists=false" >> $GITHUB_OUTPUT

      - uses: hadolint/hadolint-action@v3.1.0
        if: steps.check.outputs.exists == 'true'
        with:
          dockerfile: Dockerfile
          config: ${{ env.SKILL_DIR }}/assets/hadolint.yaml
          format: sarif
          output-file: hadolint.sarif
          failure-threshold: warning

      - uses: github/codeql-action/upload-sarif@v3
        if: steps.check.outputs.exists == 'true' && always()
        with:
          sarif_file: hadolint.sarif
          category: hadolint

  # ── 5. Transitive CVE Scan (OSV-Scanner) ──────────────────────────────────
  osv-scan:
    name: "🔗 OSV-Scanner — ${{ github.repository }}"
    runs-on: ${{ fromJson(vars.CI_RUNNER || '["ubuntu-latest"]') }}
    steps:
      - uses: actions/checkout@v4

      - name: Detect lockfile from repository.md package-manager
        id: lock
        run: |
          PM=$(python3 ${{ env.SKILL_DIR }}/scripts/parse-config.py \
                ${{ env.CONFIG }} --key package-manager)
          case "$PM" in
            yarn) echo "lockfile=yarn:./yarn.lock" >> $GITHUB_OUTPUT ;;
            npm)  echo "lockfile=npm:./package-lock.json" >> $GITHUB_OUTPUT ;;
            pnpm) echo "lockfile=pnpm:./pnpm-lock.yaml" >> $GITHUB_OUTPUT ;;
            *)    echo "lockfile=" >> $GITHUB_OUTPUT ;;
          esac

      - uses: google/osv-scanner-action@v2
        if: steps.lock.outputs.lockfile != ''
        with:
          scan-args: |-
            --lockfile=${{ steps.lock.outputs.lockfile }}

  # ── 6. Verified Secret Detection (TruffleHog) ─────────────────────────────
  trufflehog-scan:
    name: "🕵️ TruffleHog — ${{ github.repository }}"
    runs-on: ${{ fromJson(vars.CI_RUNNER || '["ubuntu-latest"]') }}
    steps:
      - uses: actions/checkout@v4
        with:
          fetch-depth: 0

      - uses: trufflesecurity/trufflehog@main
        with:
          path: ./
          base: ${{ github.event.repository.default_branch }}
          head: HEAD
          extra_args: --only-verified
```

---

## Repository Variables (set once, reused across all repos)

Add these as GitHub Actions **Repository Variables** (not secrets):

| Variable | Value | Set In |
|----------|-------|--------|
| `CI_RUNNER` | `["om-ddm-runner"]` | Repo Settings → Variables |

This lets you change the runner in one place without editing every workflow file.

---

## Status Badges

```markdown
![Security Scan](https://github.com/{org}/{repo}/actions/workflows/job-security-scan.yaml/badge.svg)
```

Replace `{org}` and `{repo}` — or read them from `repository.md`:
```bash
python3 .github/skills/job-security-scan/scripts/parse-config.py \
  .github/skills/job-security-scan/assets/repository.md --key org
```
