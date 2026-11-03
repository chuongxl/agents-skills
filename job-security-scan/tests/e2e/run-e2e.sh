#!/usr/bin/env bash
# run-e2e.sh - real end-to-end test: run the real scanners on the fixture repos and assert
# the expected vulnerabilities are found per ecosystem.
#
# Needs network access plus osv-scanner v2 and trivy on PATH. Used by
# .github/workflows/job-security-scan-e2e.yml; run it locally with:
#   bash job-security-scan/tests/e2e/run-e2e.sh
set -uo pipefail

HERE="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
SKILL_DIR="$(cd "$HERE/../.." && pwd)"
FIX="$SKILL_DIR/tests/fixtures"
WORK="$(mktemp -d)"
trap 'rm -rf "$WORK"' EXIT

for t in osv-scanner trivy; do
  command -v "$t" >/dev/null || { echo "missing tool: $t"; exit 2; }
done

FAILS=0

# In GitHub Actions, surface failure details as annotations (readable without the raw log).
annotate() { # annotate <text>
  [[ -n "${GITHUB_ACTIONS:-}" ]] || return 0
  local msg="${1:0:3500}"
  msg="${msg//$'\n'/%0A}"
  echo "::error::${msg}"
}

check() { # check <label> <command...>
  local label="$1"; shift
  local out
  if out=$("$@" 2>&1); then
    echo "  ok    $label"
  else
    echo "  FAIL  $label"; echo "$out" | sed 's/^/        /'
    annotate "FAIL: $label"$'\n'"$out"
    FAILS=$((FAILS+1))
  fi
}

# Workspace config pointing at the fixtures; one entry per fixture repo.
CONFIG="$WORK/repository.md"
cat > "$CONFIG" <<EOF
---
team: e2e
org: e2e
monorepo-root: "$FIX"
ci-runner: ubuntu-latest
fail-on-severity: HIGH
repos:
  - name: maven-log4j
    active: true
    has-dockerfile: false
  - name: python-django
    active: true
    has-dockerfile: false
  - name: go-text
    active: true
    has-dockerfile: false
  - name: node-lodash
    active: true
    has-dockerfile: false
  - name: monorepo
    active: true
    has-dockerfile: false
  - name: unmapped-swift
    active: true
    has-dockerfile: false
---
EOF

echo "== real scan of fixtures (osv + sbom)"
# Each run writes its own security-run-<datetime>/ folder under $WORK; caches stay in $WORK/cache.
export SECURITY_RUN_ROOT="$WORK" JOB_SECURITY_SCAN_CACHE="$WORK/cache"
newest_run() { ls -1d "$WORK"/security-run-* 2>/dev/null | tail -1; }
for scanner in osv sbom; do
  ( cd "$WORK" && bash "$SKILL_DIR/scripts/run-scan.sh" --config "$CONFIG" --scanner "$scanner" ) >"$WORK/$scanner.log" 2>&1 || true
  cat "$WORK/$scanner.log"
  if [[ "$scanner" == osv ]]; then OSV_RUN="$(newest_run)"; else SBOM_RUN="$(newest_run)"; fi
done

OUT="$OSV_RUN"
A="python3 -I $HERE/assert-findings.py"
echo "== assertions"
check "maven:  log4j-core has Log4Shell"        $A "$OUT/maven-log4j/osv.json" org.apache.logging.log4j:log4j-core CVE-2021-44228
check "python: Django has CVE-2019-14234"       $A "$OUT/python-django/osv.json" django CVE-2019-14234
check "go:     x/text has CVE-2020-14040"       $A "$OUT/go-text/osv.json" golang.org/x/text CVE-2020-14040
check "node:   lodash has CVE-2020-8203"        $A "$OUT/node-lodash/osv.json" lodash CVE-2020-8203
check "monorepo: Maven part found"              $A "$OUT/monorepo/osv.json" org.apache.logging.log4j:log4j-core CVE-2021-44228
check "monorepo: Node part found"               $A "$OUT/monorepo/osv.json" lodash CVE-2020-8203
check "unmapped: SBOM produced"                 test -s "$SBOM_RUN/unmapped-swift/sbom.cdx.json"
check "unmapped: SBOM-matched finding"          $A "$SBOM_RUN/unmapped-swift/osv-sbom.json" github.com/apple/swift-nio-http2 CVE-2023-44487 GHSA-qppj-fm5r-hxr3
check "mapped repos skip the SBOM fallback"     test ! -e "$SBOM_RUN/maven-log4j/sbom.cdx.json"
check "osv and sbom runs used separate folders" test "$OSV_RUN" != "$SBOM_RUN"
for f in security-report.md security-report.json security-report.html; do
  check "osv run wrote $f"                      test -s "$OSV_RUN/$f"
done
check "every OSV finding located to a line"     python3 -I "$HERE/assert-located.py" "$OSV_RUN/security-report.json" osv
check "osv report validates (schema v2)"       python3 -I "$SKILL_DIR/scripts/validate-report.py" "$OSV_RUN/security-report.json"
check "sbom report validates (schema v2)"      python3 -I "$SKILL_DIR/scripts/validate-report.py" "$SBOM_RUN/security-report.json"
check "sbom run compared with the osv run"     python3 -I -c 'import json,sys; d=json.load(open(sys.argv[1])); sys.exit(0 if d["run"]["previous_run"] else 1)' "$SBOM_RUN/security-report.json"
check "osv findings queued for verification"   python3 -I "$SKILL_DIR/scripts/triage.py" queue "$OSV_RUN"

if [[ $FAILS -gt 0 ]]; then
  for f in "$OSV_RUN"/*/osv.stderr "$SBOM_RUN"/*/osv-sbom.stderr "$SBOM_RUN"/*/sbom.stderr; do
    [[ -s "$f" ]] && annotate "$(basename "$(dirname "$f")")/$(basename "$f"):"$'\n'"$(head -c 1500 "$f")"
  done
  for f in "$OSV_RUN/report.log" "$SBOM_RUN/report.log"; do
    [[ -s "$f" ]] && annotate "$(basename "$(dirname "$f")")/report.log:"$'\n'"$(tail -c 1500 "$f")"
  done
  annotate "scan logs:"$'\n'"$(cat "$WORK/osv.log" "$WORK/sbom.log" | grep -v '^$' | head -60)"
fi

echo
if [[ $FAILS -eq 0 ]]; then echo "e2e: all checks passed"; else echo "e2e: $FAILS check(s) failed"; fi
exit $((FAILS > 0))
