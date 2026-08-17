# Stage 01 (superpowers): Preflight + Intake

Provider: **superpowers** — the `obra/superpowers` skills library.

Load with this file:
- [provider-rules.md](provider-rules.md) — skill names, invocation precedence, provider rules
- [../shared/branching.md](../shared/branching.md) — workspace gate (runs last, after intake)
- [../shared/intake.md](../shared/intake.md) — issue resolution, run state, Jira intake
- [../shared/preflight-guidelines-context.md](../shared/preflight-guidelines-context.md) — project context

Execution order for this stage:
**superpowers availability check → install recovery if missing → bootstrap → guidelines load →
intake (shared) → artifact paths → workspace gate (shared) → Stage 02.**

Only the superpowers-specific steps are described below; everything else lives in the shared files.

## Preflight Superpowers Availability Check (Required)

Verify the superpowers skills are invocable. Check in this order and stop at the first success:

1. Superpowers skills appear in this session's available-skills list (names may be surfaced as
   `superpowers:<name>` or bare `<name>`) — record which form is used and reuse it all run.
2. The skills exist on disk. Probe the paths for the resolved host (see
   [../shared/host-adaptation.md](../shared/host-adaptation.md)) before concluding it is missing
   (`<name>` = any skill from the minimum set below):

   | Install shape | Skills path |
   |---|---|
   | Repo-vendored (project-local) | `<repo-root>/.agents/skills/<name>/SKILL.md` |
   | User-level skills dir (Copilot) | `~/.agents/skills/<name>/SKILL.md` |
   | Copilot CLI plugin | `~/.copilot/installed-plugins/<marketplace>/superpowers/skills/<name>/SKILL.md` |
   | User-level skills dir (Claude Code) | `~/.claude/skills/<name>/SKILL.md`, `.claude/skills/<name>/SKILL.md` |
   | User-level skills dir (OpenCode) | `~/.config/opencode/skills/<name>/SKILL.md`, `.opencode/skills/<name>/SKILL.md` |

   On Copilot, glob `<marketplace>` (typically `superpowers-marketplace`) rather than hardcoding it,
   and confirm the plugin is enabled in `~/.copilot/settings.json` →
   `enabledPlugins["superpowers@superpowers-marketplace"]`. Record the resolved directory once and
   reuse it for the file-read fallback all run.
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

When superpowers is not available, load [install-recovery.md](install-recovery.md) and follow it.
Never fall back to the `github-speckit` provider — the provider is fixed for the run.

## Bootstrap (Required, After Availability Check)

Invoke `using-superpowers` once per run. This is the superpowers skill-discipline bootstrap and
also proves runtime executability. Only a concrete error from this call is reportable as a runtime
failure (quote it), and only after the availability check passed.

Note: superpowers also injects this bootstrap through its session-start hook. If it is already
present in the session context, that satisfies this step — do not re-invoke it.

Do not let the bootstrap's "check for a relevant skill before every action" instruction override
this pipeline's stage order or its no-stop rules — `speckit-auto` owns the control flow.

## Scratch Path Hygiene (Required, Before Any Implementation)

Load [../shared/scratch-hygiene.md](../shared/scratch-hygiene.md) and apply it. Both `.speckit/`
and `.superpowers/` are produced in this provider.

## Preflight Guidelines Context Load (Required)

Load [../shared/preflight-guidelines-context.md](../shared/preflight-guidelines-context.md).
If `docs/guidelines/` or `architecture.md` is missing, skip and continue — never a stop.

## Workspace Handling (Critical)

The Stage 01 workspace gate in [../shared/branching.md](../shared/branching.md) already creates or
reuses the workspace — worktree isolation by default, an in-place feature branch under
`--no-worktree`. Do not invoke `using-git-worktrees` inside this provider stage, and do not assume
`workspace_root` is a worktree: in a `.gitmodules` repo it is always the repo root, because only
submodules get worktrees there.

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

`<feature_folder>` is also the branch name. Pass it to the workspace gate in
[../shared/branching.md](../shared/branching.md), which runs after this step and creates the branch
once under that exact string. There is no rename.

## Ticket Snapshot Relocation (Required, `--issue` Mode)

Right after the feature folder is created, **move** `.speckit/intake/<issue_id>-ticket.md` →
`specs/<feature_folder>/ticket.md` and record `ticket_path` in run state. Full rules (rerun
overwrite, never gitignore, never commit separately, never read back):
[../shared/intake.md](../shared/intake.md) → "Ticket Snapshot".
Pass only the compact brief into `brainstorming`, never the snapshot's contents.

## Stage 02 Entry Step

After intake completes, invoke `brainstorming` with the compact brief (or requirement
text) and the target design-spec path in the same turn, then continue to
[stage-02-spec-design-flow.md](stage-02-spec-design-flow.md).

## Execution Report (Jira-Sourced Runs)

In `--issue` mode, load [../shared/execution-report.md](../shared/execution-report.md) and
initialize the report at `specs/<feature_folder>/execution-report.md`.
