#!/usr/bin/env bash
# install-tools.sh — Install the free security scanners used by job-security-scan.
#
# Supply-chain rules (this skill scans for supply-chain attacks; its installer must not be one):
#   * every tool is pinned to an exact version below - never "latest", never a branch;
#   * on Linux each download is checked against the SHA-256 committed in assets/tool-checksums.txt before it
#     is installed - not against a checksum file fetched from the same release as the binary;
#   * every tool, freshly installed or already on this machine, must report the pinned version. A different
#     version is a failure (JOB_SECURITY_SCAN_ALLOW_VERSION_DRIFT=1 turns that into a warning, e.g. for a
#     Homebrew formula that has moved on); a known-malicious Trivy release is refused regardless;
#   * nothing downloaded is piped into a shell, and nothing from repository.md is eval'd unquoted;
#   * macOS uses Homebrew formulas (the official Trivy formula was not affected by the March 2026 compromise).
#     Homebrew installs its current version, so the version check above is what enforces the pin there.
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
CHECKSUMS="${JOB_SECURITY_SCAN_CHECKSUMS:-$SKILL_DIR/assets/tool-checksums.txt}"
ALLOW_DRIFT="${JOB_SECURITY_SCAN_ALLOW_VERSION_DRIFT:-}"
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

# fetch_verified <url> <asset-name> <dest-file>
# Downloads <url> and keeps <dest-file> only if its SHA-256 equals the one committed for <asset-name>.
fetch_verified() {
  local url="$1" asset="$2" dest="$3" expected actual
  expected="$(awk -v a="$asset" '$1 !~ /^#/ && NF==2 && $2==a {print $1; exit}' "$CHECKSUMS" 2>/dev/null)"
  if [[ ! "$expected" =~ ^[0-9a-f]{64}$ ]]; then
    echo "  ⛔ no pinned checksum for $asset in $CHECKSUMS - not installed" >&2
    return 1
  fi
  curl -fsSL --proto '=https' --retry 2 -o "$dest" "$url" || return 1
  actual="$(sha256_of "$dest")"
  if [[ "$expected" != "$actual" ]]; then
    echo "  ⛔ checksum mismatch for $asset (expected $expected, got $actual) - not installed" >&2
    rm -f "$dest"
    return 1
  fi
}

# installed_version <tool>  - the x.y.z the binary on PATH (or in INSTALL_DIR) reports, or nothing
installed_version() {
  local tool="$1" bin args
  bin="$(command -v "$tool" 2>/dev/null || true)"
  [[ -z "$bin" && -x "$INSTALL_DIR/$tool" ]] && bin="$INSTALL_DIR/$tool"
  [[ -n "$bin" ]] || return 0
  case "$tool" in gitleaks) args=(version) ;; *) args=(--version) ;; esac
  "$bin" "${args[@]}" 2>&1 | grep -oE '[0-9]+\.[0-9]+\.[0-9]+' | head -n1 || true
}

# verify_version <tool> <pinned>  - ok only when the tool reports the pinned version
verify_version() {
  local tool="$1" want="$2" got
  got="$(installed_version "$tool")"
  if [[ "$tool" == "trivy" && "$got" =~ ^0\.69\.[456]$ ]]; then
    fail "$tool" "version $got is a known-malicious release (GHSA-69fq-xp46-6x23) - remove it and rotate any secret it could reach"
  elif [[ "$got" == "$want" ]]; then
    ok "$tool"
  elif [[ -n "$got" && "$ALLOW_DRIFT" == "1" ]]; then
    echo "  🟡 $tool is $got, not the pinned $want - accepted (JOB_SECURITY_SCAN_ALLOW_VERSION_DRIFT=1)"
  else
    fail "$tool" "found version ${got:-unknown}, pinned is $want (set JOB_SECURITY_SCAN_ALLOW_VERSION_DRIFT=1 to accept after checking the release)"
  fi
}

# install_tarball <tool> <pinned-version> <url> <asset>   - binary named <tool> inside a .tar.gz
install_tarball() {
  local tool="$1" want="$2" url="$3" asset="$4" tmp
  tmp="$(mktemp -d)"
  if fetch_verified "$url" "$asset" "$tmp/$asset" \
     && tar -xzf "$tmp/$asset" -C "$tmp" "$tool" \
     && install -m 0755 "$tmp/$tool" "$INSTALL_DIR/$tool"; then
    verify_version "$tool" "$want"
  else
    fail "$tool" "download or checksum verification failed"
  fi
  rm -rf "$tmp"
}

# install_binary <tool> <pinned-version> <url> <asset>   - a release asset that is the binary itself
install_binary() {
  local tool="$1" want="$2" url="$3" asset="$4" tmp
  tmp="$(mktemp -d)"
  if fetch_verified "$url" "$asset" "$tmp/$asset" && install -m 0755 "$tmp/$asset" "$INSTALL_DIR/$tool"; then
    verify_version "$tool" "$want"
  else
    fail "$tool" "download or checksum verification failed"
  fi
  rm -rf "$tmp"
}

need_linux_arch() { [[ -n "$ARCH_GO" ]] || { fail "$1" "unsupported CPU $(uname -m)"; return 1; }; }

# brew_install <tool> <formula> <pinned-version>
brew_install() { if brew install "$2" >/dev/null 2>&1; then verify_version "$1" "$3"; else fail "$1" "brew install $2"; fi; }

