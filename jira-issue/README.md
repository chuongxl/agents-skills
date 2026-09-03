# jira-issue: Create or Update Jira Issues from Natural Language

## Overview

**jira-issue** turns a plain-language request into a Jira issue — either a brand-new one or an
update to an existing one — without ever writing to Jira on a guess. It classifies the request,
interviews you one question at a time for whatever's missing, renders the exact draft it's about to
send, and only writes after you explicitly confirm.

Unlike `jira-to-speckit` (which *reads* a ticket to seed a Speckit spec), this skill's only output
is the Jira issue itself: no spec folders, no git operations, no pipeline hand-off. It stops the
moment the issue is written and reports its key and URL.

## Quick Start

### 1. Prerequisites

- A `.env` file in your repository root with Jira credentials:
  ```env
  JIRA_URL=https://your-jira-instance.atlassian.net
  JIRA_USERNAME=your-email@company.com
  JIRA_API_TOKEN=your-api-token-here
  ```
- Network access to your Jira instance.

### 2. Invoke it

```
/jira-issue create a bug for the login page throwing a 500 on empty passwords
```

```
/jira-issue update PAYR-31 to add a note about the retry limit
```

The skill extracts a Jira key or `/browse/` URL to decide **create** vs. **update**, interviews you
for anything missing, shows the complete draft, and waits for an explicit "yes" before writing.

### 3. Confirm and get the result

Once you approve the draft, the skill writes to Jira and reports:

```
Created PAYR-52: https://your-jira-instance.atlassian.net/browse/PAYR-52
```

## Features

- **Create or update, one skill**: classifies the request from an issue key/URL plus intent
  language ("create" vs. "update"), and asks you to disambiguate when they conflict (e.g. "create a
  ticket similar to PAYR-31").
- **Structured interview**: for a create, gathers a summary and a structured description (goal,
  acceptance criteria, constraints) one question at a time; for an update, asks only about what's
  actually ambiguous (replace vs. append, which fields change).
- **Enhancement brainstorm (create only)**: after the interview, surfaces up to 3–5 suggestions
  grounded in the stated request — a missing edge case, an implied acceptance criterion, a
  relevant label or dependency — and folds in only what you explicitly accept.
- **Exact-draft confirmation gate**: always renders the literal title/body/fields it will send —
  never a paraphrase — and treats anything short of explicit approval as "keep refining."
- **No guessing on updates**: requires an explicit issue key or URL in the prompt; never searches
  Jira to find one.
- **Credential safety**: reads Jira credentials from `.env` only, never asks you to paste secrets
  into chat, and never prints them to logs or chat output.

## Installation

Copy the skill folder into your agent's skill location:

| Agent | Location |
|-------|----------|
| GitHub Copilot CLI | `~/.agents/skills/` |
| GitHub Copilot (repo) | `.github/skills/` |
| Claude Code | `~/.claude/skills/` |
| Claude Code (repo) | `.claude/skills/` |
| OpenCode | `~/.config/opencode/skills/` |

```bash
cp -r jira-issue ~/.agents/skills/
```

Restart your agent session so it's discovered.

## Compatibility

- **Platforms**: macOS, Linux, Windows (with WSL or Git Bash).
- **Jira versions**: Jira Cloud and Server (7.0+) with REST API v2 access.
- **Agents**: GitHub Copilot, Claude Code, OpenCode, and other agents that expose a shell/bash tool
  and a way to read a repo-local file. `allowed-tools: bash view` in the frontmatter maps to
  Copilot's tool names; Claude Code and OpenCode expose the same capabilities as `Bash` and `Read`.
- **Network**: requires outbound access to your Jira instance's REST API.

## Configuration

Required `.env` entries:

```env
JIRA_URL=https://your-jira-instance.atlassian.net
JIRA_USERNAME=your-email@company.com
JIRA_API_TOKEN=your-api-token-here
```

Optional:

```env
JIRA_DEFAULT_PROJECT=PAYR   # assumed project key for a create request that doesn't name one
```

When `JIRA_DEFAULT_PROJECT` is unset, the interview asks for the project instead of guessing.

## Examples

**Create, unambiguous type:**
```
/jira-issue file a bug: search results page crashes when filter list is empty
→ interview for summary/description details
→ brainstorm: "1) Add an edge case for a filter list that's empty vs. missing entirely.
   2) Note the browser/version this was seen on as a constraint. Fold in which ones?"
→ user: "1" → draft shown (includes the accepted suggestion) → confirm → PAYR-53 created
```

**Update, existing key:**
```
/jira-issue update PAYR-31 to add a note about the retry limit
→ fetches PAYR-31 → asks whether to replace or append the description → draft shown → confirm → PAYR-31 updated
```

**Ambiguous type:**
```
/jira-issue log this as a Jira story for adding CSV export
→ asks: Story, Task, or Bug? → continues interview
```

## Troubleshooting

**"Missing `.env` keys"** — populate `JIRA_URL`, `JIRA_USERNAME`, `JIRA_API_TOKEN` in the
repository root `.env`; the skill stops before starting the interview until all three are present.

**"401/403 from Jira"** — the API token is invalid or lacks permission for that project/action;
generate a fresh token and confirm project access.

**"404 on update"** — the issue key wasn't found; double-check the key or URL you passed in.

**"400 on create/update"** — Jira's response names a missing or invalid field for that issue type;
the skill surfaces the exact error and asks which value to use rather than dropping the field.

**Multiple issues in one prompt** — only the first is handled; re-run the skill for the rest.

## References

- [Jira API guide](references/JIRA_API.md)
