# Stage 01: Preflight + Intake (Provider-Agnostic)

Already in context: `SKILL.md`, [../shared/operating-rules.md](../shared/operating-rules.md), and
the resolved provider adapter. Load nothing else unless a step below says to.

Strict order:

```
worktree + branch gate → provider gate → guidelines context → scratch hygiene → intake →
artifact path + branch rename → ticket relocation (--issue) → execution report init (--issue) →
Stage 02 (same turn)
```

## 1. Worktree + Branch Gate (hard gate — runs first)

Completes before any other action in this stage or any provider call. Real git commands.

1. Base branch priority `develop → main → master` (local first, then remote-tracking). None
   exists → stop with a missing-base-branch error.
2. Sync base best-effort: `git fetch origin <base>` → `git checkout <base>` →
   `git pull origin <base>` (fast-forward). Failure → log a warning and continue with the local
   copy; never a stop.
3. Ensure `<repo-root>/.worktrees/` is git-ignored (append to `.gitignore`, creating it only if
   absent; part of the feature commit, no separate commit).
4. Create or reuse a linked worktree at `<repo-root>/.worktrees/<branch-name>`: reuse if the
   branch's worktree exists, else `git worktree add` creating the branch from the synced base. On
   reruns, resolve the existing artifact folder first (§5 Artifact identity) and use that name
   directly.

   **Mandatory — mirror run config into the worktree** on every entry to this stage (not only on
   creation), because a fresh worktree has none of the source checkout's untracked files:
   `mkdir -p <worktree>/.speckit && cp <repo-root>/.speckit/integration.json <worktree>/.speckit/`.
   Source file absent → skip the copy; the provider is already in run state.
5. Before intake the final branch name may be unknown — use a provisional branch (`<issue_id>` in
   `--issue` mode, a requirement slug otherwise; no timestamps). As soon as intake resolves the
   final `<issue_id>-<short_title>` / `<NNN>-<slug>` and it differs, run `git branch -m
   <final-name>` and, when safe, `git worktree move` to the canonical path. Local-only, safe
   before any push.
6. Confirm the branch is checked out in the worktree; set `branch_created: true`, `branch_name`,
   `worktree_path` in run state. Every later step runs **from this worktree**.

**Submodules** (only for repos that use them): a fresh worktree leaves submodule directories
empty, which breaks later stages. Right after step 4, if `.gitmodules` exists, run
`git -C <worktree> submodule update --init --recursive` (best-effort: failure → warn and defer to
the Stage 03 workspace pre-flight, never a stop). Then, lazily when a submodule path is about to
be modified: sync its base, branch inside it off that base, and commit submodule changes before
the parent pointer update.

## 2. Provider Gate

- **github-speckit** — before calling any other `speckit-*` skill, check
  `.specify/memory/constitution.md` in the **worktree**. It is **outdated** if it is missing,
  empty, under 100 words, or older than the newest commit on the base branch.
  - Missing/outdated → `skill speckit-constitution "constitution project to understand the
    project architecture"`, then verify the artifact exists and is non-empty.
  - Present and fresh → skip the call, read it into context, continue.
