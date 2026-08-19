# Stage 01: Preflight + Intake (Provider-Agnostic)

Load with: the resolved provider adapter ([../providers/](../providers/)),
[../shared/operating-rules.md](../shared/operating-rules.md),
[../shared/host-adaptation.md](../shared/host-adaptation.md). Provider-specific steps (probe
paths, constitution/bootstrap gates, artifact paths) come from the adapter.

Execution order — strict:

```
worktree + branch gate → mandatory provider gate (constitution OR using-superpowers bootstrap) →
guidelines context → scratch hygiene → intake → artifact path + branch rename →
ticket relocation (--issue) → execution report init (--issue) → Stage 02 entry (same turn)
```

## 1. Worktree + Branch Gate (hard gate — runs first)

Must complete before any other action in this stage or any provider call. Real git commands.

1. Base branch priority `develop → main → master` (local first, then remote-tracking). None
   exists → stop with a missing-base-branch error.
2. Sync base best-effort: `git fetch origin <base>` → `git checkout <base>` →
   `git pull origin <base>` (fast-forward). Fetch/pull failure → log warning, continue with the
   local copy — never a stop.
3. Ensure `<repo-root>/.worktrees/` is git-ignored (append to `.gitignore`, creating it only if
   absent; part of the feature commit, no separate commit).
4. Create or reuse a linked worktree at the canonical path `<repo-root>/.worktrees/<branch-name>`:
   reuse if the branch's worktree exists; `git worktree add` (creating the branch from the synced
   base) if not. Reruns: if an artifact folder from a prior run exists, resolve it first (see
   Intake → Artifact Identity) and use that final name directly.
   **Mandatory — mirror run config into the worktree.** A fresh worktree never contains uncommitted
   or untracked files from the source checkout, so `<repo-root>/.speckit/integration.json` must be
   copied explicitly right after the worktree exists (reuse or new):
   `mkdir -p <worktree>/.speckit && cp <repo-root>/.speckit/integration.json <worktree>/.speckit/integration.json`.
   Run this on every entry to this stage (not only on first creation). If the source file is
   absent, skip the copy — provider resolution already ran from the source checkout and the value
   is in run state.
5. Before intake the final branch name may be unknown — use a provisional branch (`<issue_id>`
   in `--issue` mode, a requirement slug in manual mode; no timestamps). **Rename step:** as soon
   as intake resolves the final `<issue_id>-<short_title>` / `<NNN>-<slug>` and the current name
   differs, run `git branch -m <final-name>` and, when safe, `git worktree move` to the canonical
   path. Local-only, safe before any push.
6. Confirm the branch is checked out in the worktree; set `branch_created: true`, `branch_name`,
   `worktree_path` in run state. Every subsequent step executes **from this worktree**.

**Submodules (condensed):** only for repos that use them, lazily when a submodule path is about to
be modified: sync its base (same priority/best-effort rules), branch inside it off the synced
base, and commit submodule changes before the parent pointer update. If none exist or none are
modified, behavior is unchanged.

## 2. Mandatory Provider Gate

- **github-speckit (all hosts):**

  Before calling any other `speckit-*` skill, check whether the constitution artifact is present
  and up-to-date in the **worktree**:

  1. **Locate the artifact.** Look for a non-empty `.specify/memory/constitution.md` (written by
     `speckit-constitution`, github-speckit only) inside the worktree.
  2. **Freshness check.** The artifact is considered **outdated** if any of the following are true:
     - The file does not exist or is empty.
     - Its last-modified timestamp is older than the most recent commit on the current base branch
       (i.e., there were new commits since the file was last written).
     - The file's word count is under 100 words (truncated / partial run artifact).
  3. **Decision:**
     - **Missing or outdated** → invoke `skill speckit-constitution` with prompt
       `"constitution project to understand the project architecture"`. The `skill` tool returns
       inline — no turn boundary, no user ask needed. Validate the return value and verify the
       artifact now exists and is non-empty.
     - **Present and fresh** → skip the invocation; read the existing artifact into context and
       continue to section 3 in the same turn.
  4. **Failure handling.** If the skill invocation fails (skill not found, tool error, or artifact
     still absent/empty after the call) → **stop immediately** and tell the user:
     > "Provider skills are not installed. Please run `/speckit-auto --integration github-speckit`
     > first to set up the integration, then re-run your command."

