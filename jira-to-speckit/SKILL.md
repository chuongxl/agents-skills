---
name: jira-to-speckit
description: Fetch a Jira issue or Jira issue URL using credentials from `.env`, compact the ticket into a Speckit-ready feature brief, then support repository exploration, commits, pushes, and pull request preparation with plain `git` commands. Use when work starts from Jira and needs to become a spec under `specs/` and then a Git-backed change.
compatibility: Requires network access, Jira REST API access, and git access via SSH authorization. Requires `.env` entries for `JIRA_URL`, `JIRA_USERNAME`, and `JIRA_API_TOKEN`. Repository detection is automatic via `git remote` or folder name.
metadata:
  author: one-om-ddm
  version: "1.1"
---

# Jira to Speckit

Use this skill when a Jira ticket is the source of truth for a new feature, task, or change request and you need to turn it into a Speckit spec, then carry that work through git changes in the correct repository.

This skill acts as the **orchestrator** for the Speckit workflow:

1. Read Jira and compact it into a spec-ready brief.
2. Run `speckit.specify` with a Jira-key-based feature name.
3. Enter an interactive clarification loop with the user.
4. Summarize the final spec direction and ask for explicit confirmation.
5. On confirmation, automatically continue to `speckit.plan`.
6. Run a plan review loop and continue to `speckit.testplan` on confirmation.
7. Run a test-plan review loop and continue to `speckit.tasks` on confirmation.
8. Run a tasks review loop and continue to `speckit.implement`, then `speckit.verify` when requested.

The skill also maintains a running **execution report** across every phase and
updates it after each step until the workflow ends.

Execution report initialization:

- Create a report file from the template at `assets/execution-report-template.md`.
- Recommended output path: `specs/{US-or-Task}-{JIRA-KEY}-{slug}/execution-report.md`.
- Update that file in place after each phase and clarification step.

## What This Skill Does

- Reads Jira issue content from a Jira issue key or URL.
- Uses Jira credentials from the local repository `.env` file.
- Compacts the Jira ticket into a Speckit-friendly feature brief.
- Preserves the Jira key in the Speckit feature name and spec folder name.
- Starts the Speckit specification flow from the main repo root.
- Supports repository exploration, commits, pushes, and pull request creation.
- Orchestrates the spec review loop so the user can refine requirements before planning begins.
- Orchestrates the same review loop for planning and task generation so every phase is reviewed before advancing.
- Orchestrates a dedicated test-planning phase so unit and e2e coverage are explicit before tasks are generated.
- Produces and updates a running execution report with progress, issues, request counts, token usage, and estimated AI cost.
- Applies a size-aware Jira compaction pipeline to prevent context overflow on large issues.

## Required Inputs

- A Jira issue key such as `DDM-1234`, or a Jira browse URL.
- Access to the repository root `.env` file.
- Jira credentials in `.env`:
  - `JIRA_URL`
  - `JIRA_USERNAME`
  - `JIRA_API_TOKEN`

Repository detection is automatic:
- Uses `git remote get-url origin` as the canonical source for the target repository.
- If remote URL is unavailable, infers repo from folder name.

Optional `.env` tuning for large Jira tickets:
- `JIRA_MAX_INPUT_CHARS` (default `12000`)
- `JIRA_MAX_DESCRIPTION_CHARS` (default `6000`)
- `JIRA_MAX_OUTPUT_CHARS` (default `2500`)
- `JIRA_FETCH_COMMENTS` (default `false`)
- `JIRA_MAX_COMMENTS` (default `5`)

## Guardrails

- Do not ask the user to paste secrets into chat.
- If the Jira environment variables are missing, stop and instruct the user to add them to `.env` locally.
- Do not require repository hosting tokens for git operations.
- Do not move to `speckit.plan` until the Jira content has been compacted into a spec-ready brief.
- Keep the result business-focused; remove implementation noise, vendor chatter, and duplicate ticket text.
- Preserve exact Jira IDs, business terms, office codes, acceptance criteria, and dependencies.
- Never print tokens or `.env` values in logs or chat output.
- Never pass raw Jira payloads, full comment threads, or full ADF trees directly into Speckit commands.
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

### 2b. Resolve the repository

Resolve the target repository using `git remote get-url origin` as the primary source.
- If remote URL is unavailable, infer repository from the folder name.

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

