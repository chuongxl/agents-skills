# find-python.sh - sourced by run-scan.sh and install-tools.sh (bash 3.2+; macOS, Linux, Windows Git Bash/WSL).
#
# Sets PY to a working Python 3.8+ and defines:
#   py <args>   run "$PY" -I <args>. Output has any Windows "\r\n" turned into "\n", so command substitutions and
#               `read` loops behave the same on every platform. The exit status is Python's own.
#   native_path <p> a path as native Python/Windows tools expect it (cygpath -m on Git Bash/MSYS, unchanged elsewhere)
#   abs_dir <d> absolute path of a directory; on Windows Git Bash the C:/... form that both bash and Python accept
#               (plain `pwd` would give /c/..., which native Python cannot open).
# Override the interpreter with PY=/path/to/python. "python3" on Windows is often a Microsoft Store stub that
# exits non-zero, so every candidate is run, not just looked up.
if [[ -z "${PY:-}" ]]; then
  for _c in python3 python py; do
    if command -v "$_c" >/dev/null 2>&1 && "$_c" -c 'import sys; sys.exit(0 if sys.version_info >= (3, 8) else 1)' >/dev/null 2>&1; then
      PY="$_c"; break
    fi
  done
  unset _c
fi
[[ -n "${PY:-}" ]] || { echo "❌ Python 3.8+ not found (tried python3, python, py). Install it from https://www.python.org/downloads/ and re-run." >&2; exit 1; }

py() { "$PY" -I "$@" | tr -d '\r'; return "${PIPESTATUS[0]}"; }

abs_dir() { (cd "$1" 2>/dev/null && { pwd -W 2>/dev/null || pwd; }); }

native_path() { if command -v cygpath >/dev/null 2>&1; then cygpath -m "$1"; else printf '%s' "$1"; fi; }
