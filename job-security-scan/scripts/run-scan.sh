#!/usr/bin/env bash
# run-scan.sh — Generic security scanner for any team/repo workspace.
#
# Usage:
#   run-scan.sh [--config path/to/repository.md] [--repo REPO_NAME] [--scanner SCANNER]
#
# Flags:
#   --config   Path to repository.md config file (default: auto-discover)
#   --repo     Scan one repo by name only (default: all active repos)
#   --scanner  Run one scanner only: gitleaks|trivy|semgrep|hadolint|osv|sbom|trufflehog|all
#
# Reads all team/repo config from repository.md — no hardcoded values.

set -uo pipefail

# ─── Argument parsing ──────────────────────────────────────────────────────
SCANNER="all"
REPO_FILTER=""
CONFIG_PATH=""

while [[ $# -gt 0 ]]; do
  case "$1" in
    --config)   CONFIG_PATH="$2"; shift 2 ;;
    --repo)     REPO_FILTER="$2"; shift 2 ;;
    --scanner)  SCANNER="$2";     shift 2 ;;
    -s)         SCANNER="$2";     shift 2 ;;
    -r)         REPO_FILTER="$2"; shift 2 ;;
    *)          echo "Unknown arg: $1"; exit 1 ;;
  esac
done

# ─── Locate skill root & config ────────────────────────────────────────────
SKILL_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"

if [[ -z "$CONFIG_PATH" ]]; then
  CONFIG_PATH="$SKILL_DIR/assets/repository.md"
fi

if [[ ! -f "$CONFIG_PATH" ]]; then
  echo "❌ Config not found: $CONFIG_PATH"
  echo "   Create one by copying: $SKILL_DIR/assets/repository.md"
  exit 1
fi

# ─── Load config ──────────────────────────────────────────────────────────
eval "$(python3 "$SKILL_DIR/scripts/parse-config.py" "$CONFIG_PATH")"

WORKSPACE="${MONOREPO_ROOT:-.}"
OUTPUT_BASE="${OUTPUT_DIR:-.security-scan-results}"
mkdir -p "$OUTPUT_BASE"

ASSET_DIR="$SKILL_DIR/assets"

# ─── Determine repos to scan ───────────────────────────────────────────────
declare -a REPOS_TO_SCAN
if [[ -n "$REPO_FILTER" ]]; then
  REPOS_TO_SCAN=("$REPO_FILTER")
else
  REPOS_TO_SCAN=("${ACTIVE_REPOS[@]}")
fi

# ─── Helpers ──────────────────────────────────────────────────────────────
GLOBAL_EXIT=0

_log()  { echo "  [$1] $2: $3"; }
_pass() { echo "  ✅ [$1] $2: $3"; }
_warn() { echo "  🟡 [$1] $2: $3"; [[ $GLOBAL_EXIT -lt 1 ]] && GLOBAL_EXIT=1; }
_fail() { echo "  🔴 [$1] $2: $3"; GLOBAL_EXIT=2; }
_skip() { echo "  ⏭️  [$1] $2: $3 — skipped"; }

has_tool() { command -v "$1" &>/dev/null; }

# osv-scanner flag names changed across v2 releases (--output -> --output-file, --sbom -> -L).
OSV_OUT_FLAG=""
osv_out_flag() {
  if [[ -z "$OSV_OUT_FLAG" ]]; then
    if osv-scanner scan source --help 2>&1 | grep -q -- '--output-file'; then OSV_OUT_FLAG="--output-file"; else OSV_OUT_FLAG="--output"; fi
  fi
  echo "$OSV_OUT_FLAG"
}

# Ecosystem detection (descriptors in ecosystems/*.json).
detect_cached() {  # detect_cached <path> <format>  -> prints detection output
  python3 -I "$SKILL_DIR/scripts/detect-ecosystems.py" "$1" --format "$2" \
    || echo "  ⚠️  ecosystem detection failed for $1 (see error above) - results may be incomplete" >&2
}

# ─── SCANNERS ─────────────────────────────────────────────────────────────

run_gitleaks() {
  local repo="$1" path="$2"
  local out="$OUTPUT_BASE/$repo/gitleaks.json"
  mkdir -p "$(dirname "$out")"

  if ! has_tool gitleaks; then _skip gitleaks "$repo" "tool not installed"; return; fi

  _log gitleaks "$repo" "Scanning full git history for secrets..."
  gitleaks detect \
    --source "$path" \
    --log-opts "--all" \
    --config "$ASSET_DIR/gitleaks.toml" \
    --report-format json \
    --report-path "$out" \
    --no-banner \
    --exit-code 1 \
    2>/dev/null
  local rc=$?
  if [[ $rc -eq 0 ]]; then
    _pass gitleaks "$repo" "No secrets found"
  else
    local count
    count=$(python3 -c "import json; print(len(json.load(open('$out'))))" 2>/dev/null || echo "?")
    _fail gitleaks "$repo" "$count secret(s) — see $out (values masked in report)"
  fi
}