The Jira key must stay in the name so the generated `specs/` folder is easy to trace back to Jira.

### 6. Start Speckit specification

Use the compacted Jira brief as the input to `speckit.specify`.

- Run the Speckit workflow from the main repo root.
- Pass the Jira-derived feature name so the generated spec folder uses the Jira-based structure.
- Keep the spec path under `specs/{US-or-Task}-{JIRA-KEY}-{slug}/`.
- After the spec is written, immediately enter the clarification/review loop.

### 6a. Run the spec review loop

Treat the spec as a living draft until the user confirms it is ready.

Loop behavior:

- Present a concise spec summary back to the user.
- Ask one clarification question at a time when ambiguity remains.
- Suggest the most likely question when the next decision point is obvious.
- Keep questions focused on scope, acceptance, terminology, ownership, and testability.
- Update the compacted brief mentally as answers arrive.
- Do not expose more than one future question at a time.
- Stop the loop early if the user says `done`, `good`, `no more`, or `proceed`.

Final review gate:

- After ambiguities are resolved, ask the user to confirm the spec is ready for planning.
- If the user confirms, proceed automatically to `speckit.plan`.
- If the user wants changes, ask the next clarification or revise the brief and re-check.
- If the user declines, pause and wait for further instruction.

Execution report updates:

- After each spec loop interaction, append the current progress, any issue or blocker, the number of Copilot requests made so far, and the best available input/output token estimate.
- If exact token counts are not available from the active tools, estimate them from the exchanged text and label the values as estimates.
- Keep the report current after each clarification round.

### 6c. Run the plan review loop

After `speckit.plan` completes:

- Present a concise plan summary back to the user.
- Ask clarification questions about technical choices, boundaries, dependencies, or missing constraints.
- Keep the scope limited to what affects the plan output.
- Update the plan mentally as answers arrive.
- When the plan is clear, ask the user to confirm it is ready for task generation.
- If the user confirms, automatically continue to `speckit.testplan`.
- If the user requests changes, revise the plan and re-check before advancing.

Execution report updates:

- After each plan loop interaction, update the report with the plan progress, any open issues, cumulative Copilot request count, token estimates, and updated cost estimate.
- Reflect whether the plan is ready for tasks, still needs clarification, or was revised.

### 6d. Run the test plan review loop

After `speckit.testplan` completes:

- Present a concise test plan summary back to the user.
- Ask clarification questions about acceptance criteria traceability, unit coverage, integration boundaries, or e2e journey coverage.
- Keep the scope limited to test completeness and service-specific validation strategy.
- When the test plan is clear, ask the user to confirm it is ready for task generation.
- If the user confirms, automatically continue to `speckit.tasks`.
- If the user requests changes, revise the test plan and re-check before advancing.

Execution report updates:

- After each test-plan loop interaction, update the report with test coverage status, any blockers, cumulative Copilot request count, token estimates, and updated cost estimate.
- Reflect whether the test plan is ready for tasks, still needs clarification, or was revised.

### 6e. Run the tasks review loop

After `speckit.tasks` completes:

- Present a concise task summary back to the user.
- Ask clarification questions about task sequencing, missing work items, parallelization, or validation steps.
- Keep questions grounded in execution order and deliverable completeness.
- When the task list is clear, ask the user to confirm it is ready for implementation.
- If the user confirms, automatically continue to `speckit.implement`.
- If the user requests changes, revise the tasks and re-check before advancing.

Execution report updates:

- After each tasks loop interaction, update the report with task progress, any sequencing or completeness issues, cumulative Copilot request count, token estimates, and updated cost estimate.
- Reflect whether the task list is ready for implementation, still needs clarification, or was revised.

### 6f. Verification handoff

After `speckit.implement` completes:

- Run `speckit.verify` to produce a GO/NO-GO readiness report.
- Include code evidence, unit evidence, e2e evidence, and service command evidence in the execution report.

### 6g. Discover the repo and prepare git work

If the task requires code changes after planning:

- inspect the repository contents before editing
- identify the service or submodule path from the feature scope
- fetch the latest remote state for the target branch
- use the existing feature branch created during `speckit.specify`
- commit incremental changes with a conventional commit message
- push the branch to the repository remote
- open a pull request against the default branch

Use plain `git` commands over SSH-authorized remotes for all git operations. Do not use `gh` CLI.

Execution report updates:

