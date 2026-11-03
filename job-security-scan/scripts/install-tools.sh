#!/usr/bin/env bash
# install-tools.sh — Install the free security scanners used by job-security-scan.
#
# Supply-chain rules (this skill scans for supply-chain attacks; its installer must not be one):
#   * every tool is pinned to an exact version below - never "latest", never a branch;
#   * on Linux each download is checked against the release's published SHA-256 sums before it is installed;
#   * nothing downloaded is piped into a shell, and nothing from repository.md is eval'd unquoted;
#   * macOS uses Homebrew formulas (the official Trivy formula was not affected by the March 2026 compromise).
# Trivy is pinned to v0.69.3 (an immutable release): v0.69.4 and images 0.69.4-0.69.6 were malicious
# (GHSA-69fq-xp46-6x23). Bump a version only after checking the release and its advisories.
#
# Usage: bash scripts/install-tools.sh [--config path/to/repository.md]
#        INSTALL_DIR=~/.local/bin bash scripts/install-tools.sh     (default /usr/local/bin)
set -euo pipefail

TRIVY_VERSION="0.69.3"
GITLEAKS_VERSION="8.30.1"
TRUFFLEHOG_VERSION="3.99.7"
HADOLINT_VERSION="2.15.1"
OSV_SCANNER_VERSION="2.7.0"
SEMGREP_VERSION="1.183.0"

SKILL_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
CONFIG="$SKILL_DIR/assets/repository.md"
[[ "${1:-}" == "--config" && -n "${2:-}" ]] && CONFIG="$2"
OS="$(uname -s)"
INSTALL_DIR="${INSTALL_DIR:-/usr/local/bin}"
GH="https://github.com"
FAILED=()

# Load config (values are shell-quoted by parse-config.py; stop if the config is rejected)
CONFIG_SH="$(python3 -I "$SKILL_DIR/scripts/parse-config.py" "$CONFIG")" || { echo "❌ Invalid config: $CONFIG"; exit 1; }
eval "$CONFIG_SH"

log()  { echo "  [install] $*"; }
ok()   { echo "  ✅ $1 ready ($(command -v "$1" || echo "$INSTALL_DIR/$1"))"; }
skip() { echo "  ⏭️  $1 not needed — skipping"; }
fail() { echo "  ❌ $1 failed to install${2:+: $2}"; FAILED+=("$1"); }

case "$(uname -m)" in
  x86_64|amd64)  ARCH_GO="amd64"; ARCH_X="x64";   ARCH_TRIVY="64bit";  ARCH_HADO="x86_64" ;;
  arm64|aarch64) ARCH_GO="arm64"; ARCH_X="arm64"; ARCH_TRIVY="ARM64";  ARCH_HADO="arm64" ;;
  *)             ARCH_GO="";      ARCH_X="";      ARCH_TRIVY="";       ARCH_HADO="" ;;
esac

sha256_of() {
  if command -v sha256sum >/dev/null 2>&1; then sha256sum "$1" | awk '{print $1}'; else shasum -a 256 "$1" | awk '{print $1}'; fi
}

# fetch_verified <url> <sums-url> <asset-name> <dest-file>
# Downloads <url> and the release's checksum file, and keeps <dest-file> only if the SHA-256 matches.
fetch_verified() {
  local url="$1" sums_url="$2" asset="$3" dest="$4" sums expected actual
  curl -fsSL --proto '=https,file' --retry 2 -o "$dest" "$url" || return 1
  sums="$(curl -fsSL --proto '=https,file' --retry 2 "$sums_url")" || { rm -f "$dest"; return 1; }
  expected="$(printf '%s\n' "$sums" | awk -v a="$asset" '{f=$2; sub(/^\*/, "", f)} f==a || (NF==1) {print $1; exit}')"
  actual="$(sha256_of "$dest")"
  if [[ -z "$expected" || "$expected" != "$actual" ]]; then
    echo "  ⛔ checksum mismatch for $asset (expected ${expected:-none}, got $actual) - not installed" >&2
    rm -f "$dest"
    return 1
  fi
}

# install_tarball <tool> <url> <sums-url> <asset>   - binary named <tool> inside a .tar.gz
install_tarball() {
  local tool="$1" url="$2" sums_url="$3" asset="$4" tmp
  tmp="$(mktemp -d)"
  if fetch_verified "$url" "$sums_url" "$asset" "$tmp/$asset" \
     && tar -xzf "$tmp/$asset" -C "$tmp" "$tool" \
     && install -m 0755 "$tmp/$tool" "$INSTALL_DIR/$tool"; then
    ok "$tool"
  else
    fail "$tool" "download or checksum verification failed"
  fi
  rm -rf "$tmp"
}

# install_binary <tool> <url> <sums-url> <asset>   - a release asset that is the binary itself
install_binary() {
  local tool="$1" url="$2" sums_url="$3" asset="$4" tmp
  tmp="$(mktemp -d)"
  if fetch_verified "$url" "$sums_url" "$asset" "$tmp/$asset" && install -m 0755 "$tmp/$asset" "$INSTALL_DIR/$tool"; then
    ok "$tool"
  else
    fail "$tool" "download or checksum verification failed"
  fi
  rm -rf "$tmp"
}

