# Stage 01: Intake

Loads: [run-state.md](../shared/run-state.md), [repo-profile.md](../shared/repo-profile.md),
[workspace-guard.md](../shared/workspace-guard.md),
[operating-rules.md](../shared/operating-rules.md), [discovery.md](../shared/discovery.md), and —
only when discovery reports no test framework — [bootstrap.md](../shared/bootstrap.md). Five leaves
always, a sixth conditionally, so the reader knows the cost before paying it (design spec §11.2
rule 1). The conditional load is the point: a repository that already has a test tree never pays
for the file that builds one. `run-state.md` is declared because this stage writes
the run-state yaml every later stage reads: written from memory instead of from the contract, the
field names drift, and a drifted field is one no reader finds. It links to no other file under
`references/pipeline/` — its successor is named, never linked: **enter Stage 02** at the end of
this stage, same turn.

No human gate. Takes a Jira issue key or browse URL and leaves behind an isolated worktree, two
integrity baselines, a discovered repo profile, and the artifact folder Stage 02 designs from.

## Why This Order Is Not The Obvious Order

The eight steps below run in exactly the order design spec §4 fixes, and that order looks wrong
until the reasons are stated:

- **Repo profile discovery runs first, before any worktree exists.** Step 4 (frontend source
  init) is conditioned on `frontend_source_root` — a field discovery produces. An earlier draft of
  this design had the two reversed, so frontend init depended on output from a step that had not
  run yet (design spec §4, "The order matters and was wrong in the first draft (D12)"). Discovery
  only reads, so running it against the source checkout before a worktree exists is safe — there
  is nothing yet for a read to disturb.
- **`workspace_baseline` is captured second, before the run touches anything.** Capturing it later
  would bake in changes the run itself caused between "the run started" and "the baseline was
  taken," which defeats the point of a baseline (design spec §4 step 2, §7.1).
- **`frontend_baseline` is captured immediately after frontend init, as a baseline separate from
  `workspace_baseline` — not folded into it.** Two reasons, both required (design spec §4 step 5;
  `workspace-guard.md`, "Why Two And Not One"): the frontend is initialized inside the *worktree*,
  not the source checkout, so the source-checkout baseline cannot cover it even in principle; and a
  parent repository's `git diff HEAD` sees a submodule only as a gitlink — a commit pointer — so
  file edits inside it are invisible to a parent-repo diff no matter when that diff runs.

## Execution Order

```
repo profile (read-only) → source baseline → worktree + branch gate → frontend init + FE baseline
→ Jira intake (fetch → slug → artifact folder → `ticket.md`) → discovery sweeps
→ bootstrap (only when no framework) → artifact folder init (`execution-report.md`) + resume check
→ Stage 02
```

### 1. Repo profile

Read-only, against the source checkout — no worktree exists yet. Run `repo-profile.md`'s discovery
order and resolve the fourteen fields it lists. This is the one point in the stage that may ask the
human a round of questions: only for a field no discovered source answers, and only once
(`repo-profile.md`, "Discovery Order"). The `answers` cache file is *written* later, from inside
the worktree, alongside step 6 — this step only resolves the fields, it does not persist them.

### 2. Capture `workspace_baseline`

Before the run touches anything. Follow `workspace-guard.md` exactly: `head_sha`,
`worktree_diff_sha256`, `index_diff_sha256`, and the `untracked` fingerprint list, all scoped to
the source checkout root. Content-addressed, not a `git status --porcelain` string — see
`workspace-guard.md`, "Why `git status --porcelain` Is Not Sufficient," for why a status letter
misses a path that was already dirty before the run and grows more dirty during it.

### 3. Worktree gate

- Base branch priority `develop → main → master`, local first, then remote-tracking. Sync
  best-effort; a fetch or pull failure is a warning, never a stop.
- Linked worktree at `<repo-root>/.worktrees/<branch>`, branch name used verbatim — a slashed
  branch such as `test/mom-1234-agreement-reset-button` therefore nests
  (`run-state.md` rule 1).
- Ensure `.worktrees/` is git-ignored.
- The final branch name — `<branch_prefix><jira-key>-<slug>` — is not yet knowable here: the
  Jira key is known from the invocation, but the slug comes from the Jira title, fetched at step 6.
  Create the worktree against a provisional branch now; once step 6 resolves the slug, rename in
  place with `git branch -m` (design spec §4 step 3).

### 4. Frontend source initialization (hard stop, not best-effort)