- After each repository preparation or implementation action, update the report with the branch status, commit/push/PR status, blockers, and final usage totals.
- Preserve cumulative request and token counters through the end of the session.

## Compact Output Template

When this skill finishes the Jira read step, produce a concise handoff in this shape:

- Jira issue key:
- Jira title:
- Jira type:
- Spec prefix:
- Suggested Speckit name:
- Compact brief:
- Open questions:
- Next action:
- Truncation note: (state what was truncated/sampled when budgets were applied)

When the spec review loop is active, also include:

- Current clarification status:
- User confirmation needed:
- Planned next Speckit command:

When the plan or tasks review loop is active, also include:

- Phase being reviewed:
- Current review status:
- User confirmation needed:
- Planned next Speckit command:

The skill must maintain a separate running execution report with these columns:

| Phase | Progress | Issue | Copilot Requests | Input Tokens | Response Tokens | Cost Estimate |
|-------|----------|-------|------------------|--------------|-----------------|---------------|

- Update the row after every completed step in the workflow.
- Use cumulative counts for Copilot requests, input tokens, and response tokens.
- Use an estimated dollar cost when exact billing is unavailable; note the estimate basis in the issue field if needed.
- Keep the report concise, but do not omit blockers or unresolved issues.
- Carry the report forward through spec, plan, tasks, and implementation.
- Use `assets/execution-report-template.md` as the canonical structure for report generation.

## Common Edge Cases

- **Jira URL instead of key**: extract the key and continue.
- **Missing env vars**: stop and ask the user to populate `.env` locally.
- **Large description**: summarize into the minimum set of spec-ready bullets.
- **Very large ticket or comment-heavy issue**: use stage-1 fields first, then fetch capped comments only if ambiguity remains.
- **Multiple acceptance criteria formats**: normalize them into plain, testable behavior statements.
- **Epic or parent issue**: use the nearest actionable child story or task as the source for the spec.
- **Epic with no child stories/tasks**: ask the user whether to spec the Epic directly or wait until child issues are created.

## Git Workflow

For complete git branching, commit, and PR discipline, see [WORKFLOW.md](../../WORKFLOW.md).

### Repository Discovery

- Use `git remote get-url origin` to determine the repository.
- If not available, infer repo from the folder name.

### Branching & Commits

- Reuse the existing feature branch created by `speckit.specify` (see [WORKFLOW.md](../../WORKFLOW.md)).
- Do not create a new branch in this skill.
- For commits, follow [WORKFLOW.md](../../WORKFLOW.md) discipline and [Conventional Commits](https://www.conventionalcommits.org/).

### Scope

- Make only the files required by the Jira scope.
- Prefer the smallest possible change set.
- Keep changes aligned with the spec folder name and Jira issue key.

### Safety Rules

- Never push directly to the default branch unless the repo policy explicitly allows it.
- Never create a PR against the wrong repository.
- Never expose Jira tokens or any credentials in the PR description, logs, or commit messages.
- For full push and PR rules, see [WORKFLOW.md](../../WORKFLOW.md).

## Orchestration Rules

- Treat `speckit.specify` as the entry point, not the finish line.
- Keep the user in the loop until the spec is clear enough for planning.
- Prefer small, targeted clarification questions over broad rewrites.
- For large Jira content, always run the staged compaction pipeline before calling `speckit.specify`.
- If the conversation exceeds approximately 80,000 tokens or you notice degraded recall of earlier decisions, pause and ask the user to run `/compact` before proceeding.
- After the user compacts the session, resume from the latest confirmed phase without redoing completed clarification work.
- Do not run `speckit.plan` until the user explicitly confirms readiness or no meaningful ambiguities remain.
- Do not run `speckit.tasks` until the user confirms the plan.
- Do not run implementation work until the user confirms the task list.
- Once confirmed, advance automatically to the next Speckit command without asking the user to restate the whole ticket.
- Preserve the Jira key and spec folder naming throughout the entire workflow.
- Update the execution report after every major step and after each accepted clarification answer.
- Include progress, issue status, Copilot request count, input token count, response token count, and cost estimation in the report.
- Keep the report current until the workflow ends.

## References

- [Jira API guide](references/JIRA_API.md)
- [Execution report template](assets/execution-report-template.md)
- [Main submodule workflow](../../../SUBMODULES.md)
- [Copilot instructions](../../../.github/copilot-instructions.md)