- **superpowers:** invoke `using-superpowers` once per run (skip if already injected by
  superpowers' session hook). If the invocation fails → **stop immediately** and tell the user:
  > "Provider skills are not installed. Please run `/speckit-auto --integration superpowers`
  > first to set up the integration, then re-run your command."

## 3. Guidelines Context (docs/guidelines/architecture.md)

Skipped silently when `docs/guidelines/architecture.md` is absent — the pipeline continues with a
fallback `repo_map`.

1. Detect layout: `monorepo` if `pnpm-workspace.yaml`, `package.json.workspaces`, or `lerna.json`
   exists, else `single-repo`. Resolve workspace folders from globs.
2. Parse `architecture.md` once into an in-memory **Project Context**:
   `layout`, `workspaces`, `repo_map` (explicit Repository Map section, else inferred from
   workspace names: backend / frontend / bff / database / shared; single-repo → `{ ".": "root",
   "inferred": true }`), `arch_pattern`, `dependency_rule` (one sentence),
   `bounded_context_layout` (compact), `linked_guidelines` (stem → repo-relative path for every
   relative `.md` link found), `summary` (≤120 words), `loaded_guidelines` (cache, empty).
3. **Lazy-load linked guidelines**: never load them during parse; load only when a stage needs
   detail the cached fields lack, matched by stem (naming/style, database/data, workflow/process,
   or best match); cache in `loaded_guidelines`; never load the same file twice.
4. Mandatory downstream usage: `repo_map` drives every task/workspace assignment; generated
   structure follows `arch_pattern`; the Project Context `summary` prefixes provider stage prompts
   and relevant `repo_map`/loaded guidelines are appended (prompt-injection pattern in Stage 02/03).
5. Log one line: `[Preflight] Context loaded: layout=<...>, workspaces=<n>, arch=<...>, linked_guidelines=<...>`.

## 4. Scratch Hygiene

Stage 04 commits with `git add -A`, so before Stage 03 ensure `.superpowers/` (superpowers only)
is git-ignored if needed. The relocated `ticket.md` is **not** scratch — never gitignore it.

## 5. Intake

### Issue resolution

`--issue <url>` / `--issue=<url>` → any Jira browse URL in the current turn text → existing
in-run `issue_url` → `--issue` parsed from the original command → a browse URL in the skill
payload. If a URL resolves by any method, the run is `--issue` mode — go straight to Jira intake,
never ask the user to re-invoke. Missing required input (explicit `--issue` with no URL, or no
requirement text at all): ask once, continue Stage 01 in the same run after receiving it.

### Run-state bootstrap

If no persisted run state exists, initialize in memory: `{ integration, current_stage,
mode (default|yolo), branch_created, branch_name, worktree_path, issue_url, ticket_path,
requirement_text }`. `branch_created` must be true before any provider call, `jira-to-speckit`
call, or intake step.

### Jira intake via `jira-to-speckit` (`--issue`)

Invoke the `skill` tool with name `jira-to-speckit`, passing the URL and the ticket staging path.
**Scope constraint:** instruct it to perform only Jira fetch + compaction (workflow steps 1–5,
including the ticket snapshot write to `ticket_output_path = .speckit/intake/<issue_id>-ticket.md`)
and to return compact brief + Jira key + open questions + snapshot path — no downstream framework
stages; `speckit-auto` owns everything after intake. Extract: Jira issue key (artifact id prefix,
lowercase), compact brief (Stage 02 input), open questions (clarification seeds), snapshot path.

If `jira-to-speckit` fails (skill not found, tool error) → **stop immediately** and tell the user:
> "The `jira-to-speckit` skill is not available. Please ensure it is installed, then re-run."

Continue immediately in the same turn — a "next action" line in its output is data, not a stop cue.

**Fallback** if `jira-to-speckit` is unavailable: read root `.env` (`JIRA_URL`, `JIRA_USERNAME`,
`JIRA_API_TOKEN`; stop and request completion if any is missing — without printing them), fetch
`GET {JIRA_URL}/rest/api/2/issue/{issueKey}?fields=summary,description,issuetype,status,priority,labels,assignee,fixVersions`,
handle errors (401/403 auth, 404 confirm key, 5xx retry later), write the snapshot yourself in
the same shape, compact into summary/goal/acceptance/constraints, keep the raw payload off the
live context.

### Ticket snapshot rules

Spec/plan are the source of truth for *what gets built*; `ticket.md` records *what was asked*.
Stage → relocate (move) to `<artifact_folder>/ticket.md` once the artifact path exists; overwrite
on rerun (never `ticket-2.md`); committed with the other artifacts (never separately, never
gitignored); never loaded back wholesale — work from the compact brief; read a section only if a
later stage genuinely needs a detail the brief dropped.

### Artifact identity

`issue_id` = lowercase Jira key; `short_title` = slug from the Jira title (manual mode:
`<NNN>-<slug>`, next unused three-digit prefix under `specs/`). **Stability across reruns:**
before deriving a new slug, search for an existing artifact starting with `<issue_id>-`; exactly
one match → reuse its `short_title` verbatim (even if the Jira title changed); several → use the
most recent and log the ambiguity; none → derive fresh. This is also the point the provisional
branch gets renamed to the final name (Section 1).

## 6. Artifact Path + Stage 02 Entry

- **github-speckit:** `specs/<issue_id>-<short_title>/` (`--issue`) or `specs/<nnn>-<slug>/`
  (manual). Artifacts: ticket snapshot, spec/plan/tasks/checklist (written by `speckit.*` agents),
  execution report (`--issue`).
- **superpowers:** `specs/<feature_folder>/` with `spec.md` (brainstorming) and `plan.md`
  (writing-plans). Artifact Path Guard applies (adapter).

Create the folder, run the branch rename, relocate the ticket snapshot (`--issue`), then invoke
the Stage 02 entry step with the compact brief (or requirement text) — `speckit.specify` for
github-speckit, `brainstorming` for superpowers — in the same turn.

## 7. Execution Report (`--issue` only — skipped for manual runs)

Initialize `execution-report.md` in the artifact folder from
[../../assets/execution-report-template.md](../../assets/execution-report-template.md) right after
Jira intake, populating metadata (issue key, title, feature name, repository) from the intake
output. Update it in place after **every** stage of the run (progress, current blocker). No token
or cost estimates are tracked.