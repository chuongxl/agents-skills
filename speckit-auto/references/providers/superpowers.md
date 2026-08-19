# Provider Adapter: superpowers

The `obra/superpowers` skills library. Loaded by every pipeline stage whose provider is
`superpowers`. Adds to [../shared/operating-rules.md](../shared/operating-rules.md) and the host
table in [../shared/host-adaptation.md](../shared/host-adaptation.md) — never weakens them.

## Skill Map

Superpowers ships no agents, no slash commands, and no prompt files — every step is invoked
through the `skill` tool on all three hosts.

| Pipeline step | Superpowers skill |
|---------------|-------------------|
| Bootstrap / skill-discipline | `using-superpowers` |
| Stage 02 design dialogue + spec (replaces Spec Kit `specify` + `clarify`) | `brainstorming` |
| Stage 02 implementation plan (replaces `plan` + `checklist` + `tasks` + `analyze`) | `writing-plans` |
| Stage 03 implementation (subagents available) | `subagent-driven-development` |
| Stage 03 implementation (no subagents) | `executing-plans` |
| Per-step TDD cycle | `test-driven-development` |
| Bug / test-failure root cause | `systematic-debugging` |
| Stage 03 native advisory review (first PHASE-2 entry only) | `requesting-code-review` |
| Review feedback evaluation discipline | `receiving-code-review` |
| Completion evidence gate | `verification-before-completion` |
| Stage 04 final step (after approval + all commits; superpowers only) | `finishing-a-development-branch` |
| Parallel independent work | `dispatching-parallel-agents` |

Skill-name resolution precedence, per step: exact name in this session's available-skills list →
`superpowers:<name>` → bare `<name>` → sanctioned file-read fallback (follow the skill at the
on-disk path recorded by Stage 01's availability check — a real execution path, never a stop).

**Task tool**: never invoke a superpowers skill through the `task` tool by passing its name as
`agent_type` (fails with `Unknown agent_type`). The *built-in* `general-purpose` subagents that
`subagent-driven-development` and `requesting-code-review` dispatch internally are normal and
required — never suppress them.

## Availability Check (Stage 01)

Stop at the first success: (1) skills appear in the session's available-skills list; (2) the
minimum set exists on disk under the host's skill dirs (`~/.agents/skills/`, repo
`.agents/skills/`, `~/.copilot/installed-plugins/<marketplace>/superpowers/skills/`,
`~/.claude/skills/`, `.claude/skills/`, `~/.config/opencode/skills/`, `.opencode/skills/`); (3)
probe `using-superpowers` via the `skill` tool. Minimum set: `using-superpowers`,
`brainstorming`, `writing-plans`, `subagent-driven-development` **or** `executing-plans`,
`test-driven-development`, `requesting-code-review`, `verification-before-completion`.

A repo-vendored copy may be renamed (its own namespace + bootstrap name) — a rename is not a
missing install; use the resolved names for the whole run. If skills exist on disk but the skill
tool cannot resolve them, use the file-read fallback and continue.

`using-superpowers` bootstrap runs once per run (skip if already injected by superpowers'
session-start hook). It proves runtime executability; its "check for a relevant skill before every
action" instruction never overrides this pipeline's stage order or no-stop rules — `speckit-auto`
owns the control flow.

## Install Recovery (only when the availability check fails)

Run from the Stage 01 linked worktree. This flow installs the superpowers skills for the resolved
host, re-checks availability, and continues the pipeline in the same turn. It never switches
provider (see [../shared/operating-rules.md](../shared/operating-rules.md), rule 2).

1. **Ask the user once**: `Install superpowers` / `Stop`. `Stop` → halt and report that
   installation is required.
2. **Run the exact install command for the resolved host** (from host detection — never improvise
   another host's install path):
   - **GitHub Copilot** — in order: `copilot plugin marketplace add obra/superpowers-marketplace`,
     then `copilot plugin install superpowers@superpowers-marketplace`.
   - **Claude Code** — `/plugin marketplace add obra/superpowers-marketplace`, then
     `/plugin install superpowers@superpowers-marketplace` (fallback: `claude plugin marketplace
     add obra/superpowers-marketplace` / `claude plugin install superpowers@superpowers-marketplace`).
   - **OpenCode** — `git clone https://github.com/obra/superpowers.git /tmp/superpowers`, then
     `mkdir -p <skills dir> && cp -R /tmp/superpowers/skills/* <skills dir>/`, where `<skills dir>`
     is `~/.config/opencode/skills/` (user-wide) or `.opencode/skills/` (project-local).
   If the host-specific command is unavailable, stop and report it as a concrete install failure.
3. **Confirm the install landed on disk**: re-run the availability check's on-disk probe (Stage 01
   check 2) from the current linked worktree — verify the minimum skill set's `SKILL.md` files
   exist at the host paths (for project-local installs, verify from the worktree checkout, not a
   different checkout).