echo ""
echo "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"
echo "  Security Scanner Installer — team: ${TEAM} | org: ${ORG}"
echo "  Pinned: trivy ${TRIVY_VERSION}, gitleaks ${GITLEAKS_VERSION}, trufflehog ${TRUFFLEHOG_VERSION},"
echo "          hadolint ${HADOLINT_VERSION}, osv-scanner ${OSV_SCANNER_VERSION}, semgrep ${SEMGREP_VERSION}"
echo "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"
echo ""
[[ "$OS" == "Darwin" ]] || mkdir -p "$INSTALL_DIR"

# 1. Trivy — CVE + secret + misconfig
if command -v trivy >/dev/null 2>&1; then verify_version trivy "$TRIVY_VERSION"
elif [[ "$OS" == "Darwin" ]]; then brew_install trivy trivy "$TRIVY_VERSION"
elif need_linux_arch trivy; then
  a="trivy_${TRIVY_VERSION}_Linux-${ARCH_TRIVY}.tar.gz"; r="$GH/aquasecurity/trivy/releases/download/v${TRIVY_VERSION}"
  install_tarball trivy "$TRIVY_VERSION" "$r/$a" "$a"
fi

# 2. Gitleaks — secrets in git history
if command -v gitleaks >/dev/null 2>&1; then verify_version gitleaks "$GITLEAKS_VERSION"
elif [[ "$OS" == "Darwin" ]]; then brew_install gitleaks gitleaks "$GITLEAKS_VERSION"
elif need_linux_arch gitleaks; then
  a="gitleaks_${GITLEAKS_VERSION}_linux_${ARCH_X}.tar.gz"; r="$GH/gitleaks/gitleaks/releases/download/v${GITLEAKS_VERSION}"
  install_tarball gitleaks "$GITLEAKS_VERSION" "$r/$a" "$a"
fi

# 3. TruffleHog — verified secrets
if command -v trufflehog >/dev/null 2>&1; then verify_version trufflehog "$TRUFFLEHOG_VERSION"
elif [[ "$OS" == "Darwin" ]]; then brew_install trufflehog trufflehog "$TRUFFLEHOG_VERSION"
elif need_linux_arch trufflehog; then
  a="trufflehog_${TRUFFLEHOG_VERSION}_linux_${ARCH_GO}.tar.gz"; r="$GH/trufflesecurity/trufflehog/releases/download/v${TRUFFLEHOG_VERSION}"
  install_tarball trufflehog "$TRUFFLEHOG_VERSION" "$r/$a" "$a"
fi

# 4. Hadolint — only if any repo has a Dockerfile
if [[ ${#DOCKERFILE_REPOS[@]} -gt 0 ]]; then
  if command -v hadolint >/dev/null 2>&1; then verify_version hadolint "$HADOLINT_VERSION"
  elif [[ "$OS" == "Darwin" ]]; then brew_install hadolint hadolint "$HADOLINT_VERSION"
  elif need_linux_arch hadolint; then
    a="hadolint-linux-${ARCH_HADO}"; r="$GH/hadolint/hadolint/releases/download/v${HADOLINT_VERSION}"
    install_binary hadolint "$HADOLINT_VERSION" "$r/$a" "$a"
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
  if command -v semgrep >/dev/null 2>&1; then verify_version semgrep "$SEMGREP_VERSION"; else
    # Own virtualenv, installed from the hash-locked set: semgrep and every transitive dependency are pinned
    # by SHA-256 (assets/semgrep-requirements.txt), so pip can never resolve something unreviewed.
    venv="${JOB_SECURITY_SCAN_TOOLS:-${XDG_DATA_HOME:-$HOME/.local/share}/job-security-scan}/semgrep-venv"
    log "Installing semgrep ${SEMGREP_VERSION} into $venv (requires Python 3.10+)..."
    if python3 -m venv "$venv" >/dev/null 2>&1 \
       && "$venv/bin/python" -m pip install --quiet --disable-pip-version-check --no-deps --require-hashes \
            -r "$SKILL_DIR/assets/semgrep-requirements.txt" >/dev/null 2>&1 \
       && mkdir -p "$INSTALL_DIR" 2>/dev/null && ln -sf "$venv/bin/semgrep" "$INSTALL_DIR/semgrep" 2>/dev/null; then
      verify_version semgrep "$SEMGREP_VERSION"
    else
      fail semgrep "hash-locked install failed (need Python 3.10+ and a writable INSTALL_DIR, e.g. INSTALL_DIR=~/.local/bin)"
    fi
  fi
else
  skip "semgrep"
fi

# 6. OSV-Scanner — every ecosystem (lockfiles are detected per repo)
if command -v osv-scanner >/dev/null 2>&1; then verify_version osv-scanner "$OSV_SCANNER_VERSION"
elif [[ "$OS" == "Darwin" ]]; then brew_install osv-scanner osv-scanner "$OSV_SCANNER_VERSION"
elif need_linux_arch osv-scanner; then
  a="osv-scanner_linux_${ARCH_GO}"; r="$GH/google/osv-scanner/releases/download/v${OSV_SCANNER_VERSION}"
  install_binary osv-scanner "$OSV_SCANNER_VERSION" "$r/$a" "$a"
fi

echo ""
if [[ ${#FAILED[@]} -eq 0 ]]; then
  echo "✅ All tools ready for team [${TEAM}]"
else
  echo "⚠️  Failed tools: ${FAILED[*]} — not installed, or not the pinned version (see above)"
fi
echo ""
