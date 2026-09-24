# jira-to-speckit: Turn a Jira Issue Into a Speckit-Ready Brief

## Overview

**jira-to-speckit** is a pure Jira reader, not an orchestrator. It fetches one Jira issue, compacts
it under strict size budgets so large tickets never overflow a caller's context, optionally writes
a full-fidelity snapshot of the raw ticket to a file the caller names, and returns a structured
brief plus a Jira-key-based feature name. Then it stops.

It never calls `speckit.specify`, `speckit.plan`, `speckit.tasks`, `speckit.implement`, or any
other Speckit/Spec Kit stage. It never runs a clarification or review loop. It never touches git
(no branches, no commits, no pushes, no PRs). It never creates or updates an execution report. All
of that belongs to the caller, typically the `speckit-auto` skill, which consumes this skill's
brief and owns every stage that follows: spec, plan, tasks, implementation, review, and commit.

If you invoke this skill directly and expect it to build you a feature end to end, it won't; it
hands back a brief and a suggested name, and your next step is to feed that into `speckit-auto` (or
your own pipeline) yourself.

## Quick Start

### 1. Prerequisites

- GitHub Copilot, Claude Code, or OpenCode (for accessing the skill)
- `.env` file in your repository root with these Jira credentials:
  ```env
  JIRA_URL=https://your-jira-instance.atlassian.net
  JIRA_USERNAME=your-email@company.com
  JIRA_API_TOKEN=your-api-token-here
  ```
- Network access to your Jira instance

### 2. Invoke with a Jira Issue

Use the skill with either a **Jira issue key** or a **browse URL**:

```
@jira-to-speckit DDM-1234
```

or

```
@jira-to-speckit https://jira.company.com/browse/DDM-1234
```

The skill will:
1. Fetch the Jira issue over the REST API using your `.env` credentials.
2. Run it through the compaction pipeline (see below) to stay within size budgets.
3. Optionally write a full-fidelity snapshot, if the caller supplied `ticket_output_path`.
4. Return the Compact Output Template (issue key, title, type, suggested Speckit name, ticket
   snapshot path, compact brief, open questions, truncation note) and end its turn.

Nothing else happens. No spec is created, no branch is made, no implementation runs. That's the
caller's job.

### 3. What You Get Back

Every invocation returns exactly this shape:

```
Jira issue key: DDM-1234
Jira title: Reduce DAR review time for compliance officers
Jira type: Story
Spec prefix: US-
Suggested Speckit name: US-DDM-1234-reduce-dar-review-time
Ticket snapshot: specs/US-DDM-1234-reduce-dar-review-time/ticket.md (or "not requested")
Compact brief:
  Compliance officers spend 8+ minutes per DAR review. We need to reduce this to
  under 3 minutes by pre-filtering rejected items and providing a summary scorecard.
  Acceptance criteria: search filters apply in <500ms, summary shows pass/fail count
  and risk level, rejected items are hidden by default.
Open questions:
  - Should we persist filter state across sessions?
  - Is risk level business-defined or computed from rejection reason?
  - Do we need an audit trail for filter changes?
Truncation note: Description was trimmed to 6000 chars; comments (5 records) were not fetched.
```

`Suggested Speckit name` preserves the Jira key so a caller-created spec folder stays traceable
back to the ticket:
- `US-DDM-1234-reduce-review-time` (stories and features)
- `Task-DDM-4567-fix-sync-error` (tasks and bugs)

The folder itself, and everything after it, is the caller's responsibility. This skill never
creates `specs/` content.

---

## Jira Compaction Pipeline: Handling Large Tickets

Large or verbose Jira issues can cause context overflow when passed directly to a downstream spec
step. jira-to-speckit runs a mandatory four-stage compaction pipeline before returning its brief:

### Stage 1: Normalize Source Text
- Convert Jira description from ADF (Atlassian Document Format) or wiki markup to plain text
- Remove boilerplate sections (system-generated templates, repeated headers, long URL lists)
- Collapse duplicate sentences and repeated acceptance criteria
- Keep only the minimum details needed for a strong spec

