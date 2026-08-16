#!/usr/bin/env bash
# fetch_jira_issue.sh — one-shot Jira fetch for jira-to-speckit.
#
#   fetch_jira_issue.sh --key DDM-1234 --output <snapshot.md> [--env-file .env]
#
# Effects:
#   1. Reads JIRA_URL / JIRA_USERNAME / JIRA_API_TOKEN (+ optional budget vars) from the env file.
#      Credentials are never printed.
#   2. Fetches the issue once (fields needed for both snapshot and brief).
#   3. Writes the FULL-FIDELITY ticket snapshot markdown to --output (never to stdout).
#   4. Prints ONE bounded JSON on stdout with only brief-sized fields (trimmed description,
#      optional capped comments) — the raw payload never enters the model context.
#
# Exit 0 = ok (warnings possible). Exit 1 = hard error (missing creds, HTTP 401/403/404/5xx,
# network failure). Snapshot write failure is NOT fatal — reported via snapshot_written:false.
set -euo pipefail

KEY="" OUTPUT="" ENV_FILE=".env"
while [ $# -gt 0 ]; do
  case "$1" in
    --key)     KEY="${2:?}"; shift 2 ;;
    --output)  OUTPUT="${2:?}"; shift 2 ;;
    --env-file) ENV_FILE="${2:?}"; shift 2 ;;
    *) printf '{"ok":false,"error":"unknown argument: %s"}\n' "$1" >&2; exit 1 ;;
  esac
done
[ -n "$KEY" ] && [ -n "$OUTPUT" ] || { printf '{"ok":false,"error":"--key and --output are required"}\n' >&2; exit 1; }

# Load env file if present (never echo values).
if [ -f "$ENV_FILE" ]; then
  set -a; . "$ENV_FILE"; set +a
fi
if [ -z "${JIRA_URL:-}" ] || [ -z "${JIRA_USERNAME:-}" ] || [ -z "${JIRA_API_TOKEN:-}" ]; then
  printf '{"ok":false,"error":"missing Jira credentials in %s (JIRA_URL, JIRA_USERNAME, JIRA_API_TOKEN)"}\n' "$ENV_FILE" >&2
  exit 1
fi

FIELDS="summary,description,issuetype,status,priority,labels,components,assignee,reporter,fixVersions,project,parent,attachments,comment,created,updated,duedate"
URL="${JIRA_URL%/}/rest/api/2/issue/$KEY?fields=$FIELDS"

HTTP_CODE="$(curl -sS -o /tmp/jira_payload_$$.json -w '%{http_code}' \
  -u "$JIRA_USERNAME:$JIRA_API_TOKEN" -H 'Accept: application/json' "$URL" 2>/tmp/jira_curl_$$.err)" || {
  printf '{"ok":false,"error":"network error contacting Jira"}\n' >&2
  cat /tmp/jira_curl_$$.err >&2; rm -f /tmp/jira_curl_$$.err /tmp/jira_payload_$$.json
  exit 1
}
rm -f /tmp/jira_curl_$$.err

case "$HTTP_CODE" in
  200) ;;
  401|403) printf '{"ok":false,"error":"invalid credentials or insufficient permission","http_status":%s}\n' "$HTTP_CODE" >&2; rm -f /tmp/jira_payload_$$.json; exit 1 ;;
  404)     printf '{"ok":false,"error":"issue not found — confirm the issue key","http_status":404}\n' >&2; rm -f /tmp/jira_payload_$$.json; exit 1 ;;
  5*)      printf '{"ok":false,"error":"Jira server error — retry after a brief wait","http_status":%s}\n' "$HTTP_CODE" >&2; rm -f /tmp/jira_payload_$$.json; exit 1 ;;
  *)       printf '{"ok":false,"error":"unexpected HTTP status","http_status":%s}\n' "$HTTP_CODE" >&2; rm -f /tmp/jira_payload_$$.json; exit 1 ;;
esac

