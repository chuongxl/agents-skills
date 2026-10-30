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
Capture the canonical source checkout root as `source_repo_path` before changing cwd or
creating the linked worktree. On resume, retain/recover that original source identity from
run state/discovery, never replace it with the current linked worktree's root.

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

Immediately after this gate succeeds, before provider validation or intake, retain
`source_repo_path`, the absolute `event_helper_path` from the loaded skill folder, and `run_id`.
Generate an absent run ID once with `node -e 'console.log(require("node:crypto").randomUUID())'`;
retain the UUID output as data. Resolve the issue URL using §5's precedence without invoking
intake yet. Ticket identity must be the uppercase Jira key from the resolved
browse URL, known before init, not the lowercase artifact slug. If an explicit `--issue` lacks
a URL, ask once to resolve it before initialization, without calling intake/provider skills.
Pre-init input waits and failures have no event file and remain on the host/session-status path.
Do not initialize a ticket attempt as standalone and try to attach its key later.

Load [../shared/run-events.md](../shared/run-events.md) now and execute its exact `init`
invocation. It emits `run_started` and `stage_started` for `01-intake` once, validates resumes,
and writes discovery in the source repository. A fresh retry uses a new UUID; never truncate
history. On a mid-stage resume, revalidate with `init` before continuing, without replaying
already-recorded starts/answers. If initialization fails, stop explicitly.

After any later `git worktree move`, update `worktree_path` and repeat the same `init` invocation
with the original source repo, run ID, and issue key to refresh discovery. Do not rewrite events
or lose the absolute helper path. If a move is unsafe, keep the actual path in state/discovery.

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

Skipped silently when `docs/guidelines/architecture.md` is absent — continue with the fallback
`repo_map` chain below. Never let the fallback default to `{ ".": "root" }` when the repo itself
declares a multi-service layout elsewhere; that map is authoritative for every later
task/workspace assignment (step 5), so a wrong map here misassigns backend/frontend features to
the meta-repo root instead of their real submodule.

1. Detect layout: `monorepo` if `pnpm-workspace.yaml`, `package.json.workspaces`, or `lerna.json`
   exists; `git-submodules` if a root `.gitmodules` exists; else `single-repo`. A repo can be both
   `monorepo` and `git-submodules` — keep both signals, don't collapse to one.
2. Derive `repo_map`, in this order, stopping at the first that yields entries:
   1. `architecture.md`'s explicit Repository Map section, when the file exists.
   2. **No `architecture.md`, layout includes `git-submodules`:** parse `.gitmodules` for
      `path = <submodule-path>` entries and use each as a workspace. If the root `AGENTS.md` (or
      equivalent contributor doc) declares names for those paths (e.g. a services/apps table),
      use its names as the `repo_map` keys instead of raw paths — that file is the authoritative
      service layout when `architecture.md` is absent.
   3. `monorepo` glob-resolved workspace folders, inferred as backend / frontend / bff / database
      / shared from folder names.
   4. Only when none of the above produced any entries: `single-repo` →
      `{ ".": "root", "inferred": true }`.
3. Parse `architecture.md` **once**, when present, into an in-memory Project Context: `layout`,
   `workspaces`, `repo_map` (from step 2), `arch_pattern`, `dependency_rule` (one sentence),
   `bounded_context_layout` (compact), `linked_guidelines` (stem → repo-relative path for every
   relative `.md` link), `summary` (≤120 words), `loaded_guidelines` (cache, empty). When
   `architecture.md` is absent, populate the same Project Context shape with `repo_map` from step
   2 and the remaining fields empty/best-effort.
4. **Lazy-load linked guidelines**: never during parse. Load one only when a stage needs detail
   the cached fields lack, matched by stem (naming/style, database/data, workflow/process, or best
   match); cache it in `loaded_guidelines`; never load the same file twice.
5. Downstream usage is mandatory: `repo_map` drives every task/workspace assignment; generated
   structure follows `arch_pattern`; `summary` prefixes provider stage prompts, with the relevant
   `repo_map` slice and loaded guidelines appended.
6. Log one line: `[Preflight] Context loaded: layout=<...>, workspaces=<n>, arch=<...>,
   linked_guidelines=<...>`.

## 4. Scratch Hygiene

Stage 04 commits with `git add -A`, so before Stage 03 ensure `.superpowers/` (superpowers only)
is git-ignored if needed. The relocated `ticket.md` is **not** scratch — never gitignore it.
Ensure `.speckit/` is git-ignored in both source repo and worktree before initializing events.
Keep runtime `events.jsonl`, locks, and `.speckit/runs/` discovery out of commits. Mirror this
ignore rule during the worktree gate, not after the first write.

## 5. Intake

**Issue resolution**, in order: `--issue <url>` / `--issue=<url>` → any Jira browse URL in the
current turn text → an existing in-run `issue_url` → `--issue` from the original command → a
browse URL in the skill payload. Any hit → the run is `--issue` mode; go straight to Jira intake,
never ask the user to re-invoke. Missing required input (explicit `--issue` with no URL, or no
requirement text at all) → ask once, then continue Stage 01 in the same run.

**Run-state bootstrap** (in memory, if not already present): `{ integration, current_stage, mode,
branch_created, branch_name, source_repo_path, event_helper_path, run_id, issue_key, worktree_path,
issue_url, ticket_path, requirement_text }`.
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

Create the folder, run the branch rename, relocate the ticket snapshot (`--issue`), and finish
execution-report initialization below when applicable. Emit
`{type: "stage_finished", stage: "01-intake"}`, then load
[stage-02-spec-design.md](stage-02-spec-design.md) and invoke its first step
(`speckit-specify` / `brainstorming`) with the compact brief or requirement text, in the same turn.

## 7. Execution Report (`--issue` only)

Right after Jira intake, initialize `execution-report.md` in the artifact folder from
[../../assets/execution-report-template.md](../../assets/execution-report-template.md),
populating metadata (issue key, title, feature name, repository) from the intake output. Update it
in place after **every** stage. No token or cost estimates are tracked.

## Questions and terminal exits

For any initialized-run missing-input ask, emit `question_waiting` with `stage: "01-intake"`
immediately before asking; after the response emit `stage_started` for `01-intake` before
continuing. Use a composed prompt such as "Provide the requirement to implement", never the
answer. Apply the shared question rule to install recovery and Jira input questions too.
After initialization, unrecoverable provider recovery or a user choosing Stop emits `run_failed`
with `reason.code: "policy_blocked"`; terminal Jira/tool errors use `crashed`, permission/policy
denials use `policy_blocked`, and terminal git failures use `git_error`. Best-effort sync and
submodule warnings are not failures. Follow shared terminal ordering, including write errors.
