# superpowers: Provider-Specific Rules

Adds to [../shared/global-rules.md](../shared/global-rules.md). Never weakens it.

Provider: **superpowers** — the `obra/superpowers` skills library.

## Invocation

Superpowers ships **no agents, no slash commands, and no prompt files** — verified: the repo
contains only `skills/<name>/SKILL.md`, and its own porting docs list GitHub Copilot CLI as using
the *native Skill tool* with "no adapter file needed". So every step is invoked through the
`skill` tool.

Resolve the skill name using this precedence, per step:

1. The name exactly as it appears in this session's available-skills list.
2. `superpowers:<name>` (the namespaced form used throughout superpowers' own docs).
3. Bare `<name>` (for example `brainstorming`).
4. **Sanctioned fallback** — if the skill tool cannot resolve it at all, read the file directly at
   `~/.copilot/installed-plugins/<marketplace>/superpowers/skills/<name>/SKILL.md` and follow it.
   Superpowers' porting guide explicitly designates file-reading as the valid mechanism on a
   harness where the skill tool does not surface it. This is a real execution path, never a reason
   to stop.

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

Never attempt these via the `task` tool with a `superpowers:*` agent_type — the `task` tool only
accepts fixed built-in agent types and will fail with `Unknown agent_type`.

## Rules

1. All pipeline steps use superpowers skills invoked through the `skill` tool (with the documented
   file-read fallback). No repo `.github/agents/speckit.*` file is required or consulted in this
   provider, and no superpowers slash command or agent exists.
2. If the superpowers skills are not available, Stage 01 runs install recovery (ask `Install` /
   `Stop`, then install and re-check). See Stage 01.
3. `superpowers:using-git-worktrees` is **never used**. Branching follows
   [../shared/branching.md](../shared/branching.md) — plain branch off `develop → main → master`.
   Any superpowers instruction to create a worktree is overridden.
4. `superpowers:finishing-a-development-branch` is **not** used for branch lifecycle or worktree
   cleanup. It may only be used at Stage 04/05 to open a PR, and only after the pipeline's own
   commit rules have run.
5. Artifacts keep Jira traceability:
   - design spec → `docs/superpowers/specs/<issue_id>-<short_title>-design.md`
   - plan → `docs/superpowers/plans/<issue_id>-<short_title>.md`
   In manual (non-Jira) mode, substitute the requirement slug for `<issue_id>-<short_title>`.
   The superpowers default `YYYY-MM-DD-` prefix is replaced by this rule.
6. `superpowers:brainstorming` replaces Spec Kit's `specify` + `clarify`. Its interactive Q&A is
   **allowed in default mode** (it is the clarification interview) and **suppressed in `--yolo`
   mode**, where it must auto-answer from the intake brief and skip section approvals.
7. `superpowers:writing-plans` replaces Spec Kit's `plan` + `checklist` + `tasks` + `analyze`.
   Its self-review must explicitly cover spec coverage, placeholder scan, and consistency — these
   are the checklist/analyze equivalents.
8. `superpowers:test-driven-development` is mandatory for every implementation step: RED (watch it
   fail) → GREEN (watch it pass) → REFACTOR.
9. Code review is two-tier and ordered: run `superpowers:requesting-code-review` first, then
   `speckit-code-review`. **`speckit-code-review` is the authoritative pass/fail gate** that drives
   the Stage 03 fix loop. A superpowers review verdict never ends Stage 03.
10. `superpowers:verification-before-completion` must run before any completion claim or commit.
11. `superpowers:systematic-debugging` is used whenever a test fails or a bug is found — no fix
    without an identified root cause.
12. `superpowers:receiving-code-review` governs how review feedback is evaluated (technical
    assessment, YAGNI check) but never authorizes ending the turn on a `failed` verdict.