run_trivy() {
  local repo="$1" path="$2"
  local out_table="$OUTPUT_BASE/$repo/trivy.txt"
  local out_sarif="$OUTPUT_BASE/$repo/trivy.sarif"
  local out_json="$OUTPUT_BASE/$repo/trivy.json"
  mkdir -p "$(dirname "$out_table")"

  if ! has_tool trivy; then _skip trivy "$repo" "tool not installed"; return; fi

  _log trivy "$repo" "Scanning dependencies, Dockerfile, secrets..."

  # Ensure DB is cached (skip re-download if already present)
  trivy image --download-db-only \
    --db-repository ghcr.io/aquasecurity/trivy-db \
    --quiet 2>/dev/null || \
  trivy image --download-db-only --quiet 2>/dev/null || true

  local sev="${FAIL_ON_SEVERITY:-HIGH},CRITICAL"
  [[ "$sev" != *"MEDIUM"* ]] && sev="MEDIUM,$sev"

  trivy fs "$path" \
    --scanners vuln,secret,misconfig \
    --severity "$sev" \
    --skip-db-update \
    --ignorefile "$ASSET_DIR/.trivyignore" \
    --format table --no-progress --quiet \
    2>/dev/null > "$out_table" || true

  trivy fs "$path" \
    --scanners vuln,secret,misconfig \
    --severity "$sev" \
    --skip-db-update \
    --ignorefile "$ASSET_DIR/.trivyignore" \
    --format json --output "$out_json" \
    --no-progress --quiet \
    2>/dev/null || true

  trivy fs "$path" \
    --scanners vuln,secret,misconfig \
    --severity "$sev" \
    --skip-db-update \
    --ignorefile "$ASSET_DIR/.trivyignore" \
    --format sarif --output "$out_sarif" \
    --no-progress --quiet \
    2>/dev/null || true

  local crits highs
  crits=$(grep -c "CRITICAL" "$out_table" 2>/dev/null || true)
  highs=$(grep -c "HIGH"     "$out_table" 2>/dev/null || true)
  crits=${crits:-0}
  highs=${highs:-0}

  if [[ "$crits" -gt 0 ]]; then
    _fail  trivy "$repo" "CRITICAL=$crits HIGH=$highs — see $out_table"
  elif [[ "$highs" -gt 0 ]]; then
    _warn  trivy "$repo" "HIGH=$highs (no CRITICAL) — see $out_table"
  else
    _pass  trivy "$repo" "No CRITICAL/HIGH vulnerabilities"
  fi
}

run_semgrep() {
  local repo="$1" path="$2"
  local out="$OUTPUT_BASE/$repo/semgrep.json"
  mkdir -p "$(dirname "$out")"

  if ! has_tool semgrep; then _skip semgrep "$repo" "tool not installed"; return; fi

  # Rulesets = base set from config + rulesets of every detected language, de-duplicated.
  local rulesets=()
  while IFS= read -r r; do [[ -n "$r" ]] && rulesets+=("$r"); done < <(
    { printf '%s\n' "${SEMGREP_RULESETS[@]}"; detect_cached "$path" semgrep; } | sort -u)

  _log semgrep "$repo" "Running SAST (${#rulesets[@]} rulesets: ${rulesets[*]})..."

  local config_args=()
  for r in "${rulesets[@]}"; do
    config_args+=(--config "$r")
  done

  semgrep scan \
    "${config_args[@]}" \
    --json --output "$out" \
    --no-rewrite-rule-ids --quiet \
    "$path" 2>/dev/null || true

  local count
  count=$(python3 -c \
    "import json; d=json.load(open('$out')); print(len(d.get('results',[])))" \
    2>/dev/null || echo 0)

  if [[ "$count" -eq 0 ]]; then
    _pass semgrep "$repo" "No findings"
  else
    _warn semgrep "$repo" "$count finding(s) — see $out"
  fi
}

