# Stage 01 (superpowers): Preflight + Intake

Provider: **superpowers** — the `obra/superpowers` skills library.

Load with this file:
- [provider-rules.md](provider-rules.md) — skill names, invocation precedence, provider rules
- [../shared/branching.md](../shared/branching.md) — branch gate (runs first)
- [../shared/intake.md](../shared/intake.md) — issue resolution, run state, Jira intake
- [../shared/preflight-guidelines-context.md](../shared/preflight-guidelines-context.md) — project context

Execution order for this stage:
**branch setup (shared) → superpowers availability check → install recovery if missing →
bootstrap → guidelines load → intake (shared) → artifact paths → Stage 02.**

Only the superpowers-specific steps are described below; everything else lives in the shared files.

## Preflight Superpowers Availability Check (Required)

Verify the superpowers skills are invocable. Check in this order and stop at the first success:

1. Superpowers skills appear in this session's available-skills list (names may be surfaced as
   `superpowers:<name>` or bare `<name>`) — record which form is used and reuse it all run.
2. The skills exist on disk. Superpowers is distributed several ways, and a repository may vendor
   its own copy, so probe **all** of these before concluding it is missing (`<name>` = any skill
   from the minimum set below):

   | Install shape | Skills path |
   |---|---|
   | Repo-vendored (project-local) | `<repo-root>/.agents/skills/<name>/SKILL.md`, `<repo-root>/.claude/skills/<name>/SKILL.md` |
   | User-level skills dir | `~/.agents/skills/<name>/SKILL.md`, `~/.claude/skills/<name>/SKILL.md` |
   | Claude Code plugin | `~/.claude/plugins/cache/<marketplace>/superpowers/<version>/skills/<name>/SKILL.md` |
   | Copilot CLI plugin | `~/.copilot/installed-plugins/<marketplace>/superpowers/skills/<name>/SKILL.md` |

   `<marketplace>` is typically `superpowers-marketplace` (obra's) or `claude-plugins-official`;
   glob it rather than hardcoding. `<version>` is a version directory — take the highest.
   For a plugin install, also confirm it is enabled where the harness records that
   (Copilot CLI: `~/.copilot/settings.json` → `enabledPlugins["superpowers@superpowers-marketplace"]`).
   Record the resolved directory once and reuse it for the file-read fallback all run.
3. Direct probe: invoke `using-superpowers` via the `skill` tool. If it returns content,
   superpowers is available and the bootstrap step below is already satisfied.

A repo-vendored copy may be renamed (its own namespace and its own bootstrap skill name instead of
`using-superpowers`). If the minimum set below resolves under different names, use those names for
the whole run — a rename is not a missing install.

If the skills exist on disk (check 2) but the skill tool cannot resolve them, that is **not** a
failure — use the file-read fallback from [provider-rules.md](provider-rules.md) and continue.

At minimum these skills must be resolvable: `using-superpowers`, `brainstorming`, `writing-plans`,
`subagent-driven-development` **or** `executing-plans`, `test-driven-development`,
`requesting-code-review`, `verification-before-completion`.

If none of the three checks succeed, run install recovery below.

## Missing Superpowers Recovery (Required)

When superpowers is not available:

1. Fetch the install guide: `https://github.com/obra/superpowers`.
2. Ask the user once: `Install superpowers` or `Stop`.
3. If `Stop`, halt and report that installation is required.
4. If `Install`, use the installation method for the **current harness** — never run another
   harness's command:

   | Harness | How to install |
   |---|---|
   | GitHub Copilot CLI | Run both, in order: `copilot plugin marketplace add obra/superpowers-marketplace`, then `copilot plugin install superpowers@superpowers-marketplace` |
   | Claude Code | Plugin install is an interactive slash command the agent cannot run itself. Ask the user to run `/plugin marketplace add obra/superpowers-marketplace` then `/plugin install superpowers@superpowers-marketplace` (superpowers is also in the official marketplace), and continue in the same turn once they confirm. |
   | Other / unknown | Clone the repo and copy `skills/*` into the harness's skills directory (`~/.agents/skills/` or `~/.claude/skills/`), then re-check. |

   Detect the harness from what is present: a `~/.copilot/` tree and a working `copilot` binary →
   Copilot CLI; a `~/.claude/` tree → Claude Code. If both exist, prefer the one whose skills
   directory the session's other skills resolve from.
5. Confirm the install landed by re-running availability check 2 against the paths above.
6. Re-run the availability check. Newly installed skills may not be surfaced in the current
   session's skill list — if so, use the file-read fallback for this run rather than stopping.
7. If it passes, continue the pipeline in the same turn.
8. Only if install fails, stop and report the exact failing step with quoted error output.

Never fall back to the `github-speckit` provider because superpowers is missing — the provider is
fixed for the run (see [../integration-mode.md](../integration-mode.md)).

## Bootstrap (Required, After Availability Check)

Invoke `using-superpowers` once per run. This is the superpowers skill-discipline bootstrap and
also proves runtime executability. Only a concrete error from this call is reportable as a runtime
failure (quote it), and only after the availability check passed.

Note: on Copilot CLI, superpowers also injects this bootstrap through its session-start hook. If it
is already present in the session context, that satisfies this step — do not re-invoke it.

Do not let the bootstrap's "check for a relevant skill before every action" instruction override
this pipeline's stage order or its no-stop rules — `speckit-auto` owns the control flow.

## Scratch Path Hygiene (Required, Before Any Implementation)

Stage 04/05 commit with `git add -A`, so any scratch directory left untracked ends up inside the
feature commit. Two are produced during a run:

| Path | Written by | Contents |
|---|---|---|
| `.speckit/` | `speckit-code-review`, Stage 01 intake | per-category detail files, `state.json`, review dirs, the staged ticket snapshot |
| `.superpowers/` | `subagent-driven-development` | the plan's ledger, briefs, review packages |

Before Stage 03, ensure both are ignored in the repo whose tree will be committed:

1. Read `.gitignore` at the repo root.
2. Append any of the two entries that is missing (`.speckit/`, `.superpowers/`), each on its own
   line under a short comment.
3. If `.gitignore` does not exist, create it with just those two entries.
4. This edit is part of the feature commit — do not commit it separately.

`.superpowers/` may already be excluded by the implementation skill through
`.git/info/exclude`; adding it to `.gitignore` anyway is harmless and survives a fresh clone.
Note that `integration-mode.md` only writes a `.gitignore` entry during a **setup** invocation
(`--integration`), which a normal pipeline run never performs — this step is what covers that case.

## Preflight Guidelines Context Load (Required)

Load [../shared/preflight-guidelines-context.md](../shared/preflight-guidelines-context.md).
If `docs/guidelines/` or `architecture.md` is missing, skip and continue — never a stop.

## Worktrees Are Skipped (Critical)

`using-git-worktrees` is **not** invoked — the branch from
[../shared/branching.md](../shared/branching.md) is the working branch for the whole run. See
global rule 3 and [provider-rules.md](provider-rules.md) rule 3.

## Artifact Paths (`specs/` Layout — Same Place as Spec Kit Output)

Superpowers artifacts live under `specs/`, one folder per feature, so SpecKit Companion renders
them and `speckit-auto` finds them in the same place as `github-speckit` output.

Resolve `<feature_folder>` using `issue_id` and `short_title` from
[../shared/intake.md](../shared/intake.md):

| Mode | `<feature_folder>` |
|------|--------------------|
| `--issue` | `<issue_id>-<short_title>` (example: `specs/ddm-6157-user-login/`) |
| manual | `<NNN>-<slug>` — `<NNN>` = next unused three-digit prefix under `specs/` (`001`, `002`, …), `<slug>` = feature name in kebab-case |

| Artifact | Path | Superpowers default it replaces |
|----------|------|---------------------------------|
| Ticket snapshot (`--issue` only) | `specs/<feature_folder>/ticket.md` | — (new; written by `jira-to-speckit`, relocated here) |
| Design spec (`brainstorming`) | `specs/<feature_folder>/spec.md` | `docs/superpowers/specs/<date>-<topic>-design.md` |
| Implementation plan (`writing-plans`) | `specs/<feature_folder>/plan.md` | `docs/superpowers/plans/<date>-<feature>.md` |

Both skills write into the **same** folder for a given feature — `brainstorming` creates it,
`writing-plans` adds to it. The folder must stay stable across reruns of the same issue.

**Neither skill takes a path parameter.** Each hardcodes its output location in its own SKILL.md,
so passing the pipeline path is an instruction they may or may not honor. Pass it anyway as an
explicit instruction, then **verify and relocate** after each call — see the Artifact Path Guard in
[stage-02-spec-design-flow.md](stage-02-spec-design-flow.md). Never treat the instruction as
sufficient, and never let a downstream stage consume a path that was not checked on disk.

Keep the plan's task checkboxes (`- [ ]`) exactly as `writing-plans` specifies:
`subagent-driven-development` and the Companion viewer both read them for progress.

This path override is the only deviation from the superpowers skills — everything else in them
applies unchanged.

Create `specs/<feature_folder>/` if missing.

## Ticket Snapshot Relocation (Required, `--issue` Mode)

Right after the feature folder is created, **move** the staged snapshot
`.speckit/intake/<issue_id>-ticket.md` → `specs/<feature_folder>/ticket.md` and record
`ticket_path` in run state. Overwrite an existing `ticket.md` on a rerun. Full rules:
[../shared/intake.md](../shared/intake.md) → "Ticket Snapshot".

`ticket.md` is the traceback record of the original request; `spec.md`/`plan.md` remain the source
of truth for what gets built. It is committed alongside them by Stage 04/05 (`git add -A`) — do not
add it to `.gitignore` and do not commit it separately. Pass only the compact brief into
`brainstorming`, never the snapshot's contents.

## Stage 02 Entry Step

After intake completes, invoke `brainstorming` with the compact brief (or requirement
text) and the target design-spec path in the same turn, then continue to
[stage-02-spec-design-flow.md](stage-02-spec-design-flow.md).

## Execution Report (Jira-Sourced Runs)

`jira-to-speckit` only fetches and compacts the Jira issue (workflow steps 1–5) — it does not run
or track any downstream stage. `speckit-auto` owns the running execution report for the whole
pipeline whenever the run started from `--issue` mode.

- Initialize once, right after Jira intake returns, from
  [../../assets/execution-report-template.md](../../assets/execution-report-template.md).
- Recommended path: `specs/<feature_folder>/execution-report.md` (same folder as `spec.md`/
  `plan.md` above).
- Populate metadata from the `jira-to-speckit` output: Jira issue key, Jira title, resolved
  feature name, repository.
- Update the report in place after every stage in this run (Jira intake, `brainstorming`,
  `writing-plans`, Stage 03 implement/review loop, Stage 04/05 commit, Stage 06 completion):
  progress, current blocker/issue, cumulative Copilot requests, and input/response token
  estimates. Label token counts as estimates when exact counts are unavailable from the active
  tools.
- Keep the report current until the pipeline ends; do not skip updates because a stage "handed
  back" — a finished stage is not a stop condition (see
  [../shared/global-rules.md](../shared/global-rules.md)).
- Skip this section entirely for manual (non-`--issue`) runs — there is no Jira metadata to track.