### Stage 2: Enforce Character Budgets
Before summarization, the skill applies these limits (configurable via `.env`):
- `JIRA_MAX_DESCRIPTION_CHARS`: 6,000 characters (default)
- `JIRA_MAX_INPUT_CHARS`: 12,000 characters (default)
- `JIRA_MAX_COMMENTS`: 5 comments (default, when `JIRA_FETCH_COMMENTS` is true)

Large descriptions are trimmed to the budget. Comments are fetched only if ambiguity remains and
are sampled to decision-bearing lines only.

### Stage 3: Prioritize Content for Spec Quality
The skill ranks content by relevance:
1. **Acceptance criteria** (must-haves for testing)
2. **Business goal** (why this work matters)
3. **Constraints and dependencies** (what we must respect)
4. **Status metadata** (lower priority)

Exact identifiers (Jira keys, office codes, system names, SLA values) are always preserved.
Implementation chatter unrelated to product behavior is discarded.

### Stage 4: Produce Bounded Compact Brief
The final compact brief must fit within `JIRA_MAX_OUTPUT_CHARS` (default 2,500 characters). If the
budget is still exceeded after all compaction, the skill returns a short brief plus up to 3
targeted clarification questions instead of expanding context, then still stops and returns
control to the caller.

---

## Optional: Full-Fidelity Ticket Snapshot

When the caller supplies a `ticket_output_path`, the skill writes an unabridged, human-readable
snapshot of the raw ticket (title, metadata, full description, acceptance criteria as written,
comments, attachment list) to that path **before** compaction runs, so nothing is lost to the
budgets above. The compact brief returned in chat never contains this raw content; only the file
path is echoed back. See [`SKILL.md`](SKILL.md) § "2b. Write the ticket snapshot" for the exact
frontmatter and section shape written.

If the caller omits `ticket_output_path`, no file is written and the output template reports
`Ticket snapshot: not requested`.

---

## Setup and Configuration

### Required: .env File

Create or update `.env` in your repository root:

```env
# Jira API credentials
JIRA_URL=https://your-jira-instance.atlassian.net
JIRA_USERNAME=your-email@company.com
JIRA_API_TOKEN=your-api-token-here

# Optional: Tuning for large tickets (defaults shown)
JIRA_MAX_INPUT_CHARS=12000
JIRA_MAX_DESCRIPTION_CHARS=6000
JIRA_MAX_OUTPUT_CHARS=2500
JIRA_FETCH_COMMENTS=false
JIRA_MAX_COMMENTS=5

# Optional: tuning for the ticket snapshot, when the caller requests one
JIRA_SNAPSHOT_COMMENTS=true
```

This skill never resolves a target repository, branch, or spec folder; it only reads `.env` for
Jira credentials and compaction tuning. Repository and spec-folder decisions belong to the caller.

---

## Naming Convention: Preserving Jira Context

The `Suggested Speckit name` this skill returns preserves the Jira key, so a caller-created spec
folder stays traceable back to Jira:

**Suggested Naming (applied by the caller, not this skill):**
- `specs/US-{JIRA-KEY}-{kebab-summary}/` (for stories and features)
- `specs/Task-{JIRA-KEY}-{kebab-summary}/` (for tasks, bugs, spikes)

**Prefix Selection:**
- Story, User Story, Feature, Requirement → `US-`
- Task, Sub-task, Bug, Spike, Tech Task → `Task-`

**Examples:**
- `US-DDM-1234-reduce-dar-review-time`
- `Task-DDM-4567-fix-sync-error-reporting`
- `US-DDM-9876-onboard-new-users`

---

## Security and Guardrails

jira-to-speckit enforces strict security and usability guardrails:

- **No secret exposure**: Jira tokens and `.env` values are never printed to chat, logs, or git output
- **No credential requests**: The skill never asks you to paste secrets into chat; credentials are always read from `.env` only
- **Preserved business identity**: Exact Jira IDs, office codes, system names, acceptance criteria, and dependencies are always preserved in the compacted brief
- **No raw Jira payloads in the return value**: Raw Jira JSON, full comment threads, or ADF trees are never passed back in the compact brief; the only place full-fidelity content can land is the optional `ticket_output_path` snapshot file, and even then its contents are never echoed into chat
- **Character budget enforcement**: Large tickets are always compacted to fit within budgets before the brief is returned
- **No git operations of any kind**: This skill never runs `git`, never creates branches, never commits, never pushes, and never opens pull requests — all of that is the caller's responsibility

