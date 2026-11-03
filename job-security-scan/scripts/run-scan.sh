#!/usr/bin/env bash
# run-scan.sh — Generic security scanner for any team/repo workspace.
#
# Usage:
#   run-scan.sh [--config path/to/repository.md] [--repo REPO_NAME] [--scanner SCANNER] [--host]
#               [--profile quick|standard|deep] [--since GIT_REF]
#
# Flags:
#   --config   Path to repository.md config file (default: auto-discover)
#   --repo     Scan one repo by name only (default: all active repos)
#   --scanner  Run one scanner only: gitleaks|trivy|semgrep|hadolint|osv|sbom|advisories|trufflehog|shai-hulud|all
#   --host     Also check THIS computer for the Shai-Hulud worm (projects under $HOME, global installs,
#              npm cache, credential stores). Alone (no --scanner), only the host check runs.
#   --profile  quick    = Gitleaks (working tree only), OSV, Shai-Hulud; nothing queued for verification
#              standard = every scanner; CRITICAL+HIGH queued for verification (default)
#              deep     = every scanner, Trivy also reports LOW; CRITICAL+HIGH+MEDIUM queued
#              --scanner still picks one scanner and overrides the profile's list.
#   --since    Report only findings in files changed since GIT_REF (committed REF...HEAD plus working-tree
#              changes). A partial run: no "fixed" list. Repos that are not git repos keep full scope.
#
# Reads all team/repo config from repository.md — no hardcoded values.
#
# Output: every run writes ./security-run-YYYYMMDD-HHMMSS/ in the folder it is run from, holding
# security-report.md, security-report.json, security-report.html and each tool's raw output.
# Caches live outside the workspace: $JOB_SECURITY_SCAN_CACHE > cache-dir: > (deprecated) output-dir:
# > ${XDG_CACHE_HOME:-$HOME/.cache}/job-security-scan.  SECURITY_RUN_ROOT moves the run folders (CI, tests).
# This script only reports: it never changes any scanned repo.

set -uo pipefail

# ─── Argument parsing ──────────────────────────────────────────────────────
SCANNER="all"
SCANNER_SET=0
PROFILE="standard"
SINCE=""
HOST_MODE=0
REPO_FILTER=""
CONFIG_PATH=""

