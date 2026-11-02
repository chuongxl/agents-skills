#!/usr/bin/env bash
# run-shai-hulud-e2e.sh - real end-to-end test of the Shai-Hulud check: runs the real run-scan.sh
# (repo mode over every fixture, then --host against a generated fake home directory) and asserts
# verdicts, the HTML report, and that no secret value leaks into any output.
#
# Offline; needs only bash and python3. Run locally with:
#   bash job-security-scan/tests/e2e/run-shai-hulud-e2e.sh
set -uo pipefail

HERE="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
SKILL_DIR="$(cd "$HERE/../.." && pwd)"
FIX="$SKILL_DIR/tests/fixtures/shai-hulud"
WORK="$(mktemp -d)"
trap 'rm -rf "$WORK"' EXIT

FAILS=0
annotate() {
  [[ -n "${GITHUB_ACTIONS:-}" ]] || return 0
  local msg="${1:0:3500}"; msg="${msg//$'\n'/%0A}"; echo "::error::${msg}"
}
check() { # check <label> <command...>
  local label="$1"; shift
  local out
  if out=$("$@" 2>&1); then echo "  ok    $label"
  else echo "  FAIL  $label"; echo "$out" | sed 's/^/        /'; annotate "FAIL: $label"$'\n'"$out"; FAILS=$((FAILS+1)); fi
}
verdict_is() { # verdict_is <json> <expected>
  python3 -I - "$1" "$2" <<'PY'
import json, sys
got = json.load(open(sys.argv[1]))["verdict"]
sys.exit(0 if got == sys.argv[2] else print("verdict %s, expected %s" % (got, sys.argv[2])) or 1)
PY
}

# Indicator file with one extra PyPI release so the pypi-pin fixture exercises the PyPI path.
IOCS="$WORK/iocs.json"
python3 -I - "$SKILL_DIR/assets/ioc/shai-hulud.json" "$IOCS" <<'PY'
import json, sys
d = json.load(open(sys.argv[1]))
d["packages"].append({"ecosystem": "pypi", "name": "evil-pkg", "versions": ["9.9.9"], "wave": "mini-2026"})
json.dump(d, open(sys.argv[2], "w"))
PY

AFFECTED=(infected-lockfile infected-node-modules planted-workflow pypi-pin)
SUSPICIOUS=(suspicious-hook)
CLEAN=(clean native-build husky-prepare)

CONFIG="$WORK/repository.md"
{
  printf -- '---\nteam: e2e\norg: e2e\nmonorepo-root: "%s"\nci-runner: x\nfail-on-severity: HIGH\nrepos:\n' \
    "$FIX"
  for r in "${AFFECTED[@]}" "${SUSPICIOUS[@]}" "${CLEAN[@]}"; do
    printf '  - name: %s\n    active: true\n    has-dockerfile: false\n' "$r"
  done
  printf -- '---\n'
} > "$CONFIG"

# Fake home: an infected project, a cached worm release, an npm token, a world-readable SSH key.
FAKE_TOKEN="npm_E2EFAKETOKENE2EFAKETOKENE2EFAKETOKEN"
HOME_DIR="$WORK/home"
mkdir -p "$HOME_DIR/work" "$HOME_DIR/.ssh" "$HOME_DIR/.npm/_cacache/index-v5/aa/bb"
cp -R "$FIX/infected-lockfile" "$HOME_DIR/work/app"
printf '//registry.npmjs.org/:_authToken=%s\n' "$FAKE_TOKEN" > "$HOME_DIR/.npmrc"
printf 'deadbeef\t{"key":"make-fetch-happen:request-cache:https://registry.npmjs.org/@accordproject/concerto-linter/-/concerto-linter-3.24.1.tgz"}\n' \
  > "$HOME_DIR/.npm/_cacache/index-v5/aa/bb/0001"
printf -- '-----BEGIN OPENSSH PRIVATE KEY-----\nAAAA\n-----END OPENSSH PRIVATE KEY-----\n' > "$HOME_DIR/.ssh/id_ed25519"
chmod 0644 "$HOME_DIR/.ssh/id_ed25519"

echo "== real run-scan.sh --scanner shai-hulud --host"
( cd "$WORK" && HOME="$HOME_DIR" NPM_CONFIG_PREFIX="" SHAI_HULUD_IOCS="$IOCS" JOB_SECURITY_SCAN_CACHE="$WORK/cache" \
    bash "$SKILL_DIR/scripts/run-scan.sh" --config "$CONFIG" --scanner shai-hulud --host ) >"$WORK/scan.log" 2>&1
RC=$?
cat "$WORK/scan.log"

OUT="$(ls -1d "$WORK"/security-run-* 2>/dev/null | tail -1)"
echo "== assertions"
check "run-scan exits 2 when anything is affected"  test "$RC" -eq 2
for r in "${AFFECTED[@]}";   do check "repo $r: affected"   verdict_is "$OUT/$r/shai-hulud.json" affected;   done
for r in "${SUSPICIOUS[@]}"; do check "repo $r: suspicious" verdict_is "$OUT/$r/shai-hulud.json" suspicious; done
for r in "${CLEAN[@]}";      do check "repo $r: clean"      verdict_is "$OUT/$r/shai-hulud.json" clean;      done
check "host: affected"                              verdict_is "$OUT/_host/shai-hulud.json" affected
check "host: cached worm release found"             grep -q '"category": "cached-package"' "$OUT/_host/shai-hulud.json"
check "host: npm token presence reported"           grep -q 'has auth token: yes' "$OUT/_host/shai-hulud.json"
check "host: open SSH key permissions flagged"      grep -q '"category": "credential-permissions"' "$OUT/_host/shai-hulud.json"
check "console shows AFFECTED"                      grep -q 'AFFECTED' "$WORK/scan.log"
check "HTML report written"                         test -s "$OUT/security-report.html"
check "HTML report has shai-hulud rows"             grep -q 'shai-hulud' "$OUT/security-report.html"
check "HTML report shows this machine"              grep -q 'this machine' "$OUT/security-report.html"
check "HTML report names the worm release"          grep -q '@accordproject/concerto-linter' "$OUT/security-report.html"
check "run folder in the workspace folder"          test -n "$OUT" -a -d "$OUT"
check "run folder keeps itself out of git"          grep -qx '[*]' "$OUT/.gitignore"
check "no cache folder in the workspace"            test ! -e "$WORK/.security-scan-results"
check "Markdown report written"                     test -s "$OUT/security-report.md"
check "JSON report written"                         test -s "$OUT/security-report.json"
check "Markdown shows file:line for the worm release" grep -q 'package-lock.json:6' "$OUT/security-report.md"
check "every file finding located; no code on secret/credential rows" python3 -I "$HERE/assert-located.py" "$OUT/security-report.json"
check "no secret value anywhere in output"          bash -c "! grep -rq 'E2EFAKETOKEN' '$OUT' '$WORK/scan.log'"

echo
if [[ $FAILS -eq 0 ]]; then echo "shai-hulud e2e: all checks passed"; else echo "shai-hulud e2e: $FAILS check(s) failed"; fi
exit $((FAILS > 0))