When `frontend_source_root` names a submodule, run `git submodule update --init -- <path>`
**inside the worktree**. Failure stops the run with the git error quoted — this is one of the
`operating-rules.md` turn-ending conditions ("Stage 01 frontend-source initialization failure").
Not a warning: the Stage 03 entry selector gate reads frontend source, and an empty submodule
directory makes that gate unsatisfiable before it can even start. It stops here rather than there
because a missing checkout is an intake problem with an intake fix, and discovering it two stages
later wastes an entire design.

Frontend source is treated as read-only past this point. No general multi-submodule handling
exists — the pipeline expects at most one submodule, the frontend (design spec D10).

### 5. Capture `frontend_baseline`

Immediately after step 4 succeeds. Same shape as `workspace_baseline`, scoped instead to
`<worktree>/<frontend_source_root>` (`workspace-guard.md`, "The Two Baseline Schemas"). This is
the separate baseline explained above — capture it now, not folded into step 2's baseline and not
deferred to later in the run.

### 6. Jira intake

Invoke `jira-to-speckit` by name through the `skill` tool, default mode. This is the call that
resolves the Jira title — which both step 3's branch rename and the artifact folder name need.

**Resolve `run.anchor_type` from what the key turned out to be** — `story`, `epic`, or `test` — and
record it. It is resolved from the fetched issue's type, never guessed from the key's shape, and it
is written once: step 7's first sweep walks different links for each, and the design stage reads it
to decide whether it is designing from acceptance criteria or converting existing tests.

An `epic` anchor names the epic in `run.jira_key` and the artifact folder, and produces one
`.feature` per child, each carrying its own child's `@REQ_` tag. A `test` anchor takes its `@REQ_`
target from the requirement the test links to.

`ticket_output_path` therefore cannot simply be handed `<artifact_dir>/ticket.md` and left at that:
`artifact_dir` is `<artifact_root>/<jira-key>-<slug>` and the slug comes from that same title, the
identical ordering problem step 3 hits with the branch name. Resolve it the way step 3 does, in
order rather than in one move:

1. Invoke the skill and read the issue.
2. Derive the slug from the returned title; record `run.slug` and `run.artifact_dir`.
3. Create the artifact folder at `run.artifact_dir`.
4. Put `ticket.md` inside it — passing the resolved `ticket_output_path = <artifact_dir>/ticket.md`
   where the skill can be given the path up front, or moving a provisionally written file into the
   folder where it cannot, exactly as step 3 renames a provisional branch with `git branch -m`.

Only after move 3 is `<artifact_dir>/…` a path anything may be written to — step 7's Xray outputs
included.

### 7. Discovery sweeps

Run `discovery.md` in full: the three sweeps, concurrently, each in its own subagent, each
returning a structured list and no judgement. This step generalizes what was once a bare Xray
read — the Xray export is one of the three sweeps, not the whole of what Stage 01 needs to look at.

**Sweep 2 produces the export files dedup reads.** Invoke `jira-to-speckit` with `xray_tests:
true`, `xray_output_path = <artifact_dir>/existing-tests.feature`, `xray_manual_output_path =
<artifact_dir>/existing-tests-manual.md`, and extend the query to cover every issue Sweep 1
returned, not the anchor alone. Record `xray.query` from whichever JQL ran (`testRequirement` or
`linkedIssues`), and `xray.cucumber_tests` / `xray.manual_tests` from the counts reported back.

Unavailable Xray credentials degrade to a warning, never a stop, and the reason is recorded in
`discovery.ran` per `discovery.md`, "When A Sweep Cannot Run". Stage 02 is the stage that then
records every behaviour `NEW` and marks dedup `not-run`; this stage only records that the fetch did
not happen.

**Sweep 3 resolves `discovery.framework`, and that field decides whether step 8 runs at all.**
`framework: none` means the repository has no Playwright-BDD test tree to generate into. That is
not a failure and not something to leave for later: it is the condition step 8 exists for.
Detecting it here — before a scenario has been designed, two stages before anything would try to
run `generate_cmd` — is why the sweep is in this stage rather than in the one that needs the
framework.

Sweep 3 also records `discovery.orphan_features[]`. Orphans are **reported and left untouched**,
per `discovery.md`, "Orphan `.feature` Files Are Reported, Never Adopted" — not copied into the
artifact root, not rewritten, not deleted.

### 8. Bootstrap — only when `discovery.framework: none`

Skip this step entirely when discovery found a framework. When it did not, load `bootstrap.md` and
follow it in full: one approval for the complete list of paths, nothing overwritten, and the Xray
import CI job written even when its secrets are unset.