while [[ $# -gt 0 ]]; do
  case "$1" in
    --config)   CONFIG_PATH="$2"; shift 2 ;;
    --repo)     REPO_FILTER="$2"; shift 2 ;;
    --scanner)  SCANNER="$2"; SCANNER_SET=1; shift 2 ;;
    -s)         SCANNER="$2"; SCANNER_SET=1; shift 2 ;;
    --host)     HOST_MODE=1;      shift ;;
    -r)         REPO_FILTER="$2"; shift 2 ;;
    --profile)  [[ $# -ge 2 ]] || { echo "--profile needs quick, standard or deep"; exit 1; }
                PROFILE="$2"; shift 2 ;;
    --since)    [[ $# -ge 2 ]] || { echo "--since needs a git ref"; exit 1; }
                SINCE="$2"; shift 2 ;;
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
CONFIG_SH="$(python3 -I "$SKILL_DIR/scripts/parse-config.py" "$CONFIG_PATH")" || { echo "❌ Invalid config: $CONFIG_PATH"; exit 1; }
eval "$CONFIG_SH"   # values are shell-quoted by parse-config.py

WORKSPACE="${MONOREPO_ROOT:-.}"
# Shared caches (vendor advisories, refreshed Shai-Hulud indicators) - never in the workspace by default.
CACHE_BASE="${JOB_SECURITY_SCAN_CACHE:-${CACHE_DIR:-${OUTPUT_DIR:-${XDG_CACHE_HOME:-$HOME/.cache}/job-security-scan}}}"
# The run folder is created in MAIN, once the arguments are known to be valid.
OUTPUT_BASE=""

ASSET_DIR="$SKILL_DIR/assets"

# ─── Determine repos to scan ───────────────────────────────────────────────
declare -a REPOS_TO_SCAN
if [[ $HOST_MODE -eq 1 && $SCANNER_SET -eq 0 && -z "$REPO_FILTER" ]]; then
  REPOS_TO_SCAN=()                      # --host alone: check this computer only
elif [[ -n "$REPO_FILTER" ]]; then
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

  local scope=(--log-opts "--all")
  if [[ "$PROFILE" == "quick" ]]; then
    scope=(--no-git)
    _log gitleaks "$repo" "Scanning the working tree for secrets (quick profile: no git history)..."
  else
    _log gitleaks "$repo" "Scanning full git history for secrets..."
  fi
  gitleaks detect \
    --source "$path" \
    "${scope[@]}" \
    --config "$ASSET_DIR/gitleaks.toml" \
    --report-format json \
    --report-path "$out" \
    --no-banner \
    --redact \
    --exit-code 1 \
    2>/dev/null
  local rc=$?
  if [[ $rc -eq 0 ]]; then
    _pass gitleaks "$repo" "No secrets found"
  else
    local count
    count=$(python3 -I -c 'import json, sys; print(len(json.load(open(sys.argv[1]))))' "$out" 2>/dev/null || echo "?")
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
  [[ "$PROFILE" == "deep" && "$sev" != *"LOW"* ]] && sev="LOW,$sev"

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
  count=$(python3 -I -c \
    'import json, sys; d=json.load(open(sys.argv[1])); print(len(d.get("results",[])))' "$out" \
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
  hadolint --config "$ASSET_DIR/hadolint.yaml" --format tty "$dockerfile" > "$out" 2>&1 || true

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
  count=$(python3 -I -c \
    'import json, sys; d=json.load(open(sys.argv[1])); print(sum(len(r.get("packages",[])) for r in d.get("results",[])))' "$out" \
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
  comps=$(python3 -I -c 'import json, sys; print(len(json.load(open(sys.argv[1])).get("components",[])))' "$sbom" 2>/dev/null || echo 0)
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
  count=$(python3 -I -c \
    'import json, sys; d=json.load(open(sys.argv[1])); print(sum(len(r.get("packages",[])) for r in d.get("results",[])))' "$out" \
    2>/dev/null || echo 0)
  if [[ "$count" -eq 0 ]]; then
    _pass sbom "$repo" "SBOM ($comps components) - no OSV vulnerabilities"
  else
    _warn sbom "$repo" "SBOM ($comps components): $count package(s) with CVEs - see $out"
  fi
}

# Vendor-first advisory engine: fetch once per run, then match every repo against the cache.
ADVISORY_CACHE=""
fetch_advisories_once() {
  [[ -n "$ADVISORY_CACHE" ]] && return
  ADVISORY_CACHE="$CACHE_BASE/advisories"
  mkdir -p "$ADVISORY_CACHE"
  [[ -n "${ADVISORY_OFFLINE:-}" ]] && return   # use committed advisories only (tests, air-gapped runs)
  # Network trouble must not break the scan: committed advisories (assets/advisories) still apply.
  python3 -I "$SKILL_DIR/scripts/fetch-advisories.py" --out "$ADVISORY_CACHE" \
    --only nodejs nextjs go cisa-kev endoflife ghsa \
    >"$OUTPUT_BASE/advisory-fetch.log" 2>&1 \
    || echo "  🟡 [advisories] some sources could not be fetched - see $OUTPUT_BASE/advisory-fetch.log"
}

run_advisories() {
  local repo="$1" path="$2"
  local out="$OUTPUT_BASE/$repo/advisories.json"
  mkdir -p "$(dirname "$out")"

  fetch_advisories_once

  local args=(--repo "$path" --cache "$ADVISORY_CACHE" --output "$out" --fail-on none)
  # What the Dockerfile base images really ship. Opt-in: it pulls and runs the image a scanned repo names,
  # so it only runs when JOB_SECURITY_SCAN_PROBE_IMAGES=1 (sandboxed: no network, read-only, no caps).
  local probed="$OUTPUT_BASE/$repo/runtime-probe.json"
  rm -f "$probed"
  if [[ "${JOB_SECURITY_SCAN_PROBE_IMAGES:-}" == "1" ]]; then
    python3 -I "$SKILL_DIR/scripts/probe-runtime.py" --repo "$path" --output "$probed" 2>&1 | sed 's/^/  /' || true
  else
    echo "  [advisories] $repo: Dockerfile base images not probed (set JOB_SECURITY_SCAN_PROBE_IMAGES=1 to run them, sandboxed)"
  fi
  [[ -s "$probed" ]] && args+=(--inventory "$probed")
  if has_tool trivy; then
    local sbom="$OUTPUT_BASE/$repo/advisories-sbom.cdx.json"
    trivy fs "$path" --scanners license --format cyclonedx --output "$sbom" --no-progress --quiet 2>/dev/null || true
    [[ -s "$sbom" ]] && args+=(--sbom "$sbom")
  fi

  _log advisories "$repo" "Matching vendor and aggregator advisories..."
  python3 -I "$SKILL_DIR/scripts/match.py" "${args[@]}" >"$OUTPUT_BASE/$repo/advisories.txt" 2>&1
  local rc=$?
  if [[ $rc -ne 0 ]]; then
    _warn advisories "$repo" "advisory matching failed - see $OUTPUT_BASE/$repo/advisories.txt"; return
  fi

  local crit_high actionable
  read -r crit_high actionable < <(python3 -I -c '
import json, sys
d = json.load(open(sys.argv[1]))
act = [f for f in d["findings"] if f["state"] != "pending"]
hard = ("affected", "affected-end-of-life", "end-of-life", "affected-if-condition-holds", "possibly-affected")
print(sum(1 for f in act if f["state"] in hard and f["severity"] in ("critical", "high")), len(act))
' "$out" 2>/dev/null || echo "0 0")
  if [[ "${crit_high:-0}" -gt 0 ]]; then
    _fail advisories "$repo" "$crit_high critical/high of $actionable applicable advisory(ies) - see $OUTPUT_BASE/$repo/advisories.txt"
  elif [[ "${actionable:-0}" -gt 0 ]]; then
    _warn advisories "$repo" "$actionable applicable advisory(ies) - see $OUTPUT_BASE/$repo/advisories.txt"
  else
    _pass advisories "$repo" "No applicable advisories"
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
  # TruffleHog has no redact flag: drop the secret values before the raw file stays in the run folder.
  python3 -I "$SKILL_DIR/scripts/lib/sanitize.py" trufflehog "$out" >/dev/null 2>&1 || : > "$out"

  local count verified
  # Use wc for total line count and tolerate grep's non-zero exit on zero matches.
  count=$(wc -l < "$out" 2>/dev/null | tr -d '[:space:]')
  count=${count:-0}
  verified=$(grep -ci '"verified": *true' "$out" 2>/dev/null || true)
  verified=${verified:-0}

  if [[ "$count" -eq 0 ]]; then
    _pass trufflehog "$repo" "No secrets detected"
  elif [[ "$verified" -gt 0 ]]; then
    _fail trufflehog "$repo" "$count secret(s) — $verified VERIFIED ACTIVE — see $out (values masked)"
  else
    _warn trufflehog "$repo" "$count unverified secret(s) — see $out"
  fi
}

# Shai-Hulud worm check (offline): known indicators = affected, worm-like install hooks = suspicious.
shai_hulud_iocs_args() {
  local cache="$CACHE_BASE/ioc/shai-hulud.json"
  [[ -s "$cache" ]] && echo "--iocs $cache"
}

_shai_hulud_result() {  # _shai_hulud_result <label> <rc> <txt>
  local label="$1" rc="$2" txt="$3"
  case "$rc" in
    0) _pass shai-hulud "$label" "No Shai-Hulud indicator or worm-like install hook" ;;
    1) _warn shai-hulud "$label" "SUSPICIOUS worm-like install behaviour - see $txt" ;;
    2) _fail shai-hulud "$label" "AFFECTED - known Shai-Hulud indicator - see $txt (runbook: references/remediation.md)" ;;
    *) _warn shai-hulud "$label" "scan error (exit $rc) - see $txt" ;;
  esac
}

run_shai_hulud() {
  local repo="$1" path="$2"
  local out="$OUTPUT_BASE/$repo/shai-hulud.json" txt="$OUTPUT_BASE/$repo/shai-hulud.txt"
  mkdir -p "$(dirname "$out")"
  _log shai-hulud "$repo" "Checking for Shai-Hulud worm indicators and install-hook behaviour..."
  # shellcheck disable=SC2046
  python3 -I "$SKILL_DIR/scripts/shai-hulud-scan.py" --repo "$path" --output "$out" --format text \
    $(shai_hulud_iocs_args) >"$txt" 2>&1
  _shai_hulud_result "$repo" $? "$txt"
}

run_shai_hulud_host() {
  local out="$OUTPUT_BASE/_host/shai-hulud.json" txt="$OUTPUT_BASE/_host/shai-hulud.txt"
  mkdir -p "$(dirname "$out")"
  echo ""
  echo "  ── this machine ($HOME) ──"
  _log shai-hulud "host" "Checking projects, global installs, npm cache and credential stores..."
  # shellcheck disable=SC2046
  python3 -I "$SKILL_DIR/scripts/shai-hulud-scan.py" --host --output "$out" --format text \
    $(shai_hulud_iocs_args) >"$txt" 2>&1
  _shai_hulud_result "host" $? "$txt"
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
    advisories) run_advisories "$repo" "$path" ;;
    trufflehog) run_trufflehog "$repo" "$path" ;;
    shai-hulud) run_shai_hulud "$repo" "$path" ;;
    all)
      if [[ "$PROFILE" == "quick" ]]; then
        run_gitleaks    "$repo" "$path"
        run_osv         "$repo" "$path"
        run_shai_hulud  "$repo" "$path"
        return
      fi
      run_gitleaks   "$repo" "$path"
      run_trivy      "$repo" "$path"
      run_semgrep    "$repo" "$path"
      run_hadolint   "$repo" "$path"
      run_osv        "$repo" "$path"
      run_sbom       "$repo" "$path"
      run_advisories "$repo" "$path"
      run_trufflehog "$repo" "$path"
      run_shai_hulud "$repo" "$path"
      ;;
    *)
      echo "Unknown scanner: $SCANNER"
      echo "Valid: gitleaks | trivy | semgrep | hadolint | osv | sbom | advisories | trufflehog | shai-hulud | all"
      exit 1
      ;;
  esac
}

