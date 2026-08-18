# Stage 01: Preflight + Intake (Provider-Agnostic)

Load with: the resolved provider adapter ([../providers/](../providers/)),
[../shared/operating-rules.md](../shared/operating-rules.md),
[../shared/host-adaptation.md](../shared/host-adaptation.md). Provider-specific steps (probe
paths, install commands, constitution/bootstrap gates, artifact paths) come from the adapter.

Execution order — strict:

```
worktree + branch gate → framework source check → install recovery if missing →
mandatory provider gate (constitution OR using-superpowers bootstrap) → guidelines context →
scratch hygiene → intake → artifact path + branch rename → ticket relocation (--issue) →
execution report init (--issue) → Stage 02 entry (same turn)
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
5. Before intake the final branch name may be unknown — use a provisional branch (`<issue_id>`
   in `--issue` mode, a requirement slug in manual mode; no timestamps). **Rename step:** as soon
   as intake resolves the final `<issue_id>-<short_title>` / `<NNN>-<slug>` and the current name
   differs, run `git branch -m <final-name>` and, when safe, `git worktree move` to the canonical
   path. Local-only, safe before any push.
6. Confirm the branch is checked out in the worktree; set `branch_created: true`, `branch_name`,
   `worktree_path` in run state. Every subsequent step executes **from this worktree**. Mirror
   `.speckit/integration.json` from the source checkout into the worktree if present.

**Submodules (condensed):** only for repos that use them, lazily when a submodule path is about to
be modified: sync its base (same priority/best-effort rules), branch inside it off the synced
base, and commit submodule changes before the parent pointer update. If none exist or none are
modified, behavior is unchanged.

## 2. Framework Source Check + Install Recovery (Startup Gate, required every run)

This is the startup recovery gate from entry dispatch. It must execute on every pipeline
invocation before any provider stage call. The same validation + recovery logic is reused later
before provider invocations in Stage 02/03/04.

**Detect.** Probe the provider's installed layout for the resolved host per the adapter
(github-speckit: probe the repo for `constitution`, `specify`, `clarify`, `plan`, `checklist`,
`tasks`, `analyze`, `implement`, `converge` under the host's layout dirs; superpowers: check the
session skill list, then the host on-disk skill dirs, then probe `using-superpowers`). Record the resolved layout + invocation channel in run state. A **complete** set → continue to
section 3 (no install step). Do not defer this check.

**No complete set → RUN install recovery now, do not skip and do not abandon the run:**

1. **Load the adapter's Install Recovery section** — open
   [../providers/github-speckit.md](../providers/github-speckit.md) or
   [../providers/superpowers.md](../providers/superpowers.md) for the RESOLVED provider as given
   by integration.json — the exact install commands for this host are there.
2. **Ask the user once** via the host ask tool: `Install <framework>` / `Stop`
   (e.g. `Install GitHub Speckit` / `Install superpowers`). `Stop` → halt and report that
   installation is required (a valid turn end, operating rules premise).
3. **Install** — run the adapter's exact commands for the resolved host: github-speckit → CLI
   install + `specify version` sanity + `specify init . --integration <host-key>` (mandatory
   success gate) + `speckit.constitution` through the host channel; superpowers → the host's
   plugin/clone+copy command + on-disk verification.
4. **Validate + re-check (hard gate)** — run the adapter's post-install validation gates and
   re-run the probe from step "Detect". On pass, continue to section 3 in the same turn.
5. **If validation fails after install** — stop immediately; do not continue provider stages.
   Ask the user to manually install/fix the provider or restart the host session (Copilot /
   Claude Code / OpenCode), then re-run `speckit-auto`.

Never switch provider because a framework is missing; never fall back to a global/external
variant; never continue past a concrete install failure (stop and report the exact error quoted).

## 3. Mandatory Provider Gate

- **github-speckit:** invoke `speckit.constitution` through the host channel (repo slash-agent on
  Copilot/Claude Code — never the `skill` tool on Copilot for this step; `skill` tool on OpenCode)
  and require success before Stage 02. Failure → stop with the exact error.
- **superpowers:** invoke `using-superpowers` once per run (skip if already injected by
  superpowers' session hook). It proves runtime executability.

## 4. Guidelines Context (docs/guidelines/architecture.md)

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

## 5. Scratch Hygiene

Stage 04 commits with `git add -A`, so before Stage 03 ensure `.speckit/` (both providers) and
`.superpowers/` (superpowers only) are git-ignored (append to `.gitignore` if missing; part of the
feature commit). The relocated `ticket.md` is **not** scratch — never gitignore it.

## 6. Intake

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

## 7. Artifact Path + Stage 02 Entry

- **github-speckit:** `specs/<issue_id>-<short_title>/` (`--issue`) or `specs/<nnn>-<slug>/`
  (manual). Artifacts: ticket snapshot, spec/plan/tasks/checklist (written by `speckit.*` agents),
  execution report (`--issue`).
- **superpowers:** `specs/<feature_folder>/` with `spec.md` (brainstorming) and `plan.md`
  (writing-plans). Artifact Path Guard applies (adapter).

Create the folder, run the branch rename, relocate the ticket snapshot (`--issue`), then invoke
the Stage 02 entry step with the compact brief (or requirement text) — `speckit.specify` for
github-speckit, `brainstorming` for superpowers — in the same turn.

## 8. Execution Report (`--issue` only — skipped for manual runs)

Initialize `execution-report.md` in the artifact folder from
[../../assets/execution-report-template.md](../../assets/execution-report-template.md) right after
Jira intake, populating metadata (issue key, title, feature name, repository) from the intake
output. Update it in place after **every** stage of the run (progress, current blocker). No token
or cost estimates are tracked.