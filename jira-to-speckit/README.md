# jira-to-speckit: Bridge Jira Issues to Speckit Workflow

## Overview

**jira-to-speckit** is the primary entry point for turning Jira issues into detailed specifications and implementation plans using the Speckit workflow. This skill acts as an orchestrator, automatically reading Jira tickets, compacting them to prevent context overflow, and then guiding users through a comprehensive 8-phase workflow that ensures requirements are clarified, planned, tested, and implemented with full traceability.

When you have a Jira ticket as your source of truth, jira-to-speckit eliminates manual handoff friction. It reads your Jira credentials from a local `.env` file, compacts large or verbose tickets into spec-ready briefs, creates a Speckit feature specification with the Jira key preserved in the folder structure, and then orchestrates review loops at every stage—specification, planning, test planning, and task generation—before implementation begins.

## Quick Start

### 1. Prerequisites

- GitHub Copilot or Claude Code (for accessing the skill)
- `.env` file in your repository root with these Jira credentials:
  ```env
  JIRA_URL=https://your-jira-instance.atlassian.net
  JIRA_USERNAME=your-email@company.com
  JIRA_API_TOKEN=your-api-token-here
  ```
- Git SSH access to your repository
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
1. Fetch the Jira issue and compact it into a spec-ready brief
2. Start the Speckit specification workflow
3. Guide you through clarification loops
4. Advance through planning, test planning, and task generation when you confirm each phase
5. Maintain a running execution report with progress, token usage, and cost estimates

### 3. Work With Your Generated Spec

Your spec is created under `specs/{PREFIX}-{JIRA-KEY}-{kebab-summary}/`, preserving the Jira key for easy traceability:
- `US-DDM-1234-reduce-review-time/` (for stories and features)
- `Task-DDM-4567-fix-sync-error/` (for tasks and bugs)

The execution report is updated at each phase and tracks cumulative progress, issues, and token usage.

---

## The 8-Phase Workflow

jira-to-speckit orchestrates a complete 8-phase workflow to move from Jira ticket to implementation, with explicit review gates at each phase:

### Phase 1: Intake
The skill reads your Jira issue (key or URL) and extracts essential fields: summary, description, issue type, priority, acceptance criteria, constraints, and optional comments. The Jira REST API is used with your credentials; no secrets are ever printed to chat.

### Phase 2: Clarification (Spec Review Loop)
After compacting the Jira ticket, the skill presents a concise brief to you and enters an interactive clarification loop. It asks targeted questions about scope, acceptance criteria, business goals, and terminology—one at a time—until ambiguities are resolved. The spec is a living draft during this phase. When you confirm the spec is ready, the skill automatically advances to Phase 3.

### Phase 3: Planning (speckit.plan)
The skill runs the plan phase, generating a technical approach and implementation strategy based on your confirmed spec. A plan review loop follows, asking clarification questions about technical choices, dependencies, and boundaries. When you confirm the plan is clear, the skill automatically advances to Phase 4.

### Phase 4: Test Planning (speckit.testplan)
A dedicated test-planning phase ensures unit test coverage, e2e journey coverage, and acceptance criteria traceability are explicit before tasks are generated. The test plan review loop asks questions about coverage strategy, integration boundaries, and service-specific validation. When you confirm the test plan is complete, the skill automatically advances to Phase 5.

### Phase 5: Task Generation (speckit.tasks)
The skill generates a sequenced task list for implementation. A task review loop asks clarification questions about task ordering, missing work items, and parallelization. When you confirm the task list is ready, the skill automatically advances to Phase 6.

### Phase 6: Implementation (speckit.implement)
The skill prepares the repository, creates or updates the feature branch, and implements the code changes in small, traceable commits aligned with your task list. Each commit includes a conventional commit message with the feature name and Jira key.

### Phase 7: Verification (speckit.verify)
A GO/NO-GO readiness report is generated, including code evidence, unit test evidence, e2e test evidence, and service command evidence. Any gaps are flagged for remediation.

### Phase 8: Reporting
The execution report is finalized with cumulative Copilot request counts, total input and output tokens, and a final cost estimate. The report is preserved in your spec folder for audit and billing purposes.

---

## Jira Compaction Pipeline: Handling Large Tickets

Large or verbose Jira issues can cause context overflow when passed directly to Speckit. jira-to-speckit implements a mandatory four-stage compaction pipeline to prevent this:

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

Large descriptions are trimmed to the budget. Comments are fetched only if ambiguity remains and are sampled to decision-bearing lines only.

### Stage 3: Prioritize Content for Spec Quality
The skill ranks content by relevance:
1. **Acceptance criteria** (must-haves for testing)
2. **Business goal** (why this work matters)
3. **Constraints and dependencies** (what we must respect)
4. **Status metadata** (lower priority)

Exact identifiers (Jira keys, office codes, system names, SLA values) are always preserved. Implementation chatter unrelated to product behavior is discarded.