# ─── MAIN ─────────────────────────────────────────────────────────────────
case "$SCANNER" in
  gitleaks|trivy|semgrep|hadolint|osv|sbom|advisories|trufflehog|shai-hulud|all) ;;
  *)
    echo "Unknown scanner: $SCANNER"
    echo "Valid: gitleaks | trivy | semgrep | hadolint | osv | sbom | advisories | trufflehog | shai-hulud | all"
    exit 1
    ;;
esac

case "$PROFILE" in
  quick|standard|deep) ;;
  *) echo "Unknown profile: $PROFILE (valid: quick | standard | deep)"; exit 1 ;;
esac
if [[ -n "$SINCE" ]] && ! [[ "$SINCE" =~ ^[A-Za-z0-9._/~^@{}+-]{1,200}$ && "$SINCE" != -* ]]; then
  echo "Invalid --since ref: $SINCE"
  exit 1
fi

# One self-contained folder per run, in the workspace folder; never overwrite an earlier run.
RUN_ROOT="${SECURITY_RUN_ROOT:-$PWD}"
RUN_STAMP="$(date +%Y%m%d-%H%M%S)"
OUTPUT_BASE="$RUN_ROOT/security-run-$RUN_STAMP"
n=2
while [[ -e "$OUTPUT_BASE" ]]; do OUTPUT_BASE="$RUN_ROOT/security-run-$RUN_STAMP-$n"; n=$((n+1)); done
mkdir -p "$OUTPUT_BASE" "$CACHE_BASE"
printf '*\n' > "$OUTPUT_BASE/.gitignore"   # keeps the run folder out of git without touching the repo's .gitignore
RUN_DIR="$OUTPUT_BASE"