---

## Common Workflows and Examples

### Workflow 1: Direct Invocation, Standalone

```bash
@jira-to-speckit DDM-1234
# Output: Compact Output Template printed, skill's turn ends here.
```
Nothing else happens automatically. If you want a spec, plan, and implementation, hand the
returned brief to `speckit-auto` (or run your own pipeline) as a separate step.

### Workflow 2: Large Jira Issue with Auto-Compaction

```bash
@jira-to-speckit https://jira.company.com/browse/DDM-4567
# Issue has 15,000-char description; skill compacts to 2,500 chars
# Output: Compact brief with truncation note, then the skill stops
```

### Workflow 3: Called From `speckit-auto` (Typical Usage)

`speckit-auto` invokes this skill with a `ticket_output_path`, scoped to only steps 1–5 of its
workflow (fetch, snapshot, compaction, prefix, name), then takes the returned brief, Jira key, and
open questions and drives every subsequent stage itself: spec, plan, tasks, implementation, review,
commit, and push. This skill has no visibility into, and does not participate in, any of those
later stages.

---

## Troubleshooting

**Issue: "401 Unauthorized" from Jira API**
- Check `.env` values: `JIRA_URL`, `JIRA_USERNAME`, `JIRA_API_TOKEN`
- Verify your API token is valid (generate a new one if needed)
- Confirm your Jira user has permission to view the issue

**Issue: "404 Issue Not Found"**
- Verify the Jira issue key is spelled correctly (e.g., `DDM-1234`, not `ddm-1234`)
- If using a URL, confirm the issue still exists

**Issue: "JIRA_MAX_OUTPUT_CHARS exceeded; emitting brief with clarification questions instead"**
- This is expected for very large or complex tickets
- Answer the 3 clarification questions to refine the scope before proceeding
- If needed, increase `JIRA_MAX_OUTPUT_CHARS` in `.env`, but this may increase the risk of context
  overflow in the caller that receives this brief

**Issue: Ticket snapshot was not written**
- Confirm the caller actually supplied `ticket_output_path` — without it, the skill reports
  `Ticket snapshot: not requested` by design
- Check the `Truncation note:` field; a failed write is reported there rather than aborting the run

---

## Best Practices

1. **Keep Jira tickets well-formatted**: Clear acceptance criteria, no duplicate text, and focused scope lead to faster, smaller compacted briefs
2. **Use comments for decisions, not chatter**: Only decision-bearing comments are fetched; implementation discussion can stay in Slack
3. **Monitor the truncation note**: If it reports heavy trimming, consider tightening the Jira ticket itself before re-invoking
4. **Let the caller own naming and folders**: This skill only suggests a name; don't expect it to create or manage `specs/` content
5. **Pass `ticket_output_path` when traceability matters**: Without it, the full ticket text is gone once the compact brief is returned

---

## Compatibility

- **Platforms**: macOS, Linux, Windows (with WSL or Git Bash)
- **Jira versions**: Jira Cloud and Server (7.0+) with REST API access
- **Network**: Requires outbound access to the Jira API endpoint only — no git or hosting access is needed
- **Agents**: GitHub Copilot, Claude Code, OpenCode, and compatible Copilot agents

### Installation Paths

- GitHub Copilot: `.github/skills/` or `~/.agents/skills/`
- Claude Code: `~/.claude/skills/`
- OpenCode: `~/.config/opencode/skills/` or `.opencode/skills/`
- Local: `~/.agents/skills/`

---

## References

- **Jira API Guide**: See [`references/JIRA_API.md`](references/JIRA_API.md) for detailed API usage
- **Full contract**: See [`SKILL.md`](SKILL.md) for the exact workflow, inputs, output template, and edge cases
- **Speckit Workflow**: The `speckit-auto` skill consumes this skill's brief and owns every stage
  that follows — spec, plan, tasks, implementation, review, and commit

This skill is self-contained: it reads nothing outside its own folder except the project `.env`,
so it works when installed on its own.
