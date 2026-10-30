# Jira API Reference

This reference supports the `jira-issue` skill. Uses Jira REST API v2 (same as `jira-to-speckit`,
for compatibility with existing automation) and Basic auth from `.env`. It covers the `.env`
fallback only: when a Jira/Atlassian MCP server is connected, the skill uses its tools instead
(SKILL.md step 1).

## Required Environment Variables

Read these from the repository root `.env` file:

- `JIRA_URL`
- `JIRA_USERNAME`
- `JIRA_API_TOKEN`

Optional:

- `JIRA_DEFAULT_PROJECT` — project key assumed for `create` requests that don't name one.

Load `.env` and call curl in the **same** shell invocation — shell state does not persist between
separate tool calls, so loading in one command and calling curl in the next sends empty
credentials. Use bash or zsh (Git Bash or WSL on Windows), not PowerShell.

```bash
while IFS='=' read -r k v || [ -n "$k" ]; do case $k in JIRA_*) v=${v%$'\r'}; v=${v#[\"\']}; v=${v%[\"\']}; export "$k=$v";; esac; done < .env
curl -sS -K <(printf 'user = "%s:%s"\n' "$JIRA_USERNAME" "$JIRA_API_TOKEN") -w '\nHTTP %{http_code}\n' ...
```

- **Never** use `curl -u "$JIRA_USERNAME:$JIRA_API_TOKEN"`: command arguments are visible to every
  process on the host via `ps`. `-K <(printf ...)` hands curl the credentials through a pipe
  (`printf` is a shell builtin, so they never reach argv or disk).
- The loop reads only `JIRA_*` lines as data — never `source` or `eval` `.env`, which would run
  any shell code in it. It strips a trailing `\r` (Windows CRLF would leave it in the token → 401)
  and one pair of surrounding quotes. `export` is a builtin, so values never reach argv.
- Do not build the environment with `export $(... | xargs)`; `xargs` puts each value in argv.
- A token containing `"` or `\` must be escaped for curl's config format; standard Jira API tokens
  do not contain either.
- The trailing `HTTP <code>` line is what the error handling below reads; Jira's 401 body is often
  empty, and a successful `PUT` has no body at all.

Every example below omits the `.env` loading line for brevity — put it in the same command,
never run it separately.

### Request bodies

Send JSON bodies through a quoted heredoc (`--data-binary @- <<'JIRA_BODY'`), not `-d '...'`. A
description containing an apostrophe breaks out of a single-quoted `-d` argument, and the quoted
heredoc stops the shell from expanding `$` or backticks in user text; the unusual delimiter keeps
a user line reading `JSON` from ending the body early. The body must still be valid
JSON: escape `"`, `\`, and newlines (`\n`) inside string values.

## Fetch an issue (update path, step 3.1)

```bash
curl -sS -K <(printf 'user = "%s:%s"\n' "$JIRA_USERNAME" "$JIRA_API_TOKEN") \
  -w '\nHTTP %{http_code}\n' \
  -H "Accept: application/json" \
  "$JIRA_URL/rest/api/2/issue/PAYR-31?fields=summary,description,issuetype,status,priority,labels,components,project"
```

## Create an issue (create path, step 7)

```bash
curl -sS -K <(printf 'user = "%s:%s"\n' "$JIRA_USERNAME" "$JIRA_API_TOKEN") \
  -w '\nHTTP %{http_code}\n' \
  -X POST \
  -H "Content-Type: application/json" \
  "$JIRA_URL/rest/api/2/issue" \
  --data-binary @- <<'JIRA_BODY'
{
  "fields": {
    "project": { "key": "PAYR" },
    "summary": "Issue title",
    "description": "Plain text or wiki markup body (API v2 uses plain string, not ADF)",
    "issuetype": { "name": "Story" }
  }
}
JIRA_BODY
```

Optional fields to include only when the user explicitly asked for them:

```json
"labels": ["label-one", "label-two"],
"priority": { "name": "Medium" },
"assignee": { "accountId": "<account-id>" },
"parent": { "key": "PAYR-1" }
```

Resolving an `accountId` for assignee (if the user names a person, not an ID):

```bash
curl -sS -K <(printf 'user = "%s:%s"\n' "$JIRA_USERNAME" "$JIRA_API_TOKEN") \
  -w '\nHTTP %{http_code}\n' \
  -H "Accept: application/json" \
  -G --data-urlencode "query=<name-or-email>" \
  "$JIRA_URL/rest/api/2/user/search"
```

Successful create response includes `"key"` (e.g. `"PAYR-45"`) and `"self"` — build the browse
URL as `{JIRA_URL}/browse/{key}`.

## Update an issue (update path, step 7)

```bash
curl -sS -K <(printf 'user = "%s:%s"\n' "$JIRA_USERNAME" "$JIRA_API_TOKEN") \
  -w '\nHTTP %{http_code}\n' \
  -X PUT \
  -H "Content-Type: application/json" \
  "$JIRA_URL/rest/api/2/issue/PAYR-31" \
  --data-binary @- <<'JIRA_BODY'
{
  "fields": {
    "summary": "New title",
    "description": "New full description body"
  }
}
JIRA_BODY
```

A successful `PUT` returns `204 No Content` — there is no response body to parse; re-fetch the
issue (the "Fetch an issue" call above) if you need to show the user the saved state.

## Discovering valid issue types for a project

```bash
curl -sS -K <(printf 'user = "%s:%s"\n' "$JIRA_USERNAME" "$JIRA_API_TOKEN") \
  -w '\nHTTP %{http_code}\n' \
  -H "Accept: application/json" \
  "$JIRA_URL/rest/api/2/issue/createmeta/PAYR/issuetypes"
```

Use this only if the interview needs to offer the project's actual configured issue types rather
than the common defaults (Story, Task, Bug). The older
`createmeta?projectKeys=...&expand=projects.issuetypes` form is deprecated on Jira Cloud.

## Error Handling

- `401` / `403`: credentials may be invalid, or the user lacks permission for that project/action.
- `404` (on fetch/update): the issue key doesn't exist — ask the user to confirm it.
- `400` (on create/update): a required field is missing or invalid for that issue type — the
  response body's `errors`/`errorMessages` names which one; surface it and ask the user for the
  value rather than retrying blindly.
- `5xx`: transient — ask the user to retry after a brief wait.

## URL to Issue Key Extraction

Supported Jira input formats:

- `PAYR-31`
- `https://your-domain.atlassian.net/browse/PAYR-31`
- `https://your-domain.atlassian.net/jira/software/c/projects/PAYR/issues/PAYR-31`

Extract the issue key from the final path segment or matching `browse`/`issues` path segment.