need_linux_arch() { [[ -n "$ARCH_GO" ]] || { fail "$1" "unsupported CPU $(uname -m)"; return 1; }; }

brew_install() { brew install "$2" >/dev/null 2>&1 && ok "$1" || fail "$1" "brew install $2"; }

echo ""
echo "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"
echo "  Security Scanner Installer — team: ${TEAM} | org: ${ORG}"
echo "  Pinned: trivy ${TRIVY_VERSION}, gitleaks ${GITLEAKS_VERSION}, trufflehog ${TRUFFLEHOG_VERSION},"
echo "          hadolint ${HADOLINT_VERSION}, osv-scanner ${OSV_SCANNER_VERSION}, semgrep ${SEMGREP_VERSION}"
echo "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"
echo ""
[[ "$OS" == "Darwin" ]] || mkdir -p "$INSTALL_DIR"

# 1. Trivy — CVE + secret + misconfig
if command -v trivy >/dev/null 2>&1; then ok trivy
elif [[ "$OS" == "Darwin" ]]; then brew_install trivy trivy
elif need_linux_arch trivy; then
  a="trivy_${TRIVY_VERSION}_Linux-${ARCH_TRIVY}.tar.gz"; r="$GH/aquasecurity/trivy/releases/download/v${TRIVY_VERSION}"
  install_tarball trivy "$r/$a" "$r/trivy_${TRIVY_VERSION}_checksums.txt" "$a"
fi

# 2. Gitleaks — secrets in git history
if command -v gitleaks >/dev/null 2>&1; then ok gitleaks
elif [[ "$OS" == "Darwin" ]]; then brew_install gitleaks gitleaks
elif need_linux_arch gitleaks; then
  a="gitleaks_${GITLEAKS_VERSION}_linux_${ARCH_X}.tar.gz"; r="$GH/gitleaks/gitleaks/releases/download/v${GITLEAKS_VERSION}"
  install_tarball gitleaks "$r/$a" "$r/gitleaks_${GITLEAKS_VERSION}_checksums.txt" "$a"
fi

# 3. TruffleHog — verified secrets
if command -v trufflehog >/dev/null 2>&1; then ok trufflehog
elif [[ "$OS" == "Darwin" ]]; then brew_install trufflehog trufflehog
elif need_linux_arch trufflehog; then
  a="trufflehog_${TRUFFLEHOG_VERSION}_linux_${ARCH_GO}.tar.gz"; r="$GH/trufflesecurity/trufflehog/releases/download/v${TRUFFLEHOG_VERSION}"
  install_tarball trufflehog "$r/$a" "$r/trufflehog_${TRUFFLEHOG_VERSION}_checksums.txt" "$a"
fi

# 4. Hadolint — only if any repo has a Dockerfile
if [[ ${#DOCKERFILE_REPOS[@]} -gt 0 ]]; then
  if command -v hadolint >/dev/null 2>&1; then ok hadolint
  elif [[ "$OS" == "Darwin" ]]; then brew_install hadolint hadolint
  elif need_linux_arch hadolint; then
    a="hadolint-Linux-${ARCH_HADO}"; r="$GH/hadolint/hadolint/releases/download/v${HADOLINT_VERSION}"
    install_binary hadolint "$r/$a" "$r/$a.sha256" "$a"
  fi
else
  skip "hadolint"
fi

# 5. Semgrep — pinned on PyPI
NEEDS_SEMGREP=false
for s in "${SEMGREP_RULESETS[@]:-}"; do
  [[ "$s" == p/* ]] && NEEDS_SEMGREP=true && break
done
if [[ "$NEEDS_SEMGREP" == "true" ]]; then
  if command -v semgrep >/dev/null 2>&1; then ok semgrep; else
    log "Installing semgrep ${SEMGREP_VERSION} (requires Python 3.9+)..."
    python3 -m pip install --quiet --user "semgrep==${SEMGREP_VERSION}" >/dev/null 2>&1 && ok semgrep || fail semgrep
  fi
else
  skip "semgrep"
fi

# 6. OSV-Scanner — every ecosystem (lockfiles are detected per repo)
if command -v osv-scanner >/dev/null 2>&1; then ok osv-scanner
elif [[ "$OS" == "Darwin" ]]; then brew_install osv-scanner osv-scanner
elif need_linux_arch osv-scanner; then
  a="osv-scanner_linux_${ARCH_GO}"; r="$GH/google/osv-scanner/releases/download/v${OSV_SCANNER_VERSION}"
  install_binary osv-scanner "$r/$a" "$r/osv-scanner_SHA256SUMS" "$a"
fi

echo ""
if [[ ${#FAILED[@]} -eq 0 ]]; then
  echo "✅ All tools ready for team [${TEAM}]"
else
  echo "⚠️  Failed tools: ${FAILED[*]} — those scanners will be skipped"
fi
echo ""
