# superpowers: Provider-Specific Rules

Adds to [../shared/global-rules.md](../shared/global-rules.md). Never weakens it.
Also loads [../shared/host-adaptation.md](../shared/host-adaptation.md) for the per-host layout.

Provider: **superpowers** — the `obra/superpowers` skills library.

## Invocation

Superpowers ships **no agents, no slash commands, and no prompt files** — verified: the repo
contains only `skills/<name>/SKILL.md`, and its own porting docs list GitHub Copilot, Claude Code,
and OpenCode as using the *native skill tool* with "no adapter file needed". So every step is
invoked through the `skill` tool on all three hosts.

Resolve the skill name using this precedence, per step:

1. The name exactly as it appears in this session's available-skills list.
2. `superpowers:<name>` (the namespaced form used throughout superpowers' own docs).
3. Bare `<name>` (for example `brainstorming`).
4. **Sanctioned fallback** — if the skill tool cannot resolve it at all, read the file directly at
   the on-disk path recorded by the Stage 01 availability check (host-dependent, see
   [../shared/host-adaptation.md](../shared/host-adaptation.md): `~/.claude/skills/` on Claude Code,
   `~/.config/opencode/skills/` on OpenCode, `~/.agents/skills/` or the Copilot plugin path on
   Copilot) at `<skills-dir>/<name>/SKILL.md` and follow it. Superpowers' porting guide explicitly
   designates file-reading as the valid mechanism on a harness where the skill tool does not surface
   it. This is a real execution path, never a reason to stop.

| Purpose | Skill |
|---------|-------|
| Bootstrap / skill-discipline | `using-superpowers` |
| Design dialogue + spec document | `brainstorming` |
| Implementation plan | `writing-plans` |
| Implementation (subagents available) | `subagent-driven-development` |
| Implementation (no subagents) | `executing-plans` |
| Per-step TDD cycle | `test-driven-development` |
| Bug / test-failure root cause | `systematic-debugging` |
| Native code review pass | `requesting-code-review` |
| Responding to review feedback | `receiving-code-review` |
| Completion evidence gate | `verification-before-completion` |
| Branch finish / PR | `finishing-a-development-branch` |
| Parallel independent work | `dispatching-parallel-agents` |

### Task Tool: What Is Forbidden vs What Is Required

The two are easy to confuse. Read both lines before Stage 03.

- **Forbidden** — invoking a *superpowers skill* through the `task` tool by passing its name as
  `agent_type` (`superpowers:brainstorming`, `superpowers:subagent-driven-development`, …). The
  `task` tool only accepts fixed built-in agent types and fails with `Unknown agent_type`. Skills
  are invoked through the `skill` tool, per the precedence above.
- **Required** — the *built-in* subagent dispatch that superpowers skills themselves perform.
  `subagent-driven-development` dispatches a fresh implementer and a task reviewer per task, and
  `requesting-code-review` dispatches a `general-purpose` code reviewer. Those dispatches use the
  built-in agent types and are a normal, expected part of Stage 03. Never suppress them.

In one sentence: never a `superpowers:*` name as `agent_type`; always allow `general-purpose`
subagents dispatched from inside a superpowers skill.

## Rules

1. All pipeline steps use superpowers skills invoked through the `skill` tool (with the documented
   file-read fallback). No repo `.github/agents/speckit.*` file is required or consulted in this
   provider, and no superpowers slash command or agent exists.
2. If the superpowers skills are not available, Stage 01 runs install recovery (ask `Install` /
   `Stop`, then install and re-check). See Stage 01.
3. Stage 01 in [../shared/branching.md](../shared/branching.md) is authoritative for isolation: its
   workspace gate checks out the working branch — in place by default, in a worktree under
   `--worktree` — after intake and before the Stage 02 entry step.
   `subagent-driven-development`'s "create or verify isolated workspace" requirement is satisfied by
   that gate, whichever strategy it chose. Do not create another worktree in later stages, and
   never stop to ask which workspace to use. Root-level commands run in `workspace_root`; commands
   targeting a mapped submodule run in its workspace from `submodule_workspaces{}`.
4. `superpowers:finishing-a-development-branch` is **not** used for branch lifecycle or workspace
   cleanup. It may only be used at Stage 04/05 to open a PR, and only after the pipeline's own
   commit rules have run.
   **`subagent-driven-development`'s terminal handoff is suspended along with it.** That skill
   ends with "final review clean → delete this plan's workspace → use
   `superpowers:finishing-a-development-branch`". Both of those steps are Stage 04/05 territory and
   must not run inside Stage 03: no PR, no merge, no branch deletion, no workspace deletion when
   the implementation skill reports done. Returning from the implementation skill means "go to the
   next Stage 03 phase", never "the branch is finished".
5. Artifacts live under `specs/`, one folder per feature (same place as Spec Kit output):
   - design spec → `specs/<feature_folder>/spec.md`
   - plan → `specs/<feature_folder>/plan.md`
   `<feature_folder>` = `<issue_id>-<short_title>` in `--issue` mode, or `<NNN>-<slug>` (next
   unused three-digit prefix under `specs/`) in manual mode. See Stage 01.
   This replaces the superpowers defaults `docs/superpowers/specs/<date>-<topic>-design.md` and
   `docs/superpowers/plans/<date>-<feature>.md`, and is the **only** deviation from those skills.
   **These skills expose no path parameter** — `brainstorming` and `writing-plans` each hardcode
   their output path in their own SKILL.md. Passing the target path is an instruction they may or
   may not follow, so it is never sufficient on its own: after each skill returns, Stage 02 must
   verify the file exists at the pipeline path and relocate it if the skill used its default. See
   the Artifact Path Guard in [stage-02-spec-design-flow.md](stage-02-spec-design-flow.md).
   Preserve the plan's task checkboxes (`- [ ]`) exactly as `writing-plans` emits them —
   `subagent-driven-development` and the Companion viewer read them for progress.
6. `superpowers:brainstorming` replaces Spec Kit's `specify` + `clarify`. Its interactive Q&A is
   **allowed in default mode** (it is the clarification interview) and **suppressed in `--yolo`
   mode**, where it must auto-answer from the intake brief and skip section approvals.
   `brainstorming` carries a `<HARD-GATE>` forbidding any implementation action before a human
   approves the design. That gate is honored, not bypassed: in `--yolo` the pipeline is the
   approver, so auto-approval **is** the approval event and the gate is satisfied the moment the
   design document is written and self-reviewed. Never wait for a human message in `--yolo`.
   `brainstorming` also commits the design document itself. Instruct it not to commit (the pipeline
   owns commits); if it commits anyway, that is harmless — log it and continue, never treat it as
   an error or re-commit the same file.
7. `superpowers:writing-plans` replaces Spec Kit's `plan` + `checklist` + `tasks` + `analyze`.
   Its self-review must explicitly cover spec coverage, placeholder scan, and consistency — these
   are the checklist/analyze equivalents.
8. `superpowers:test-driven-development` is mandatory for every implementation step: RED (watch it
   fail) → GREEN (watch it pass) → REFACTOR.
9. Code review is two-tier and ordered: run `superpowers:requesting-code-review` once, on first
   entry to the Stage 03 review phase, then `speckit-code-review`. Fix iterations go straight back
   to `speckit-code-review` — the advisory pass is not repeated.
   **`speckit-code-review` is the authoritative pass/fail gate** that drives the Stage 03 fix loop.
   A superpowers review verdict never ends Stage 03.
10. `superpowers:verification-before-completion` must run before any completion claim or commit.
11. `superpowers:systematic-debugging` is used whenever a test fails or a bug is found — no fix
    without an identified root cause.
12. `superpowers:receiving-code-review` governs how review feedback is evaluated (technical
    assessment, YAGNI check) but never authorizes ending the turn on a `failed` verdict.
