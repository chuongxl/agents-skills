---
name: jira-to-speckit
description: Fetch a Jira issue or Jira issue URL using credentials from `.env`, then compact the ticket into a Speckit-ready feature brief (title, business goal, acceptance criteria, constraints, open questions) plus a Jira-key-based feature name. Use when work starts from Jira and a caller (typically `speckit-auto`) needs a clean, size-bounded intake payload to drive its own spec/plan/task pipeline. This skill only reads Jira and produces that brief — it does not run Speckit stages, review loops, git operations, or track execution progress.
compatibility: Requires network access and Jira REST API access. Requires `.env` entries for `JIRA_URL`, `JIRA_USERNAME`, and `JIRA_API_TOKEN`.
metadata:
  author: Alex Nguyen
  version: "0.1.0"
---

# Jira to Speckit

Use this skill when a Jira ticket is the source of truth for a new feature, task, or change
request and a caller needs it turned into a Speckit-ready brief.

This skill is a **pure Jira reader**, not an orchestrator: it fetches one Jira issue, compacts it
under strict size budgets, and returns a structured brief plus a Jira-key-based feature name. It
never invokes `speckit.specify` or any other Speckit/Spec Kit command, never runs clarification or
review loops, never performs git operations, and never tracks an execution report — all of that is
owned by the caller (`speckit-auto`'s stage files, see
[../speckit-auto/references/shared/intake.md](../speckit-auto/references/shared/intake.md) and its
provider `stage-01-preflight-intake.md` files).

## What This Skill Does

- Reads Jira issue content from a Jira issue key or URL.
- Uses Jira credentials from the local repository `.env` file.
- Compacts the Jira ticket into a Speckit-friendly feature brief.
- Chooses a Speckit-style prefix (`US-`/`Task-`) and builds a Jira-key-based feature name.
- Applies a size-aware Jira compaction pipeline to prevent context overflow on large issues.
- Returns the brief in the fixed output template below and stops.

## What This Skill Does NOT Do

- Does not call `speckit.specify`, `speckit.plan`, `speckit.tasks`, `speckit.implement`, or any
  other Speckit/Spec Kit stage.
- Does not run spec/plan/tasks clarification or review loops.
- Does not resolve the target repository, create branches, commit, push, or open pull requests.
- Does not create or update an execution report.

If a caller needs any of the above, it is responsible for performing it itself after receiving this
skill's output.

## Required Inputs

- A Jira issue key such as `DDM-1234`, or a Jira browse URL.
- Access to the repository root `.env` file.
- Jira credentials in `.env`:
  - `JIRA_URL`
  - `JIRA_USERNAME`
  - `JIRA_API_TOKEN`

Optional `.env` tuning for large Jira tickets:
- `JIRA_MAX_INPUT_CHARS` (default `12000`)
- `JIRA_MAX_DESCRIPTION_CHARS` (default `6000`)
- `JIRA_MAX_OUTPUT_CHARS` (default `2500`)
- `JIRA_FETCH_COMMENTS` (default `false`)
- `JIRA_MAX_COMMENTS` (default `5`)

## Guardrails

- Do not ask the user to paste secrets into chat.
- If the Jira environment variables are missing, stop and instruct the user to add them to `.env` locally.
- Keep the result business-focused; remove implementation noise, vendor chatter, and duplicate ticket text.
- Preserve exact Jira IDs, business terms, office codes, acceptance criteria, and dependencies.
- Never print tokens or `.env` values in logs or chat output.
- Never pass raw Jira payloads, full comment threads, or full ADF trees back to the caller.
- Always enforce character budgets before producing the compact brief.

## Workflow

### 1. Resolve the Jira issue

- Accept either a Jira issue key or a browse URL.
- If a URL is provided, extract the issue key from the URL path.
- Treat the Jira issue key as the canonical ID for naming.

### 2. Read Jira credentials from `.env`

Load the repository `.env` file and confirm these values exist:

- `JIRA_URL`
- `JIRA_USERNAME`
- `JIRA_API_TOKEN`

Use the Jira REST API with basic authentication.

Suggested endpoint (stage 1, required):