### Stage 4: Produce Bounded Compact Brief
The final compact brief must fit within `JIRA_MAX_OUTPUT_CHARS` (default 2,500 characters). If the budget is still exceeded after all compaction, the skill emits a short brief plus up to 3 targeted clarification questions instead of expanding context.

**Example Compact Brief Output:**
```
Jira issue key: DDM-1234
Jira title: Reduce DAR review time for compliance officers
Jira type: Story
Spec prefix: US-
Suggested Speckit name: US-DDM-1234-reduce-dar-review-time
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

# Optional: Xray credentials, only needed when xray_tests is requested
XRAY_CLIENT_ID=your-xray-client-id
XRAY_CLIENT_SECRET=your-xray-client-secret
```

### Optional: Xray Read Mode

Since v0.3.0, the skill can additionally export the Xray tests that cover the Jira issue. This is
off by default and changes nothing about the `0.2.0` brief-and-snapshot behaviour when unused.

Three optional inputs control it:

| Input | Default | Meaning |
|---|---|---|
| `xray_tests` | `false` | Set `true` to export covering Xray tests after the brief is produced. |
| `xray_output_path` | none | Path to write covering Cucumber tests as one concatenated `.feature` file. Not written if omitted. |
| `xray_manual_output_path` | none | Path to write covering Manual/Generic tests as a markdown table. Not written if omitted. |

When `xray_tests` is `true`, the skill discovers covering tests with exactly one JQL query, never
both and never merged:

- **Primary** — `issue in testRequirement("<STORY-KEY>") ORDER BY key ASC`, run whenever the Xray
  JQL functions are available on the instance.
- **Fallback** — `issuetype = Test AND issue in linkedIssues("<STORY-KEY>") ORDER BY key ASC`, run
  only when the Xray JQL functions are unavailable.

Which query ran is always reported back (`Xray query:` in the output template).

**Manual and Generic tests never appear in the Cucumber export.** Xray's `export/cucumber`
endpoint only returns Cucumber-format tests; Manual and Generic tests are fetched separately —
metadata through the Jira REST API, and **their steps through Xray's GraphQL API** — and written to
`xray_manual_output_path`. A caller that receives Cucumber tests (`xray_output_path` populated) but
no Manual tests is looking at **partial coverage**, not proof the story has no manual tests — the
skill reports explicitly when the non-Cucumber set could not be fetched, and this should never be
silently assumed.

**Since v0.4.0 the manual table carries verbatim test steps.** A Manual test's steps are its
content; key, summary, and labels are only metadata about it. Steps are recorded one row per raw
step object, in Xray's own Action / Data / Expected Result columns, in original order, with unedited
wording and no invented section headers — because a caller reads this table either to judge whether
coverage already exists or to convert the test into Gherkin, and both read an edit as the original.
When steps cannot be fetched the table is emitted without them and the report says so: a stepless
table and a test with genuinely no steps are different facts.

Missing `XRAY_CLIENT_ID` / `XRAY_CLIENT_SECRET` is a warning, not a stop: the skill reports `xray:
unavailable` and returns the brief as usual. This skill only reads Xray — it never imports a
feature file, creates a test execution, or uploads a result; that belongs to CI. See
[`references/XRAY_API.md`](references/XRAY_API.md) for the exact endpoints.

### Repository Detection

The skill automatically discovers your target repository using:
1. `git remote get-url origin` (primary source)
2. Folder name inference (fallback)

No additional configuration is needed; the repository is automatically matched to your Jira issue and feature spec folder.

---

## Execution Report and Progress Tracking

After each phase completes, the execution report is updated with:

| Phase | Progress | Issue | Copilot Requests | Input Tokens | Response Tokens | Cost Estimate |
|-------|----------|-------|------------------|--------------|-----------------|---------------|
| Intake | Complete | None | 1 | 2,400 | 1,200 | $0.07 |
| Specification | In Review | Ambiguity on scope | 5 | 8,900 | 4,500 | $0.28 |
| Planning | In Review | — | 8 | 14,200 | 7,100 | $0.42 |

The report includes:
- **Phase name** and current progress status
- **Issue or blocker** (if any)
- **Cumulative Copilot request count** since intake
- **Cumulative token counts** (input and response)
- **Cost estimate** based on token usage and current API pricing

The report is stored at `specs/{PREFIX}-{JIRA-KEY}-{slug}/execution-report.md` and is preserved for audit, billing, and workflow resumption.

---

## Naming Convention: Preserving Jira Context

All generated specs preserve the Jira key to maintain traceability:

**Spec Folder Naming:**
- `specs/US-{JIRA-KEY}-{kebab-summary}/` (for stories and features)
- `specs/Task-{JIRA-KEY}-{kebab-summary}/` (for tasks, bugs, spikes)

**Prefix Selection:**
- Story, User Story, Feature, Requirement → `US-`
- Task, Sub-task, Bug, Spike, Tech Task → `Task-`