run_hadolint() {
  local repo="$1" path="$2"
  local dockerfile="$path/Dockerfile"

  if [[ ! -f "$dockerfile" ]]; then _skip hadolint "$repo" "no Dockerfile"; return; fi
  if ! has_tool hadolint;      then _skip hadolint "$repo" "tool not installed"; return; fi

  local out="$OUTPUT_BASE/$repo/hadolint.txt"
  mkdir -p "$(dirname "$out")"

  _log hadolint "$repo" "Linting Dockerfile..."
  hadolint --config "$ASSET_DIR/hadolint.yaml" --format tty "$dockerfile" 2>&1 > "$out" || true

  local count
  count=$(wc -l < "$out" 2>/dev/null | tr -d '[:space:]')
  count=${count:-0}

  if [[ "$count" -eq 0 ]]; then
    _pass hadolint "$repo" "Dockerfile clean"
  else
    _warn hadolint "$repo" "$count issue(s) — see $out"
  fi
}

run_osv() {
  local repo="$1" path="$2"
  local out="$OUTPUT_BASE/$repo/osv.json"

  local lockfiles=()
  while IFS= read -r lf; do [[ -n "$lf" ]] && lockfiles+=("$lf"); done < <(detect_cached "$path" lockfiles)

  if [[ ${#lockfiles[@]} -eq 0 ]]; then _skip osv "$repo" "no supported lockfile found"; return; fi
  if ! has_tool osv-scanner; then _skip osv "$repo" "tool not installed"; return; fi

  mkdir -p "$(dirname "$out")"
  _log osv "$repo" "Scanning ${#lockfiles[@]} lockfile(s) via OSV.dev: ${lockfiles[*]}"

  # osv-scanner v2: `scan source -L <file>` (repeatable); the parser is chosen from the file name.
  local args=()
  for lf in "${lockfiles[@]}"; do args+=(-L "$path/$lf"); done
  osv-scanner scan source "${args[@]}" --format json "$(osv_out_flag)" "$out" 2>"$OUTPUT_BASE/$repo/osv.stderr"
  local rc=$?
  # exit 0 = clean, 1 = vulnerabilities found; anything else is a scanner error
  if [[ $rc -gt 1 || ! -s "$out" ]]; then
    _warn osv "$repo" "osv-scanner failed (exit $rc) - see $OUTPUT_BASE/$repo/osv.stderr"
    return
  fi

  local count
  count=$(python3 -c \
    "import json; d=json.load(open('$out')); print(sum(len(r.get('packages',[])) for r in d.get('results',[])))" \
    2>/dev/null || echo 0)

  if [[ "$count" -eq 0 ]]; then
    _pass osv "$repo" "No OSV vulnerabilities"
  else
    _warn osv "$repo" "$count package(s) with CVEs - see $out"
  fi
}

run_sbom() {
  local repo="$1" path="$2"

  if [[ "$(detect_cached "$path" needs-sbom)" != "true" ]]; then
    _skip sbom "$repo" "every detected ecosystem has a lockfile"; return
  fi
  if ! has_tool trivy; then _skip sbom "$repo" "tool not installed"; return; fi

  local sbom="$OUTPUT_BASE/$repo/sbom.cdx.json"
  local out="$OUTPUT_BASE/$repo/osv-sbom.json"
  mkdir -p "$(dirname "$sbom")"

  _log sbom "$repo" "Unmapped or lockfile-less stack - generating CycloneDX SBOM..."
  trivy fs "$path" --scanners license --format cyclonedx --output "$sbom" --no-progress --quiet 2>"$OUTPUT_BASE/$repo/sbom.stderr" || true
  if [[ ! -s "$sbom" ]]; then _warn sbom "$repo" "could not generate SBOM - see $OUTPUT_BASE/$repo/sbom.stderr"; return; fi

  local comps
  comps=$(python3 -c "import json; print(len(json.load(open('$sbom')).get('components',[])))" 2>/dev/null || echo 0)
  if [[ "$comps" -eq 0 ]]; then _skip sbom "$repo" "SBOM has no components"; return; fi

  if ! has_tool osv-scanner; then _pass sbom "$repo" "SBOM written ($comps components) - osv-scanner missing, not matched"; return; fi

  # Newer osv-scanner reads an SBOM with -L; older v2 releases only know --sbom.
  osv-scanner scan source -L "$sbom" --format json "$(osv_out_flag)" "$out" 2>"$OUTPUT_BASE/$repo/osv-sbom.stderr"
  local rc=$?
  if [[ $rc -gt 1 ]]; then
    osv-scanner scan source --sbom "$sbom" --format json "$(osv_out_flag)" "$out" 2>"$OUTPUT_BASE/$repo/osv-sbom.stderr"
    rc=$?
  fi
  if [[ $rc -gt 1 || ! -s "$out" ]]; then
    _warn sbom "$repo" "SBOM match failed (exit $rc) - see $OUTPUT_BASE/$repo/osv-sbom.stderr"; return
  fi
  local count
  count=$(python3 -c \
    "import json; d=json.load(open('$out')); print(sum(len(r.get('packages',[])) for r in d.get('results',[])))" \
    2>/dev/null || echo 0)
  if [[ "$count" -eq 0 ]]; then
    _pass sbom "$repo" "SBOM ($comps components) - no OSV vulnerabilities"
  else
    _warn sbom "$repo" "SBOM ($comps components): $count package(s) with CVEs - see $out"
  fi
}

run_trufflehog() {
  local repo="$1" path="$2"
  local out="$OUTPUT_BASE/$repo/trufflehog.json"
  mkdir -p "$(dirname "$out")"

  if ! has_tool trufflehog; then _skip trufflehog "$repo" "tool not installed"; return; fi

  _log trufflehog "$repo" "Scanning git history — verifying active credentials..."
  trufflehog git "file://$path" \
    --json --no-update \
    2>/dev/null | grep -v "^$" > "$out" || true

  local count verified
  # Use wc for total line count and tolerate grep's non-zero exit on zero matches.
  count=$(wc -l < "$out" 2>/dev/null | tr -d '[:space:]')
  count=${count:-0}
  verified=$(grep -c '"verified":true' "$out" 2>/dev/null || true)
  verified=${verified:-0}

  if [[ "$count" -eq 0 ]]; then
    _pass trufflehog "$repo" "No secrets detected"
  elif [[ "$verified" -gt 0 ]]; then
    _fail trufflehog "$repo" "$count secret(s) — $verified VERIFIED ACTIVE — see $out (values masked)"
  else
    _warn trufflehog "$repo" "$count unverified secret(s) — see $out"
  fi
}

# ─── DISPATCH ─────────────────────────────────────────────────────────────

run_scanner_for_repo() {
  local repo="$1"
  local path="$WORKSPACE/$repo"

  if [[ ! -d "$path" ]]; then
    echo "  ⚠️  Repo not found on disk: $path — skipping"
    return
  fi

  case "$SCANNER" in
    gitleaks)   run_gitleaks   "$repo" "$path" ;;
    trivy)      run_trivy      "$repo" "$path" ;;
    semgrep)    run_semgrep    "$repo" "$path" ;;
    hadolint)   run_hadolint   "$repo" "$path" ;;
    osv)        run_osv        "$repo" "$path" ;;
    sbom)       run_sbom       "$repo" "$path" ;;
    trufflehog) run_trufflehog "$repo" "$path" ;;
    all)
      run_gitleaks   "$repo" "$path"
      run_trivy      "$repo" "$path"
      run_semgrep    "$repo" "$path"
      run_hadolint   "$repo" "$path"
      run_osv        "$repo" "$path"
      run_sbom       "$repo" "$path"
      run_trufflehog "$repo" "$path"
      ;;
    *)
      echo "Unknown scanner: $SCANNER"
      echo "Valid: gitleaks | trivy | semgrep | hadolint | osv | sbom | trufflehog | all"
      exit 1
      ;;
  esac
}

