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
2. The plugin is installed and enabled on disk:
   - skills directory: `~/.copilot/installed-plugins/<marketplace>/superpowers/skills/`
     (default marketplace directory name: `superpowers-marketplace`)
   - enabled flag: `~/.copilot/settings.json` → `enabledPlugins["superpowers@superpowers-marketplace"] = true`
3. Direct probe: invoke `using-superpowers` via the `skill` tool. If it returns content,
   superpowers is available and the bootstrap step below is already satisfied.

If the skills exist on disk (check 2) but the skill tool cannot resolve them, that is **not** a
failure — use the file-read fallback from [provider-rules.md](provider-rules.md) and continue.

At minimum these skills must be resolvable: `using-superpowers`, `brainstorming`, `writing-plans`,
`subagent-driven-development` **or** `executing-plans`, `test-driven-development`,
`requesting-code-review`, `verification-before-completion`.

If none of the three checks succeed, run install recovery below.

## Missing Superpowers Recovery (Required)

When superpowers is not available:

1. Fetch the install guide: `https://github.com/obra/superpowers` (GitHub Copilot CLI section).
2. Ask the user once: `Install superpowers` or `Stop`.
3. If `Stop`, halt and report that installation is required.
4. If `Install`, run both commands in order:
   - `copilot plugin marketplace add obra/superpowers-marketplace`
   - `copilot plugin install superpowers@superpowers-marketplace`
5. Confirm `~/.copilot/settings.json` has
   `enabledPlugins["superpowers@superpowers-marketplace"] = true`.
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
| Design spec (`brainstorming`) | `specs/<feature_folder>/spec.md` | `docs/superpowers/specs/<date>-<topic>-design.md` |
| Implementation plan (`writing-plans`) | `specs/<feature_folder>/plan.md` | `docs/superpowers/plans/<date>-<feature>.md` |

Both skills write into the **same** folder for a given feature — `brainstorming` creates it,
`writing-plans` adds to it. Pass the exact target path into each skill as an explicit user
instruction, since both accept a path override. The folder must stay stable across reruns of the
same issue.

Keep the plan's task checkboxes (`- [ ]`) exactly as `writing-plans` specifies:
`subagent-driven-development` and the Companion viewer both read them for progress.

This path override is the only deviation from the superpowers skills — everything else in them
applies unchanged.

Create `specs/<feature_folder>/` if missing.

## Stage 02 Entry Step

After intake completes, invoke `brainstorming` with the compact brief (or requirement
text) and the target design-spec path in the same turn, then continue to
[stage-02-spec-design-flow.md](stage-02-spec-design-flow.md).
