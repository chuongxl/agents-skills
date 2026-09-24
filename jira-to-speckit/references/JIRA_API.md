# Jira API Reference

This reference supports the `jira-to-speckit` skill.

## Required Environment Variables

Read these from the repository `.env` file:

- `JIRA_URL`
- `JIRA_USERNAME`
- `JIRA_API_TOKEN`

## Fetching an Issue

Use Jira REST API v2 for compatibility with the existing DDM automation scripts.
Always fetch in stages to control context size.

Never pass `$JIRA_API_TOKEN` on the curl command line (`-u user:$JIRA_API_TOKEN`). Command
arguments are visible to other processes on the same host via `ps`. Pass credentials through a
curl config file read from stdin (`-K -`) instead, so the token never appears in argv or on disk:

Stage 1 (required, minimal fields):

```bash
curl -K - \
  -H "Accept: application/json" \
  "$JIRA_URL/rest/api/2/issue/DDM-1234?fields=summary,description,issuetype,status,priority,labels,components,assignee,reporter,fixVersions,project,parent" <<CURLCFG
user = "$JIRA_USERNAME:$JIRA_API_TOKEN"
CURLCFG
```

Stage 2 (optional, only if stage 1 leaves ambiguity):

```bash
curl -K - \
  -H "Accept: application/json" \
  "$JIRA_URL/rest/api/2/issue/DDM-1234/comment?maxResults=5" <<CURLCFG
user = "$JIRA_USERNAME:$JIRA_API_TOKEN"
CURLCFG
```

Do not fetch unlimited comments by default.

## URL to Issue Key Extraction

Supported Jira input formats:

- `DDM-1234`
- `https://your-domain.atlassian.net/browse/DDM-1234`
- `https://your-domain.atlassian.net/jira/software/c/projects/DDM/issues/DDM-1234`

Extract the Jira issue key from the final path segment or matching browse path.

## Recommended Compaction Fields

Use these fields as the minimum source set for Speckit input:

- `summary`
- `description`
- `issuetype`
- `status`
- `priority`
- `labels`
- `components`
- `fixVersions`
- `parent`

If comments are needed for context, prefer the latest relevant comments and summarize only the key decisions, constraints, or acceptance updates.

## Context Budget Defaults

Recommended limits for stable skill behavior:

- `JIRA_MAX_INPUT_CHARS=12000`
- `JIRA_MAX_DESCRIPTION_CHARS=6000`
- `JIRA_MAX_OUTPUT_CHARS=2500`
- `JIRA_FETCH_COMMENTS=false`
- `JIRA_MAX_COMMENTS=5`

Compaction policy:

- Convert description to plain text before summarizing.
- Remove boilerplate and repeated sections.
- Prioritize acceptance criteria, business goal, constraints, and dependencies.
- If output still exceeds budget, emit concise brief + up to 3 clarification questions.

## Naming Rule

Use the Jira issue key in the Speckit feature name:

- `US-DDM-1234-summary-slug`
- `Task-DDM-1234-summary-slug`

This keeps the generated `specs/` directory traceable to the Jira source ticket.