# ─── MAIN ─────────────────────────────────────────────────────────────────
echo ""
echo "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"
echo "  🔐 Security Scan — team: ${TEAM} | org: ${ORG}"
echo "  Scanners : ${SCANNER}"
echo "  Repos    : ${REPOS_TO_SCAN[*]}"
echo "  Output   : ${OUTPUT_BASE}/"
echo "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"

for repo in "${REPOS_TO_SCAN[@]}"; do
  echo ""
  echo "  ── $repo ──"
  run_scanner_for_repo "$repo"
done

echo ""
echo "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"
if [[ $GLOBAL_EXIT -eq 0 ]]; then
  echo "  ✅ All scans passed. Results in: ${OUTPUT_BASE}/"
elif [[ $GLOBAL_EXIT -eq 1 ]]; then
  echo "  🟡 Warnings found. Review: ${OUTPUT_BASE}/"
else
  echo "  🔴 Critical/High findings. Review immediately: ${OUTPUT_BASE}/"
fi
echo "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"
echo ""

# ─── HTML REPORT ──────────────────────────────────────────────────────────────
generate_html_report() {
  local report_path="$OUTPUT_BASE/security-report.html"
  echo ""
  echo "  Generating HTML report..."
  python3 "$SKILL_DIR/scripts/generate-report.py" \
    --results-dir "$OUTPUT_BASE" \
    --config      "$CONFIG_PATH" \
    --output      "$report_path" \
    --workspace   "$(pwd)" \
    2>/dev/null
  if [[ -f "$report_path" ]]; then
    echo "  ✅ Report ready → $report_path"
    # Auto-open on macOS
    if [[ "$(uname -s)" == "Darwin" ]]; then
      open "$report_path" 2>/dev/null || true
    fi
  fi
}

generate_html_report

exit $GLOBAL_EXIT
