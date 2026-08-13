# Shared: Intake (Provider-Agnostic)

Applies identically to every provider. Loaded by Stage 01 of all providers.
Runs **after** the branch gate in [branching.md](branching.md) has completed.

## Intake Mode Selection

- If `issue_url` resolves (see below), run Jira intake via `jira-to-speckit`.
- Otherwise, use the user's requirement text directly as the Stage 02 input.

## Issue Argument Resolution (Critical)

Resolve `issue_url` using this precedence:

1. Explicit CLI flag in the current command: `--issue <url>`
2. Explicit CLI flag variant: `--issue=<url>`
3. Any Jira browse URL in the current user turn text (for example `https://.../browse/ABC-123`)
4. Existing in-run state value `issue_url` (captured earlier in this same run)
5. Existing in-run state value `original_user_command` (parse `--issue` from it if present)
6. Jira browse URL found in the loaded skill-context payload text (if present in this turn)

If `issue_url` resolves by any method, treat the run as `--issue` mode and execute Jira intake
immediately. Do not ask the user to re-invoke the skill with the same command.

Only if the user explicitly selected `--issue` mode but no URL can be resolved, ask once for the
missing Jira URL, then continue Stage 01 in the same run.

If neither issue URL nor manual requirement text can be resolved, ask once for the missing
requirement input, continue Stage 01 immediately after receiving it, and never return
"run this command in CLI" as a blocker.

## Ephemeral Run-State Bootstrap (When No Persisted Runner State Exists)

If `run_state`/stage file/channel binding is absent in this turn, initialize in memory:

```json
{
  "integration": "<github-speckit|superpowers>",
  "current_stage": "stage-01",
  "mode": "<default|yolo>",
  "branch_created": false,
  "branch_name": null,
  "issue_url": "<resolved-or-null>",
  "ticket_path": null,
  "requirement_text": "<resolved-or-null>"
}
```

Execute Stage 01 in this order (this is the true order regardless of file position):
**branch setup → framework source/availability check + install recovery → guidelines load → intake.**
`branch_created` must be `true` (real `branch_name` from an actual git command) before any
framework stage call, `jira-to-speckit` call, or intake step runs.

`integration` is resolved once by [../integration-mode.md](../integration-mode.md) and never
changes during the run.

## Jira Intake (`--issue`) via `jira-to-speckit`

Do not manually parse Jira when `jira-to-speckit` is available.

### Invocation

Invoke via the `skill` tool with name `jira-to-speckit`, passing the Jira URL as input **and** the
ticket snapshot staging path (see "Ticket Snapshot" below).

### Scope Constraint (Critical)

Override `jira-to-speckit` orchestration scope:

> Perform only Jira fetch + compaction (workflow steps 1–5), including the ticket snapshot write
> (step 2b) to the `ticket_output_path` given below.
> Return compact brief + Jira key + snapshot path.
> Do NOT run any downstream framework stages.
> `speckit-auto` owns all subsequent stages.

### Extract from Output

| Field | Source | Use |
|------|--------|-----|
| Jira issue key | `Jira issue key:` | Artifact id prefix (lowercase) |
| Compact brief | `Compact brief:` | Input for the provider's Stage 02 entry step |
| Open questions | `Open questions:` | Seed for the provider's clarification step |
| Ticket snapshot path | `Ticket snapshot:` | File to relocate into the artifact folder |
| Truncation note | `Truncation note:` | Context log |

### Continue Immediately After Jira Intake (No Turn-End Here)

A "next action"/"handing back" line in `jira-to-speckit`'s output is data, not a stop cue.
In the same turn: resolve/create the artifact path (provider-specific, see the provider's Stage 01),
relocate the ticket snapshot into it, then invoke the provider's Stage 02 entry step and continue
onward without waiting for another user message.

### Fallback if `jira-to-speckit` Unavailable

1. Log the fallback message.
2. Read root `.env`: `JIRA_URL`, `JIRA_USERNAME`, `JIRA_API_TOKEN`.
3. If any is missing, stop and request `.env` completion.
4. Fetch the issue:
   `GET {JIRA_URL}/rest/api/2/issue/{issueKey}?fields=summary,description,issuetype,status,priority,labels,assignee,fixVersions`
5. Handle errors:
   - `401/403`: invalid credentials/permission
   - `404`: confirm issue key
   - `5xx`: retry later
6. Write the ticket snapshot yourself, to the same staging path and in the same shape described in
   "Ticket Snapshot" below, straight from the fetched payload.
7. Compact into: summary, business goal, acceptance criteria, constraints. Keep the raw payload out
   of the ongoing run context once the snapshot is on disk.

## Ticket Snapshot (Required in `--issue` Mode)

Spec and plan are the source of truth for *what will be built*; the ticket is the source of truth
for *what was asked*. Persist it so a future reader can trace any spec decision back to the original
Jira content without Jira access.

1. **Staging write.** Pass `ticket_output_path = .speckit/intake/<issue_id>-ticket.md` to
   `jira-to-speckit`. The staging step exists because the snapshot must be captured while the full
   Jira payload is still in hand, which is before the artifact folder name is resolved (that name
   needs `short_title`, which the same call returns). `.speckit/` is the run's scratch root, and the
   relocation below is a **move**, so nothing is left there to be committed.
2. **Relocate.** Once the provider's artifact folder is resolved and created, **move** the file to
   `<artifact_folder>/ticket.md` and set `ticket_path` in run state. This copy **is** committed with
   the rest of the artifacts by Stage 04/05 (`git add -A`) — do not add it to `.gitignore` and do
   not commit it separately.
3. **Rerun.** If `<artifact_folder>/ticket.md` already exists, overwrite it with the fresh snapshot
   — the ticket may have been edited in Jira since the last run, and the newest fetch is the
   accurate record. Never create `ticket-2.md` or any parallel copy.
4. **Never load it back.** The snapshot is deliberately un-budgeted and can be large. After writing
   it, work from the compact brief only; never read `ticket.md` back into context unless a later
   stage genuinely needs a detail the brief dropped, and then read only the relevant section. Global
   rule 8 (heavy payload prevention) still applies.
5. Skip this section entirely for manual (non-`--issue`) runs — there is no ticket to snapshot.

## Artifact Identity (Provider-Independent Parts)

Regardless of provider, when in `--issue` mode:

- `issue_id` = Jira key, lowercased (example: `ddm-6157`)
- `short_title` = short slug derived from the Jira issue title

**Stability across reruns is mandatory and must be resolved, not assumed.** Before deriving a new
slug, search the provider's artifact location for an existing artifact whose name starts with
`<issue_id>-`:

1. If exactly one match exists, reuse its `short_title` verbatim — even if the Jira title has since
   changed. Never rename or create a parallel artifact.
2. If several match, use the most recently modified one and log the ambiguity.
3. Only if none matches, derive `short_title` from the current Jira title.

The same resolution applies to the branch name: once `issue_id`/`short_title` (or `<NNN>-<slug>` in
manual mode) are resolved here, this **is** the point the provisional branch created in
[branching.md](branching.md) gets renamed (`git branch -m`) to match exactly, so branch and
artifact folder stay aligned across reruns.

Each provider's Stage 01 defines how `issue_id` and `short_title` compose into its artifact path,
and that same path is where the ticket snapshot is relocated to.

## Intake Behavior

Stage 01 has **no interview gate**.

- `--issue` mode: the compact Jira brief is the Stage 02 input.
- manual mode: the user requirement text is the Stage 02 input.
- In both cases, continue immediately to the provider's Stage 02 entry step.

If requirement clarity is insufficient, clarification happens inside Stage 02, not here.