JIRA_KEY="$KEY" JIRA_BROWSE_URL="${JIRA_URL%/}/browse/$KEY" JIRA_OUTPUT="$OUTPUT" \
JIRA_MAX_DESCRIPTION_CHARS="${JIRA_MAX_DESCRIPTION_CHARS:-6000}" \
JIRA_SNAPSHOT_COMMENTS="${JIRA_SNAPSHOT_COMMENTS:-true}" \
JIRA_FETCH_COMMENTS="${JIRA_FETCH_COMMENTS:-false}" \
JIRA_MAX_COMMENTS="${JIRA_MAX_COMMENTS:-5}" \
JIRA_PAYLOAD_FILE="/tmp/jira_payload_$$.json" python3 <<'PY'
import json, os, re, sys
from datetime import datetime, timezone

payload = json.load(open(os.environ["JIRA_PAYLOAD_FILE"]))
os.unlink(os.environ["JIRA_PAYLOAD_FILE"])
f = payload.get("fields", {})

def text_of(node):
    """ADF node -> readable markdown (best effort, full fidelity pass-through for wiki strings)."""
    if node is None:
        return ""
    if isinstance(node, str):          # wiki markup description
        return node
    out, plain = [], []
    def walk(n):
        if isinstance(n, dict):
            t = n.get("type")
            if t == "text":
                txt = n.get("text", "")
                out.append(txt); plain.append(txt)
                return
            if t == "paragraph":
                for c in n.get("content", []): walk(c)
                out.append("\n\n"); return
            if t == "heading":
                out.append("#" * int(n.get("attrs", {}).get("level", 2)) + " ")
                for c in n.get("content", []): walk(c)
                out.append("\n\n"); return
            if t in ("bulletList", "numberedList"):
                for i, li in enumerate(n.get("content", []), 1):
                    mark = "-" if t == "bulletList" else f"{i}."
                    out.append(f"{mark} ")
                    walk(li); out.append("\n")
                out.append("\n"); return
            if t == "listItem":
                for c in n.get("content", []): walk(c)
                return
            if t == "codeBlock":
                lang = n.get("attrs", {}).get("language", "")
                out.append(f"\n```{lang}\n")
                for c in n.get("content", []):
                    if isinstance(c, dict) and c.get("type") == "text":
                        out.append(c.get("text", ""))
                out.append("\n```\n\n"); return
            if t == "blockquote":
                out.append("> ")
                for c in n.get("content", []): walk(c)
                out.append("\n"); return
            if t == "rule":
                out.append("\n---\n\n"); return
            if t == "table":
                for row in n.get("content", []):
                    cells = []
                    for hdr in row.get("content", []):
                        cell, keep = [], plain[:]
                        plain.clear()
                        for c in hdr.get("content", []): walk(c)
                        cells.append("".join(plain).strip()); plain[:] = keep
                    out.append("| " + " | ".join(cells) + " |\n")
                out.append("\n"); return
            for c in n.get("content", []): walk(c)
        elif isinstance(n, list):
            for c in n: walk(c)
    walk(node.get("doc", node) if isinstance(node, dict) else node)
    md = "".join(out)
    return re.sub(r"\n{3,}", "\n\n", md).strip()

def field(v, *path):
    for p in path:
        v = (v or {}).get(p)
    return v

desc_raw = f.get("description")
desc_md = text_of(desc_raw)
summary = f.get("summary") or ""
issue_type = field(f, "issuetype", "name") or ""
status = field(f, "status", "name") or ""
priority = field(f, "priority", "name") or ""
labels = f.get("labels") or []
components = [c.get("name") for c in f.get("components") or []]
assignee = field(f, "assignee", "displayName") or ""
reporter = field(f, "reporter", "displayName") or ""
parent = field(f, "parent", "key") or ""
fix_versions = f.get("fixVersions") or []
project = field(f, "project", "key") or ""
created, updated = f.get("created") or "", f.get("updated") or ""
comments = (f.get("comment") or {}).get("comments") or []
attachments = f.get("attachments") or []