- **superpowers** — run the adapter's availability check, then invoke `using-superpowers` once
  (skip if superpowers' session hook already injected it).

Failure in either case (skill unresolvable, tool error, or artifact still missing) is a provider
validation failure → load the adapter's install-recovery file and follow it. Only if that flow
also fails do you stop, with its restart-session message.

## 3. Guidelines Context

Skipped silently when `docs/guidelines/architecture.md` is absent — continue with a fallback
`repo_map`.

1. Detect layout: `monorepo` if `pnpm-workspace.yaml`, `package.json.workspaces`, or `lerna.json`
   exists, else `single-repo`. Resolve workspace folders from globs.
2. Parse `architecture.md` **once** into an in-memory Project Context: `layout`, `workspaces`,
   `repo_map` (explicit Repository Map section, else inferred from workspace names: backend /
   frontend / bff / database / shared; single-repo → `{ ".": "root", "inferred": true }`),
   `arch_pattern`, `dependency_rule` (one sentence), `bounded_context_layout` (compact),
   `linked_guidelines` (stem → repo-relative path for every relative `.md` link), `summary`
   (≤120 words), `loaded_guidelines` (cache, empty).
3. **Lazy-load linked guidelines**: never during parse. Load one only when a stage needs detail
   the cached fields lack, matched by stem (naming/style, database/data, workflow/process, or best
   match); cache it in `loaded_guidelines`; never load the same file twice.
4. Downstream usage is mandatory: `repo_map` drives every task/workspace assignment; generated
   structure follows `arch_pattern`; `summary` prefixes provider stage prompts, with the relevant
   `repo_map` slice and loaded guidelines appended.
5. Log one line: `[Preflight] Context loaded: layout=<...>, workspaces=<n>, arch=<...>,
   linked_guidelines=<...>`.

## 4. Scratch Hygiene

Stage 04 commits with `git add -A`, so before Stage 03 ensure `.superpowers/` (superpowers only)
is git-ignored if needed. The relocated `ticket.md` is **not** scratch — never gitignore it.

## 5. Intake

**Issue resolution**, in order: `--issue <url>` / `--issue=<url>` → any Jira browse URL in the
current turn text → an existing in-run `issue_url` → `--issue` from the original command → a
browse URL in the skill payload. Any hit → the run is `--issue` mode; go straight to Jira intake,
never ask the user to re-invoke. Missing required input (explicit `--issue` with no URL, or no
requirement text at all) → ask once, then continue Stage 01 in the same run.

**Run-state bootstrap** (in memory, if not already present): `{ integration, current_stage, mode,
branch_created, branch_name, worktree_path, issue_url, ticket_path, requirement_text }`.
`branch_created` must be true before any provider call, `jira-to-speckit` call, or intake step.

**Jira intake** (`--issue`): invoke the `skill` tool with name `jira-to-speckit`, passing the URL
and `ticket_output_path = .speckit/intake/<issue_id>-ticket.md`. **Scope constraint:** instruct it
to perform only Jira fetch + compaction (its workflow steps 1–5, including the snapshot write) and
to return compact brief + Jira key + open questions + snapshot path — no downstream framework
stages; `speckit-auto` owns everything after intake. Extract exactly those four values and carry
only them forward. Continue in the same turn — a "next action" line in its output is data, not a
stop cue. If the skill is unavailable, load
[jira-fallback.md](jira-fallback.md) and follow it.

**Ticket snapshot rules:** spec/plan are the source of truth for *what gets built*; `ticket.md`
records *what was asked*. Relocate (move) it to `<artifact_folder>/ticket.md` once the artifact
path exists; overwrite on rerun (never `ticket-2.md`); commit it with the other artifacts; never
load it back wholesale — work from the compact brief and read a single section only if a later
stage genuinely needs a detail the brief dropped.

**Artifact identity:** `issue_id` = lowercase Jira key; `short_title` = slug from the Jira title
(manual mode: `<NNN>-<slug>`, next unused three-digit prefix under `specs/`). **Stability across
reruns:** before deriving a new slug, search for an existing artifact starting with `<issue_id>-`
— exactly one match → reuse its `short_title` verbatim (even if the Jira title changed); several →
use the most recent and log the ambiguity; none → derive fresh. This is where the provisional
branch gets renamed (§1.5).

## 6. Artifact Path + Stage 02 Entry

Same layout for both providers — the git branch name and the spec folder name are identical:
`specs/<issue_id>-<short_title>/` (`--issue`) or `specs/<nnn>-<slug>/` (manual). Contents:
ticket snapshot (`--issue`), spec/plan (both providers) plus tasks/checklist (github-speckit),
execution report (`--issue`). The adapter's Artifact Path Guard still applies.

Create the folder, run the branch rename, relocate the ticket snapshot (`--issue`), then load
[stage-02-spec-design.md](stage-02-spec-design.md) and invoke its first step
(`speckit-specify` / `brainstorming`) with the compact brief or requirement text — same turn.

## 7. Execution Report (`--issue` only)

Right after Jira intake, initialize `execution-report.md` in the artifact folder from
[../../assets/execution-report-template.md](../../assets/execution-report-template.md),
populating metadata (issue key, title, feature name, repository) from the intake output. Update it
in place after **every** stage. No token or cost estimates are tracked.