Nothing earlier in this stage depended on a framework existing, which is why the step sits here
rather than ahead of the worktree or the baselines. The first thing that needs one is Stage 03's
`generate_cmd`.

On completion, `discovery.framework` becomes `playwright-bdd` and the `profile.*` path and command
fields name directories and scripts that now exist. A run that reaches Stage 02 with
`framework: none` still recorded has skipped an approval it should have asked for.

### 9. Resume

An existing `<jira-key>-*` artifact folder — matched with the jira-key **lowercase**, per the case
rule below — is reused, never duplicated under a new slug. `execution-report.md` inside that
folder names the stage to resume from, in `run.stage` / `run.resume_from`.

**A run that ended after design — `resume_from: 02.4` or `03` — is resumed after a delay, and the
delay is the point.** It stopped because the code had not landed, or because the team wanted the
design first and the automation later. Either way, time passed. Two things went stale in between,
and neither fixes itself:

- **The base branch moved.** Step 3's sync is best-effort at creation time, and this worktree was
  created weeks ago. Re-sync it against the base branch **now**, before design or automation reads
  anything — this is the one point in the run where rebasing costs nothing, because nothing has been
  produced yet. Left to Stage 04, the same divergence stops a fast-forward-only push after every
  scenario has already been automated, which is the most expensive place to discover it.
- **`run.code_state` may still be `pending`.** Re-resolve it on any `02.4` resume. It stays
  `pending` if the code still has not landed, and the run stops after design again — the resume was
  simply early. A `03` resume skips this: its code had already landed when the run stopped.

A folder step 6 just created has no `execution-report.md` yet. Write it here, with the run-state
yaml block `run-state.md` specifies, carrying every field listed under "What This Stage Produces"
below. Every later stage reads its state from that file and the artifact folder and never from this
stage's prose (`run-state.md` rule 2), so a missing `execution-report.md` leaves Stage 02 with
nothing at all to read.

## Case Rule

Stated once so it is never guessed (design spec §4, "Case, stated once"). The Jira key is
**uppercase** everywhere it names the issue: `run.jira_key`, and every Jira or Xray API call. It is
**lowercase in every path**: the artifact directory, the branch name, and the resume glob. Paths
and globs are case-sensitive on Linux CI even where a developer's macOS checkout forgives them, so
a run that creates `docs/qa/mom-1234-…` and later resumes by globbing `MOM-1234-*` finds nothing
and silently starts a second artifact folder.

## What This Stage Produces

Written into run state (`run-state.md` is the authority on shape; nothing here travels between
stages that is not a field in that contract):

- `run.jira_key`, `run.slug`, `run.artifact_dir`, `run.branch`, `run.worktree_path`
- `run.mode` (always `default`), `run.design_only` — `true | false` — and `run.full_suite` —
  `true | false`. All are parsed at entry dispatch and none reaches Stage 03 or Stage 04 unless
  this stage records them; an unrecorded `run.full_suite` is a `--full-suite` flag Stage 03 has no
  way to see and therefore ignores.
- `run.stage` — written on entering this stage, and by every stage on entering itself, so step 9's
  resume has a value to read. Only Stage 04 writes the terminal `completed`; a run state that never
  holds a non-terminal stage cannot be resumed from one.
- `profile.*` — every field step 1 resolved, recorded here rather than left in this stage's working
  memory. Stage 02 reads it and Stage 03 reads every field of it, and neither may read this file
  (`run-state.md` rule 2), so an unrecorded profile field is a field that does not exist downstream.
- `baselines.workspace_baseline`, `baselines.frontend_baseline`
- `xray.query`, `xray.cucumber_tests`, `xray.manual_tests`
- `discovery.*` — every field `discovery.md`'s "What Discovery Writes" names: `ran`, `framework`
  (updated by step 8 when it ran),
  `linked_issues[]`, `xray_tests[]`, `repo_tests[]`, `orphan_features[]`. A sweep result held only
  in a subagent's reply is a result no later stage can read (`run-state.md` rule 5)

And, on disk, the artifact folder holding `execution-report.md` — **created by this stage**, per
step 9, carrying the run-state yaml block above — plus `ticket.md`, `existing-tests.feature`, and
`existing-tests-manual.md`.

## Enter Stage 02

Once the artifact folder holds `ticket.md` and the (possibly empty) Xray exports, enter Stage 02 in
the same turn. There is no human gate in this stage.
