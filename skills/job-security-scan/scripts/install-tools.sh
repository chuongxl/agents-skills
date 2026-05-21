#!/usr/bin/env bash
# install-tools.sh — Install all free security scanners
# Reads stack from repository.md to skip irrelevant tools.
set -euo pipefail

SKILL_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
CONFIG="$SKILL_DIR/assets/repository.md"
OS="$(uname -s)"
FAILED=()

# Load config
eval "$(python3 "$SKILL_DIR/scripts/parse-config.py" "$CONFIG")"

log()  { echo "  [install] $*"; }
ok()   { echo "  ✅ $1 ready ($(command -v "$1"))"; }
skip() { echo "  ⏭️  $1 not needed for stack [$STACK] — skipping"; }
fail() { echo "  ❌ $1 failed to install"; FAILED+=("$1"); }

install_brew_linux() {
  local name="$1" brew_pkg="$2" linux_cmd="$3"
  if command -v "$name" &>/dev/null; then ok "$name"; return; fi
  log "Installing $name..."
  if [[ "$OS" == "Darwin" ]]; then
    brew install "$brew_pkg" 2>/dev/null && ok "$name" || fail "$name"
  else
    eval "$linux_cmd" 2>/dev/null && ok "$name" || fail "$name"
  fi
}

echo ""
echo "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"
echo "  Security Scanner Installer — team: ${TEAM} | org: ${ORG}"
echo "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"
echo ""

# 1. Trivy — always needed (CVE + secret + misconfig)
install_brew_linux trivy trivy \
  "curl -sfL https://raw.githubusercontent.com/aquasecurity/trivy/main/contrib/install.sh | sh -s -- -b /usr/local/bin"

# 2. Gitleaks — always needed (secrets)
install_brew_linux gitleaks gitleaks \
  "curl -sSfL https://github.com/gitleaks/gitleaks/releases/latest/download/gitleaks_linux_x64.tar.gz | tar -xz -C /usr/local/bin gitleaks"

# 3. TruffleHog — always needed (verified secrets)
install_brew_linux trufflehog trufflehog \
  "curl -sSfL https://raw.githubusercontent.com/trufflesecurity/trufflehog/main/scripts/install.sh | sh -s -- -b /usr/local/bin"

# 4. Hadolint — only if any repo has a Dockerfile
if [[ ${#DOCKERFILE_REPOS[@]} -gt 0 ]]; then
  if command -v hadolint &>/dev/null; then ok "hadolint"; else
    log "Installing hadolint..."
    if [[ "$OS" == "Darwin" ]]; then
      brew install hadolint 2>/dev/null && ok "hadolint" || fail "hadolint"
    else
      curl -sSfL -o /usr/local/bin/hadolint \
        "https://github.com/hadolint/hadolint/releases/latest/download/hadolint-Linux-x86_64" \
        && chmod +x /usr/local/bin/hadolint && ok "hadolint" || fail "hadolint"
    fi
  fi
else
  skip "hadolint"
fi

# 5. Semgrep — only if stack includes ts/js/py languages
NEEDS_SEMGREP=false
for s in "${SEMGREP_RULESETS[@]:-}"; do
  [[ "$s" == p/* ]] && NEEDS_SEMGREP=true && break
done
if [[ "$NEEDS_SEMGREP" == "true" ]]; then
  if command -v semgrep &>/dev/null; then ok "semgrep"; else
    log "Installing semgrep (requires Python 3.8+)..."
    pip3 install semgrep --quiet 2>/dev/null && ok "semgrep" || fail "semgrep"
  fi
else
  skip "semgrep"
fi

# 6. OSV-Scanner — only if package manager is yarn/npm/pnpm
if [[ "$PACKAGE_MANAGER" =~ ^(yarn|npm|pnpm)$ ]]; then
  if command -v osv-scanner &>/dev/null; then ok "osv-scanner"; else
    log "Installing osv-scanner..."
    if [[ "$OS" == "Darwin" ]]; then
      brew install osv-scanner 2>/dev/null && ok "osv-scanner" || fail "osv-scanner"
    else
      curl -sSfL -o /usr/local/bin/osv-scanner \
        "https://github.com/google/osv-scanner/releases/latest/download/osv-scanner_linux_amd64" \
        && chmod +x /usr/local/bin/osv-scanner && ok "osv-scanner" || fail "osv-scanner"
    fi
  fi
else
  skip "osv-scanner"
fi

echo ""
if [[ ${#FAILED[@]} -eq 0 ]]; then
  echo "✅ All tools ready for team [${TEAM}]"
else
  echo "⚠️  Failed tools: ${FAILED[*]} — those scanners will be skipped"
fi
echo ""