# Acceptance-criteria extraction (distinct section in the description text).
ac_text = ""
m = re.search(r"(?ims)^#{0,6}\s*(?:h[1-6]\.\s*)?acceptance criteri(a|on)\s*:?\s*\n+(.*?)(?=\n#{1,6}\s|\n\Z|\Z)", desc_md)
if m:
    ac_text = m.group(2).strip()

# --- Snapshot file (full fidelity, never to stdout) ---
snapshot_ok, snapshot_err = True, ""
try:
    out_dir = os.path.dirname(os.path.abspath(os.environ["JIRA_OUTPUT"]))
    os.makedirs(out_dir, exist_ok=True)
    lines = ["---",
        f'jira_key: {os.environ["JIRA_KEY"]}',
        f'jira_url: {os.environ["JIRA_BROWSE_URL"]}',
        f'title: {summary}',
        f'issue_type: {issue_type}',
        f'status: {status}',
        f'priority: {priority}',
        f'labels: [{", ".join(labels)}]',
        f'components: [{", ".join(components)}]',
        f'assignee: {assignee}',
        f'reporter: {reporter}',
        f'parent: {parent}',
        f'fix_versions: [{", ".join(v.get("name", "") for v in fix_versions)}]',
        f'created: {created}',
        f'updated: {updated}',
        f'fetched_at: {datetime.now(timezone.utc).isoformat()}',
        "---", "",
        f"# {os.environ['JIRA_KEY']} — {summary}", "",
        "## Description", "", desc_md or "(empty)", ""]
    if ac_text and ac_text not in desc_md:
        lines += ["## Acceptance Criteria", "", ac_text, ""]
    if os.environ.get("JIRA_SNAPSHOT_COMMENTS", "true").lower() != "false":
        for c in comments[:50]:
            body = text_of(c.get("body"))
            lines += [f"### {field(c,'author','displayName') or 'Unknown'} — {c.get('created','')}", body or "", ""]
    if attachments:
        lines += ["## Attachments", ""] + [
            f"- {a.get('filename','?')} ({round((a.get('size') or 0)/1024)} KB, "
            f"uploaded by {field(a,'author','displayName') or 'Unknown'}, {a.get('created','')})"
            for a in attachments] + [""]
    with open(os.environ["JIRA_OUTPUT"], "w", encoding="utf-8") as fh:
        fh.write("\n".join(lines))
except Exception as e:  # snapshot failure is not fatal
    snapshot_ok, snapshot_err = False, str(e)

# --- Bounded brief JSON on stdout ---
max_desc = int(os.environ.get("JIRA_MAX_DESCRIPTION_CHARS") or 6000)
notes = []
desc_brief = desc_md[:max_desc]
if len(desc_md) > max_desc:
    notes.append(f"description trimmed to {max_desc} chars for the brief (full text in snapshot)")
ac_brief = ac_text[:2000]
if len(ac_text) > 2000:
    notes.append("acceptance criteria trimmed to 2000 chars for the brief (full text in snapshot)")

comments_brief = []
if os.environ.get("JIRA_FETCH_COMMENTS", "false").lower() == "true":
    n = int(os.environ.get("JIRA_MAX_COMMENTS") or 5)
    for c in comments[-n:]:
        body = text_of(c.get("body"))[:500]
        comments_brief.append({"author": field(c, "author", "displayName") or "",
                               "created": c.get("created", ""), "body": body})
    if comments and not comments_brief:
        notes.append("no comments available for brief")

result = {
    "ok": True,
    "key": os.environ["JIRA_KEY"],
    "summary": summary,
    "issue_type": issue_type,
    "status": status,
    "priority": priority,
    "labels": labels,
    "components": components,
    "assignee": assignee,
    "parent": parent,
    "project": project,
    "description_brief": desc_brief,
    "acceptance_criteria_brief": ac_brief,
    "comments_brief": comments_brief,
    "snapshot_written": snapshot_ok,
    "snapshot_path": os.environ["JIRA_OUTPUT"],
    "total_comment_count": len(comments),
    "truncation_note": "; ".join(notes) + (f"; snapshot write failed: {snapshot_err}" if not snapshot_ok else ""),
}
print(json.dumps(result, ensure_ascii=False))
PY
