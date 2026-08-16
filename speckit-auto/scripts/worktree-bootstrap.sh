#!/usr/bin/env bash
# worktree-bootstrap.sh — one-shot Stage 01 worktree + branch gate for speckit-auto.
#
# Mode 1 (bootstrap):  worktree-bootstrap.sh --branch <name>
#   Resolves base branch (develop -> main -> master, local then origin/*), syncs it best-effort,
#   ensures <repo-root>/.worktrees/ is gitignored, creates/reuses a linked worktree at
#   <repo-root>/.worktrees/<branch> with branch <branch> created from base if missing.
#
# Mode 2 (realign):    worktree-bootstrap.sh --rename-to <final-name>
#   Run from inside the linked worktree after intake resolves the final feature name:
#   renames the branch in place and moves the worktree to the canonical path when safe.
#
# Output: one compact JSON object on stdout. Exit 0 = ok (warnings are non-fatal),
# exit 1 = hard failure (missing base branch, branch checked out elsewhere, git error).
set -euo pipefail

warn_json() { printf '"%s"' "$(printf '%s' "$1" | tr -d '"' | tr '\n\r\t' ' ')"; }

BRANCH="" RENAME_TO=""
while [ $# -gt 0 ]; do
  case "$1" in
    --branch)    BRANCH="${2:?}"; shift 2 ;;
    --rename-to) RENAME_TO="${2:?}"; shift 2 ;;
    *) printf '{"ok":false,"error":"unknown argument: %s"}\n' "$1"; exit 1 ;;
  esac
done

REPO_ROOT="$(git rev-parse --show-toplevel 2>/dev/null)" || {
  printf '{"ok":false,"error":"not inside a git repository"}\n'; exit 1; }

if [ -n "$RENAME_TO" ]; then
  # ---- Mode 2: rename alignment (run from inside the linked worktree) ----
  # Resolve the MAIN repo root (inside a worktree, --show-toplevel returns the worktree itself).
  MAIN_ROOT="$(cd "$(dirname "$(git rev-parse --path-format=absolute --git-common-dir 2>/dev/null || git rev-parse --git-common-dir)")" && pwd)"
  WARN=()
  CUR="$(git rev-parse --abbrev-ref HEAD)"
  if [ "$CUR" != "$RENAME_TO" ]; then
    git branch -m "$RENAME_TO" || { printf '{"ok":false,"error":"git branch -m failed"}\n'; exit 1; }
  fi
  CANONICAL="$MAIN_ROOT/.worktrees/$RENAME_TO"
  WT_PATH="$(git rev-parse --show-toplevel)"
  if [ "$WT_PATH" != "$CANONICAL" ] && [ ! -e "$CANONICAL" ]; then
    if git -C "$MAIN_ROOT" worktree move "$WT_PATH" "$CANONICAL" 2>/dev/null; then
      WT_PATH="$CANONICAL"
    else
      WARN+=("worktree move failed; continuing on $WT_PATH")
    fi
  fi
  printf '{"ok":true,"branch":"%s","worktree_path":"%s","warnings":[' "$RENAME_TO" "$WT_PATH"
  first=1
  for w in "${WARN[@]:-}"; do
    [ -z "$w" ] && continue
    [ $first -eq 1 ] || printf ','
    first=0
    warn_json "$w"
  done
  printf ']}\n'
  exit 0
fi

[ -n "$BRANCH" ] || { printf '{"ok":false,"error":"--branch <name> required"}\n'; exit 1; }

# ---- Mode 1: bootstrap ----
WARN=()

# 1. Base branch: develop -> main -> master, local first, then origin/*.
BASE=""
for cand in develop main master; do
  if git show-ref --verify --quiet "refs/heads/$cand"; then BASE="$cand"; break; fi
done
if [ -z "$BASE" ]; then
  for cand in develop main master; do
    if git show-ref --verify --quiet "refs/remotes/origin/$cand"; then BASE="origin/$cand"; break; fi
  done
fi
[ -n "$BASE" ] || { printf '{"ok":false,"error":"missing base branch: none of develop/main/master exists"}\n'; exit 1; }
BASE_LOCAL="${BASE#origin/}"

# 2. Best-effort sync of a local base (never a hard stop).
if [ "$BASE" != "$BASE_LOCAL" ]; then
  : # remote-tracking base only — nothing to checkout/pull
else
  git fetch origin "$BASE_LOCAL" >/dev/null 2>&1 || WARN+=("fetch origin/$BASE_LOCAL failed; using local copy")
  git checkout "$BASE_LOCAL" >/dev/null 2>&1 || WARN+=("checkout $BASE_LOCAL failed")
  git pull --ff-only origin "$BASE_LOCAL" >/dev/null 2>&1 || WARN+=("pull origin/$BASE_LOCAL failed; using local copy")
fi
START_POINT="$BASE"

# 3. Ensure .worktrees/ is ignored (edit only; no separate commit).
GITIGNORE="$REPO_ROOT/.gitignore"
if [ ! -f "$GITIGNORE" ]; then
  printf '.worktrees/\n' > "$GITIGNORE" && WARN+=("created .gitignore with .worktrees/")
elif ! grep -qxE '\.worktrees/?' "$GITIGNORE"; then
  printf '.worktrees/\n' >> "$GITIGNORE" && WARN+=("appended .worktrees/ to .gitignore")
fi

# 4. Create/reuse linked worktree at the canonical path.
CANONICAL="$REPO_ROOT/.worktrees/$BRANCH"
REUSED=false
branch_exists() { git show-ref --verify --quiet "refs/heads/$BRANCH"; }
wt_branch() { git -C "$CANONICAL" rev-parse --abbrev-ref HEAD 2>/dev/null || true; }

if [ -d "$CANONICAL" ] && [ "$(wt_branch)" = "$BRANCH" ]; then
  REUSED=true
elif branch_exists; then
  if git branch --list "$BRANCH" --format='%(worktreepath)' | grep -q .; then
    printf '{"ok":false,"error":"branch %s is already checked out in another worktree"}\n' "$BRANCH"; exit 1
  fi
  git worktree add "$CANONICAL" "$BRANCH" >/dev/null 2>&1 || {
    printf '{"ok":false,"error":"git worktree add failed for existing branch %s"}\n' "$BRANCH"; exit 1; }
else
  git worktree add -b "$BRANCH" "$CANONICAL" "$START_POINT" >/dev/null 2>&1 || {
    printf '{"ok":false,"error":"git worktree add -b %s from %s failed"}\n' "$BRANCH" "$START_POINT"; exit 1; }
fi

# 5. Verify the branch is checked out inside the worktree.
CHECKED="$(git -C "$CANONICAL" rev-parse --abbrev-ref HEAD)"
[ "$CHECKED" = "$BRANCH" ] || { printf '{"ok":false,"error":"worktree at %s is on %s, expected %s"}\n' "$CANONICAL" "$CHECKED" "$BRANCH"; exit 1; }

printf '{"ok":true,"repo_root":"%s","base":"%s","branch":"%s","worktree_path":"%s","reused":%s,"warnings":[' \
  "$REPO_ROOT" "$BASE" "$BRANCH" "$CANONICAL" "$REUSED"
first=1
for w in "${WARN[@]:-}"; do
  [ -z "$w" ] && continue
  [ $first -eq 1 ] || printf ','
  first=0
  warn_json "$w"
done
printf ']}\n'
exit 0
