# CI Workflow — job-security-scan

This workflow reads team/repo config from `repository.md` at the skill root.
**No hardcoded repo names or team values** — update `repository.md` to change scope.

Copy this file to each service repo as `.github/workflows/job-security-scan.yaml`.

> **Supply-chain safety.** Every action below is pinned to a full commit SHA (the tag is in the comment), and
> every checkout drops its token (`persist-credentials: false`). Never replace a SHA with a tag or a branch:
> in March 2026 the `aquasecurity/trivy-action` tags `0.0.1`–`0.34.2` were force-pushed to malicious code
> (GHSA-69fq-xp46-6x23) and stole CI secrets. This template uses the safe `0.35.0` commit with the Trivy
> v0.69.3 binary. When you bump an action, resolve the new tag to its commit SHA yourself
> (`git ls-remote --tags https://github.com/OWNER/REPO`) and check its advisories first.

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

permissions:
  contents: read          # jobs that upload SARIF add security-events: write for themselves

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
    permissions:
      contents: read
      security-events: write
    steps:
      - uses: actions/checkout@11d5960a326750d5838078e36cf38b85af677262 # v4
        with:
          fetch-depth: 0
          persist-credentials: false

      - uses: gitleaks/gitleaks-action@ff98106e4c7b2bc287b24eaf42907196329070c7 # v2
        env:
          GITHUB_TOKEN: ${{ secrets.GITHUB_TOKEN }}
        with:
          config-path: ${{ env.SKILL_DIR }}/assets/gitleaks.toml

  # ── 2. CVE + Dockerfile + Misconfig (Trivy) ───────────────────────────────
  dependency-scan:
    name: "📦 Trivy — ${{ github.repository }}"
    runs-on: ${{ fromJson(vars.CI_RUNNER || '["ubuntu-latest"]') }}
    permissions:
      contents: read
      security-events: write
    steps:
      - uses: actions/checkout@11d5960a326750d5838078e36cf38b85af677262 # v4
        with:
          persist-credentials: false

      - name: Read fail-on-severity from repository.md
        id: cfg
        run: |
          SEV=$(python3 ${{ env.SKILL_DIR }}/scripts/parse-config.py \
                  ${{ env.CONFIG }} --key fail-on-severity)
          echo "severity=${SEV:-HIGH},CRITICAL" >> $GITHUB_OUTPUT

      - uses: aquasecurity/trivy-action@57a97c7e7821a5776cebc9bb87c984fa69cba8f1 # 0.35.0 (safe; 0.0.1-0.34.2 were hijacked)
        with:
          version: v0.69.3
          scan-type: fs
          scan-ref: .
          scanners: vuln,secret,misconfig
          severity: ${{ steps.cfg.outputs.severity }}
          format: sarif
          output: trivy.sarif
          exit-code: '1'
          ignore-unfixed: true
          trivyignores: ${{ env.SKILL_DIR }}/assets/.trivyignore

      - uses: github/codeql-action/upload-sarif@4bfa242aa49c5f7c6770b98670d354a7dfac05f8 # v3
        if: always()
        with:
          sarif_file: trivy.sarif
          category: trivy

  # ── 3. SAST (Semgrep) ─────────────────────────────────────────────────────
  sast-scan:
    name: "🔍 Semgrep — ${{ github.repository }}"
    runs-on: ${{ fromJson(vars.CI_RUNNER || '["ubuntu-latest"]') }}
    container:
      image: semgrep/semgrep:1.183.0   # pinned; prefer @sha256:<digest> once you have resolved it
    steps:
      - uses: actions/checkout@11d5960a326750d5838078e36cf38b85af677262 # v4
        with:
          persist-credentials: false

      - name: Build Semgrep config args from repository.md
        id: semgrep-cfg
        run: |
          RULESETS=$(python3 ${{ env.SKILL_DIR }}/scripts/parse-config.py \
                      ${{ env.CONFIG }} --key semgrep-rulesets | \
                      awk '{printf "--config %s ", $0}')
          echo "config_args=${RULESETS}" >> $GITHUB_OUTPUT

      - name: Run Semgrep
        env:
          CONFIG_ARGS: ${{ steps.semgrep-cfg.outputs.config_args }}   # via env, never expanded into the script
        run: |
          # shellcheck disable=SC2086  # CONFIG_ARGS is a list of --config flags
          semgrep scan \
            $CONFIG_ARGS \
            --sarif --output semgrep.sarif \
            --error --quiet .

      - uses: github/codeql-action/upload-sarif@4bfa242aa49c5f7c6770b98670d354a7dfac05f8 # v3
        if: always()
        with:
          sarif_file: semgrep.sarif
          category: semgrep

  # ── 4. Dockerfile Lint (Hadolint) ─────────────────────────────────────────
  dockerfile-lint:
    name: "🐳 Hadolint — ${{ github.repository }}"
    runs-on: ${{ fromJson(vars.CI_RUNNER || '["ubuntu-latest"]') }}
    permissions:
      contents: read
      security-events: write
    steps:
      - uses: actions/checkout@11d5960a326750d5838078e36cf38b85af677262 # v4
        with:
          persist-credentials: false

      - name: Check if Dockerfile exists
        id: check
        run: |
          [[ -f Dockerfile ]] && echo "exists=true" >> $GITHUB_OUTPUT \
                               || echo "exists=false" >> $GITHUB_OUTPUT

      - uses: hadolint/hadolint-action@54c9adbab1582c2ef04b2016b760714a4bfde3cf # v3.1.0
        if: steps.check.outputs.exists == 'true'
        with:
          dockerfile: Dockerfile
          config: ${{ env.SKILL_DIR }}/assets/hadolint.yaml
          format: sarif
          output-file: hadolint.sarif
          failure-threshold: warning

      - uses: github/codeql-action/upload-sarif@4bfa242aa49c5f7c6770b98670d354a7dfac05f8 # v3
        if: steps.check.outputs.exists == 'true' && always()
        with:
          sarif_file: hadolint.sarif
          category: hadolint

  # ── 5. Transitive CVE Scan (OSV-Scanner) ──────────────────────────────────
  osv-scan:
    name: "🔗 OSV-Scanner — ${{ github.repository }}"
    runs-on: ${{ fromJson(vars.CI_RUNNER || '["ubuntu-latest"]') }}
    permissions:
      contents: read
      security-events: write
    steps:
      - uses: actions/checkout@11d5960a326750d5838078e36cf38b85af677262 # v4
        with:
          persist-credentials: false

      - name: Detect lockfiles of every supported ecosystem
        id: lock
        run: |
          ARGS=""
          while IFS= read -r lf; do
            [ -n "$lf" ] && ARGS="$ARGS -L ./$lf"
          done < <(python3 -I ${{ env.SKILL_DIR }}/scripts/detect-ecosystems.py . --format lockfiles)
          echo "scan_args=$ARGS" >> $GITHUB_OUTPUT

      - uses: google/osv-scanner-action/osv-scanner-action@b1d267aea5211fa648d9d442fa64b90dbdcbdd36 # v2.7.0
        if: steps.lock.outputs.scan_args != ''
        with:
          scan-args: ${{ steps.lock.outputs.scan_args }}

  # ── 6. Verified Secret Detection (TruffleHog) ─────────────────────────────
  trufflehog-scan:
    name: "🕵️ TruffleHog — ${{ github.repository }}"
    runs-on: ${{ fromJson(vars.CI_RUNNER || '["ubuntu-latest"]') }}
    permissions:
      contents: read
      security-events: write
    steps:
      - uses: actions/checkout@11d5960a326750d5838078e36cf38b85af677262 # v4
        with:
          fetch-depth: 0
          persist-credentials: false

      - uses: trufflesecurity/trufflehog@31ce31ee1abbcc7dc8eee5764c17121c3044c8b2 # v3.99.7
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
