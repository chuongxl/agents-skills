# Fallback: Direct Jira Fetch

Load **only** if the `jira-to-speckit` skill is unavailable in this session. The normal `--issue`
path never loads this file.

1. Read the project-root `.env`: `JIRA_URL`, `JIRA_USERNAME`, `JIRA_API_TOKEN`. Any missing → stop
   and ask the user to complete it, **without printing any value**.
2. Fetch. Never pass the token on the curl command line (`-u user:$JIRA_API_TOKEN`); it would show
   up in `ps` for any other process on the host. Pass credentials through a curl config file read
   from stdin instead:
   ```bash
   curl -K - \
     -H "Accept: application/json" \
     "$JIRA_URL/rest/api/2/issue/$issueKey?fields=summary,description,issuetype,status,priority,labels,assignee,fixVersions" <<CURLCFG
   user = "$JIRA_USERNAME:$JIRA_API_TOKEN"
   CURLCFG
   ```
   Errors: 401/403 → auth problem; 404 → ask the user to confirm the key; 5xx → retry later.
3. Write the ticket snapshot yourself to `.speckit/intake/<issue_id>-ticket.md` in the same shape
   `jira-to-speckit` produces (title, type/status/priority, description, acceptance criteria,
   labels, links).
4. Compact into `summary` / `goal` / `acceptance criteria` / `constraints` / `open questions` and
   carry **only** that compact brief forward. Keep the raw API payload out of live context.
5. Continue Stage 01 in the same turn — never stop just because the fallback was used.