- `GET {JIRA_URL}/rest/api/2/issue/{issueKey}?fields=summary,description,issuetype,status,priority,labels,components,assignee,reporter,fixVersions,project,parent`

Optional endpoint (stage 2, only when needed by ambiguity):

- `GET {JIRA_URL}/rest/api/2/issue/{issueKey}/comment?maxResults={JIRA_MAX_COMMENTS}`

If the Jira API returns an error:
- `401` or `403`: inform the user that credentials may be invalid or they may not have permission.
- `404`: ask the user to confirm the Jira issue key.
- `5xx`: ask the user to retry after a brief wait.

### 3. Compact the Jira ticket

Turn the Jira issue into a short, structured brief with these parts:

- Title
- Problem or opportunity
- Business goal
- Primary user or actor
- Expected behavior
- Acceptance criteria
- Constraints and dependencies
- Open questions, if any

Rules:

- Prefer business language over implementation language.
- Keep only the details needed to write a strong spec.
- Limit open questions to at most 3.
- If the issue includes multiple stories, identify the primary story and note the rest as follow-up scope.

Large-ticket compaction pipeline (MANDATORY):

1. Normalize source text:
  - Convert Jira description from ADF/wiki formats to plain text.
  - Remove boilerplate sections (system templates, repeated headers, long URL lists, signatures).
  - Collapse duplicated sentences and repeated acceptance criteria.

2. Enforce budgets before summarization:
  - Trim description to `JIRA_MAX_DESCRIPTION_CHARS` (default `6000`).
  - Keep total Jira input to `JIRA_MAX_INPUT_CHARS` (default `12000`).
  - If comments are enabled, keep only latest `JIRA_MAX_COMMENTS` and only decision-bearing lines.

3. Prioritize content for spec quality:
  - Rank by relevance: acceptance criteria > business goal > constraints/dependencies > status metadata.
  - Keep exact identifiers (Jira key, office codes, system names, enums, SLA values).
  - Discard implementation chatter not needed for product behavior.

4. Produce bounded compact brief:
  - Final compact brief must stay within `JIRA_MAX_OUTPUT_CHARS` (default `2500`).
  - If budget is still exceeded, emit a short brief plus up to 3 targeted clarification questions instead of expanding context.

### 4. Choose the Speckit prefix

Use the Jira issue type to choose the prefix:

- Story, User Story, Feature, Requirement -> `US-`
- Task, Sub-task, Bug, Spike, Tech Task -> `Task-`

If the issue type is unclear, choose the closest actionable prefix and explain the choice.

### 5. Build the Speckit name

Use this format:

- `US-{JIRA-KEY}-{kebab-summary}`
- `Task-{JIRA-KEY}-{kebab-summary}`

Examples:

- `US-DDM-1234-reduce-dar-review-time`
- `Task-DDM-4567-fix-sync-error-reporting`

The Jira key must stay in the name so any spec folder the caller creates from it is easy to trace
back to Jira.

### 6. Return the output and stop

Produce the Compact Output Template below and end the skill's turn. Do not continue into any
Speckit stage, review loop, git action, or execution report — that is the caller's responsibility.

## Compact Output Template

Always return the result in this exact shape:

- Jira issue key:
- Jira title:
- Jira type:
- Spec prefix:
- Suggested Speckit name:
- Compact brief:
- Open questions:
- Truncation note: (state what was truncated/sampled when budgets were applied)

## Common Edge Cases

- **Jira URL instead of key**: extract the key and continue.
- **Missing env vars**: stop and ask the user to populate `.env` locally.
- **Large description**: summarize into the minimum set of spec-ready bullets.
- **Very large ticket or comment-heavy issue**: use stage-1 fields first, then fetch capped comments only if ambiguity remains.
- **Multiple acceptance criteria formats**: normalize them into plain, testable behavior statements.
- **Epic or parent issue**: use the nearest actionable child story or task as the source for the spec.
- **Epic with no child stories/tasks**: ask the user whether to compact the Epic directly or wait until child issues are created.

## References

- [Jira API guide](references/JIRA_API.md)