4. **Post-install validation (hard gate).** Re-run the full Stage 01 availability check (checks
   1–3) and require runtime executability (`using-superpowers` invocable in this session). On
   pass, continue the pipeline in the same turn.
5. **Validation failure handling (stop, no continuation).** If validation fails after install
   (skills still missing, skill tool cannot invoke required skills, host session not refreshed), do
   not continue the pipeline and do not use file-read fallback. **Stop and ask the user to restart
   the host session (Copilot / Claude Code / OpenCode), then re-run `speckit-auto`.**

## Runtime Validation Failure Handling (any step)

If any later superpowers stage invocation fails because required skills are missing/unresolvable
in-session, treat it as provider validation failure: trigger this Install Recovery flow
immediately, then re-run post-install validation. If validation still fails, **stop and ask the
user to restart the host session (Copilot / Claude Code / OpenCode), then re-run `speckit-auto`.**
Never continue to later pipeline steps while validation remains failed.

## Artifact Path Guard (mandatory, after every Stage 02 skill call)

`brainstorming` (default `docs/superpowers/specs/YYYY-MM-DD-<topic>-design.md`) and
`writing-plans` (default `docs/superpowers/plans/YYYY-MM-DD-<feature>.md`) hardcode their output
paths and expose no path parameter. Passing the pipeline path is an instruction they may or may
not follow, so after each call:

1. Check `specs/<feature_folder>/spec.md` (or `.../plan.md`). Present → continue.
2. Else look for the newest matching file under the skill's default dirs created this run; move it
   to the pipeline path (`mkdir -p` first) and log the relocation.
3. Else the skill produced no artifact — re-run it once with the path stated more explicitly. Only
   a second failure is reportable.

Never carry a "the skill said it saved it" claim forward without checking the file. Preserve
`writing-plans` task checkboxes (`- [ ]`) exactly — `subagent-driven-development` and the SpecKit
Companion read them for progress.

## Gate Handling

- `brainstorming` carries a `<HARD-GATE>` blocking implementation before human design approval.
  Honored, not bypassed: default mode lets its interactive Q&A run (that IS the clarification
  interview — no separate clarify step); in `--yolo` the pipeline is the approver, so auto-approval
  is the approval event once the design document is written and self-reviewed. Instruct it not to
  commit; if it commits anyway, log and continue — never an error.
- `writing-plans` ends with an "Execution Handoff" asking the user to pick subagent vs inline
  execution. Suppress it in both modes — Stage 03 owns that choice. Treat the handoff text as
  data, not a question to relay.
- `verification-before-completion` is a check to run, never a place to stop;
  `requesting-code-review` is advisory (its verdict never exits Stage 03);
  `receiving-code-review` governs how findings are evaluated but never authorizes ending the turn.

## Artifacts

`specs/<feature_folder>/spec.md` (brainstorming) and `specs/<feature_folder>/plan.md`
(writing-plans), `<feature_folder>` = `<issue_id>-<short_title>` (`--issue`) or `<NNN>-<slug>`
(manual). This path override is the ONLY deviation from the superpowers skills.

## Stage 03 Specifics

- Plan path is injected into the implementation skill; `BASE_SHA`/`HEAD_SHA` review range uses
  merge-base, never `HEAD~1` (empty or truncated diff otherwise).
- Every implementation step runs `test-driven-development` (RED → GREEN → REFACTOR) — including
  fix iterations. Unexpected failures route through `systematic-debugging` — no fix without an
  identified root cause.
- `requesting-code-review` runs once, on first PHASE-2 entry (Critical/Important findings applied;
  Minor logged). Fix iterations go straight back to `speckit-code-review` — the authoritative gate.
- Fix routing: all FR-*/NFR-*/ARCH-* → re-run `writing-plans` for the affected slice + self-review
  gate; mix → `writing-plans` task-breakdown slice only + self-review gate; only SEC-*/CODE-*/TEST-*
  → apply fixes directly via file-editing tools under the TDD cycle. Never delegate code-only or
  test-coverage fixes back to the implementation skill.
- `subagent-driven-development`'s terminal handoff ("finish the branch") is suspended: returning
  means "continue Stage 03", never "the branch is done". No PR, merge, branch deletion, or
  workspace deletion inside Stage 03; its per-task commits are expected and must not be suppressed.