echo ""
echo "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"
echo "  🔐 Security Scan — team: ${TEAM} | org: ${ORG}"
echo "  Profile  : ${PROFILE}$([[ $SCANNER_SET -eq 1 ]] && echo " (scanner: ${SCANNER})")"
[[ -n "$SINCE" ]] && echo "  Scope    : files changed since ${SINCE} (partial run)"
echo "  Repos    : ${REPOS_TO_SCAN[*]:-(none)}"
[[ $HOST_MODE -eq 1 ]] && echo "  Host     : this machine (Shai-Hulud check)"
echo "  Run      : ${OUTPUT_BASE}/"
echo "  Cache    : ${CACHE_BASE}/"
echo "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"


[[ $HOST_MODE -eq 1 ]] && run_shai_hulud_host

for repo in ${REPOS_TO_SCAN[@]+"${REPOS_TO_SCAN[@]}"}; do
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

# ─── REPORTS (Markdown + JSON + HTML) ─────────────────────────────────────────
generate_reports() {
  echo ""
  echo "  Generating reports..."
  local scope=()
  if [[ -n "$SINCE" ]]; then
    python3 -I "$SKILL_DIR/scripts/changed-files.py" --since "$SINCE" --repos-root "$WORKSPACE" \
      --out "$RUN_DIR/changed-files.json" ${REPOS_TO_SCAN[@]+"${REPOS_TO_SCAN[@]}"} \
      && scope=(--since "$SINCE" --changed-files "$RUN_DIR/changed-files.json") \
      || scope=(--since "$SINCE")
  fi
  if python3 -I "$SKILL_DIR/scripts/generate-report.py" \
      --results-dir "$RUN_DIR" \
      --profile     "$PROFILE" \
      ${scope[@]+"${scope[@]}"} \
      --out-dir     "$RUN_DIR" \
      --config      "$CONFIG_PATH" \
      --workspace   "$PWD" \
      --repos-root  "$WORKSPACE" \
      --home        "$HOME" \
      >"$RUN_DIR/report.log" 2>&1; then
    echo "  ✅ Markdown → $RUN_DIR/security-report.md"
    echo "  ✅ JSON     → $RUN_DIR/security-report.json"
    echo "  ✅ HTML     → $RUN_DIR/security-report.html"
    if [[ "$(uname -s)" == "Darwin" && -z "${CI:-}" ]]; then
      open "$RUN_DIR/security-report.html" 2>/dev/null || true
    fi
  else
    echo "  🟡 Report generation failed - see $RUN_DIR/report.log"
    [[ $GLOBAL_EXIT -lt 1 ]] && GLOBAL_EXIT=1
  fi
}

generate_reports

echo ""
echo "  📁 Run folder: $RUN_DIR"
echo ""

exit $GLOBAL_EXIT