**Examples:**
- `specs/US-DDM-1234-reduce-dar-review-time/`
- `specs/Task-DDM-4567-fix-sync-error-reporting/`
- `specs/US-DDM-9876-onboard-new-users/`

This naming ensures every generated spec, branch, and commit can be traced directly back to the Jira issue.

---

## Security and Guardrails

jira-to-speckit enforces strict security and usability guardrails:

- **No secret exposure**: Jira tokens and `.env` values are never printed to chat, logs, or git output
- **No credential requests**: The skill never asks you to paste secrets into chat; credentials are always read from `.env` only
- **Preserved business identity**: Exact Jira IDs, office codes, system names, acceptance criteria, and dependencies are always preserved in the compacted brief
- **No raw Jira payloads**: Raw Jira JSON, full comment threads, or ADF trees are never passed to Speckit; only compacted, business-focused briefs are used
- **Character budget enforcement**: Large tickets are always compacted to fit within budgets before advancing to Speckit
- **SSH-only git operations**: All git commands use SSH-authorized remotes; no hosting tokens are required
- **No direct default-branch pushes**: Commits are always made to a feature branch; PRs are created for review before merging

---

## Common Workflows and Examples

### Workflow 1: Simple Jira Issue to Spec

```bash
@jira-to-speckit DDM-1234
# Output: Compact brief, spec folder created, ready for clarification

# (After clarification loop confirms spec)
# Output: Spec folder updated, planning phase starts automatically
```

### Workflow 2: Large Jira Issue with Auto-Compaction

```bash
@jira-to-speckit https://jira.company.com/browse/DDM-4567
# Issue has 15,000-char description; skill compacts to 2,500 chars
# Output: Compact brief with truncation note, planning questions identified
```

### Workflow 3: Resuming a Paused Workflow

If the session grows too large (approx. 80,000 tokens), the skill pauses and asks you to run `/compact` to clear chat history. After compacting, the skill resumes from the latest confirmed phase without redoing completed work.

### Workflow 4: From Jira to PR

The full workflow from Jira to pull request:
1. Invoke with Jira key
2. Clarify spec (automatic review loop)
3. Confirm spec is ready
4. Plan phase (automatic review loop)
5. Confirm plan is clear
6. Test planning (automatic review loop)
7. Confirm test plan is complete
8. Task generation (automatic review loop)
9. Confirm task list is ready
10. Implementation (automatic commits and branch push)
11. Verification (GO/NO-GO report generated)
12. PR created; ready for review

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
- If needed, increase `JIRA_MAX_OUTPUT_CHARS` in `.env`, but this may increase context overflow risk

**Issue: "Repository not found"**
- Ensure you have git SSH access to the repository
- Verify `git remote get-url origin` returns a valid URL
- If working in a cloned subdirectory, move to the repository root before invoking the skill

**Issue: Spec folder created but empty**
- The folder is a placeholder created by `speckit.specify`; content is added during clarification
- Confirm the clarification loop is active and answer the first prompt

---

## Best Practices

1. **Keep Jira tickets well-formatted**: Clear acceptance criteria, no duplicate text, and focused scope lead to faster, smaller compacted briefs
2. **Use comments for decisions, not chatter**: Only decision-bearing comments are fetched; implementation discussion can stay in Slack
3. **Confirm before advancing**: The skill advances automatically when you confirm each phase; don't rush through review loops
4. **Monitor token usage**: Check the execution report between phases; if token count grows unexpectedly, pause and run `/compact`
5. **Use feature branch naming from Speckit**: The branch created during `speckit.specify` is reused throughout; do not create new branches manually
6. **Commit incrementally**: Smaller commits with clear messages are easier to review and debug
7. **Preserve spec folder structure**: Do not rename or move spec folders; they are referenced in the execution report and the PR

---

## Compatibility

- **Platforms**: macOS, Linux, Windows (with WSL or Git Bash)
- **Jira versions**: Jira Cloud and Server (7.0+) with REST API access
- **Git**: SSH-authorized remotes only (no HTTPS tokens)
- **Network**: Requires outbound access to Jira API endpoint and your git repository host
- **Agents**: GitHub Copilot, Claude Code, OpenCode, and compatible Copilot agents

### Installation Paths

- GitHub Copilot: `.github/skills/` or `~/.agents/skills/`
- Claude Code: `~/.claude/skills/`
- OpenCode: `~/.config/opencode/skills/` or `.opencode/skills/`
- Local: `~/.agents/skills/`

---

## References

- **Jira API Guide**: See [`references/JIRA_API.md`](references/JIRA_API.md) for detailed API usage
- **Xray API Guide**: See [`references/XRAY_API.md`](references/XRAY_API.md) for the optional
  Xray read mode (`xray_tests`)
- **Speckit Workflow**: The `speckit-auto` skill consumes this skill's brief and owns every
  stage that follows — spec, plan, tasks, implementation, review, and commit.

This skill is self-contained: it reads nothing outside its own folder except the project `.env`,
so it works when installed on its own.
