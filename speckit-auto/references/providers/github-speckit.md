# Provider Adapter: github-speckit

Repository-installed GitHub Spec Kit agents. Loaded by every pipeline stage whose provider is
`github-speckit`. Adds to [../shared/operating-rules.md](../shared/operating-rules.md) and the
host table in [../shared/host-adaptation.md](../shared/host-adaptation.md) — never weakens them.

## Stage Agent Map

| Pipeline step | Stage agent | Stage order |
|---------------|-------------|-------------|
| Stage 02 spec/design | `speckit.specify` → `speckit.clarify` → `speckit.plan` → `speckit.checklist` → `speckit.tasks` → `speckit.analyze` | Fixed, never skip/reorder/optionalize in either mode |
| Stage 02 design-spec approval | covered by the review interview + Stage 03 entry confirmation | — |
| Stage 03 implement | `speckit.implement` (user wording `speckit.implementation` maps here) | — |
| Stage 03 convergence | `speckit.converge` | run after implement until it reports no gaps |

Constitution: `speckit.constitution` must run once per pipeline run, through the host channel,
and succeed before Stage 02 (mandatory gate). In install recovery it is also mandatory.

All artifacts (spec/plan/tasks/checklist/implementation) are produced ONLY by these repo agents.
`speckit-auto` never synthesizes spec/plan/tasks content or writes implementation code itself.

## Install / Layout Per Host

`<command>` = `constitution`, `specify`, `clarify`, `plan`, `checklist`, `tasks`, `analyze`,
`implement`, `converge`. Skills-mode folders are `speckit-<command>`; the agent file is
`speckit.<command>.agent.md`; the prompt file is `speckit.<command>.prompt.md`.

| Host | `specify init` key | Layout to probe (first complete set wins) | Invocation |
|------|--------------------|-------------------------------------------|------------|
| GitHub Copilot | `copilot` | `.github/skills/speckit-<command>/SKILL.md` (skills mode) **or** `.github/agents/speckit.<command>.agent.md` + `.github/prompts/speckit.<command>.prompt.md` (commands mode) | `@speckit.<command>` agent call |
| Claude Code | `claude` | `.claude/skills/speckit-<command>/SKILL.md` | `/speckit.<command>` slash command or `Skill` tool |
| OpenCode | `opencode` | `.opencode/skills/` then `.agents/skills/` then `.claude/skills/` | `skill` tool by resolved name |

Never fall back to a global or external Speckit variant — the repo-installed agents are the only
valid source.

## Critical: speckit.* Are Repo Agents/Commands — Not Skills

`speckit.*` commands (`constitution`, `specify`, `clarify`, `plan`, `checklist`, `tasks`,
`analyze`, `implement`, `converge`) are **repo-installed agents or prompt-files**. They are **not**
installable skills and must **never** be invoked via the `skill` tool on Copilot or Claude Code.

**Invocation channel per host:**

- **GitHub Copilot:** `speckit.*` agents live under `.github/agents/speckit.<command>.agent.md`.
  Slash commands (`/speckit.<command>`) are **not visible** on Copilot. Invoke by calling the
  agent directly: emit `@speckit.<command> [args]` as this session's own next assistant message.
  The Copilot runtime routes the `@agent` call to the repo agent and executes it in this session.
- **Claude Code:** invoke as `/speckit.<command> [args]` (slash command) or via the `Skill` tool
  for skills-mode layout. The slash command is visible and callable on Claude Code.
- **OpenCode:** repo agents/slash commands are not available. Invoke via the `skill` tool by the
  resolved on-disk skill name.

**This is a turn boundary (Copilot and Claude Code).** When `@speckit.<command>` or
`/speckit.<command>` is emitted, the agent takes over the current turn — `speckit-auto` does NOT
continue in the same turn. When the agent finishes and returns output, `speckit-auto` must
**resume in the next turn**, read the agent's output from the conversation, and validate the
result before proceeding. A missing, truncated, or error output means the agent did not complete —
treat as a failure; do NOT proceed.

**Consequence for `speckit.constitution`:**
- Copilot: emit `@speckit.constitution` → turn ends → resume next turn → read output → validate.
- Claude Code: emit `/speckit.constitution` → turn ends → resume next turn → read output →
  validate.
- OpenCode: invoke via `skill` tool → read return value → validate.
If constitution output is absent, truncated, or the agent stopped mid-run, it is a constitution
failure — do NOT proceed to Stage 02.

## Install Recovery (only when the source check fails)

Run from the Stage 01 linked worktree. A normal run never loads this. This flow installs the Spec
Kit CLI, initializes it into THIS repo for the resolved host, proves runtime executability, and
continues the pipeline in the same turn. It never switches provider.

1. **Install the CLI** (official channels — source install is recommended, PyPI is the fallback):
   - Source (pinned, requires `uv`): fetch the install guide
     `https://github.com/github/spec-kit/blob/main/docs/installation.md`, read the current
     release tag `vX.Y.Z` from the Releases page, then
     `uv tool install specify-cli --from git+https://github.com/github/spec-kit.git@vX.Y.Z`.
   - PyPI (simpler, no tag needed): `uv tool install specify-cli`, or `pipx install specify-cli`,
     or `pip install specify-cli`.
2. **Sanity check**: `specify version` must print a version. If the command is not found after a
   successful-looking install, PATH may not include the tool dir — report the exact output and
   stop; do not proceed with a broken install.
3. **Resolve the host key** from host detection (`copilot` / `claude` / `opencode`) — never guess,
   never ask.
4. **Ask the user once**: `Install GitHub Speckit` / `Stop` (the install commands above run only
   after this confirm). `Stop` → halt and report that installation is required. (Steps 1–2 may run
   before or after the ask; the gate below never runs before the ask.)
5. **Initialize into this repo (mandatory success gate)**:
   `specify init . --integration <host-key>` — for a Copilot repo that already uses the commands
   layout, pass `--integration-options="--commands"`. This command must succeed or the run stops
   with the exact failing output quoted.
6. **Prove executability**: invoke `speckit.constitution` through the resolved host channel:
   - **Copilot:** emit `@speckit.constitution` as the next assistant message. This ends the
     current turn — resume in the next turn and confirm constitution completed successfully.
   - **Claude Code:** emit `/speckit.constitution`. Same turn-boundary rule applies.
   - **OpenCode:** invoke via `skill` tool by resolved name; validate return value inline.
   Failure (absent/truncated output, agent stopped mid-run, tool resolution error) → stop and
   report the exact output; do not proceed.
7. **Post-install validation (hard gate).** Re-run the full Stage 01 source check against the repo
   layout and confirm `speckit.constitution` completed successfully in the prior turn.
8. **Validation failure handling (stop, no continuation).** If any validation step fails
   (missing agents/layout, constitution did not complete, command not found, host channel not
   ready), do not continue the pipeline. Stop and ask the user to manually install/fix the
   provider or restart the host session (Copilot / Claude Code / OpenCode), then re-run
   `speckit-auto`.

## Runtime Validation Failure Handling (any step)

If any later github-speckit stage invocation fails due to missing/invalid `speckit.*` agents,
layout drift, or host-channel resolution failure, treat it as provider validation failure: trigger
this Install Recovery flow immediately, then re-run post-install validation. If validation still
fails, stop and ask the user to manually install/fix or restart the host session. Never continue
to later pipeline steps while validation remains failed.

## Invocation Rules (all stages)

- **GitHub Copilot:** slash commands (`/speckit.<command>`) are **not visible**. Call the repo
  agent directly: emit `@speckit.<command> [args]` as this session's own next assistant message.
  This ends the current turn — resume in the next turn, read the agent output, and validate before
  continuing.
- **Claude Code:** emit `/speckit.<command> [args]` as this session's own next assistant message
  (slash command is visible and callable). This ends the current turn — resume in the next turn,
  read the output, and validate before continuing. For skills-mode layout, the `Skill` tool is
  also valid.
- **OpenCode:** use the `skill` tool by the stage's resolved on-disk skill name — no agent calls
  or slash commands available on this host.
- NEVER invoke a `speckit.*` command via the `skill` tool on Copilot or Claude Code (commands
  mode) — `speckit.*` are repo agents/commands, not installed skills on those hosts.
- NEVER use the `task` tool with a `speckit.*` agent_type (fails with `Unknown agent_type`).
- NEVER shell out to a nested `copilot`/`claude`/`opencode` CLI subprocess from bash — that spawns
  an unrelated, unbounded nested session (see host-adaptation.md).
- If a required stage cannot be invoked via the resolved host channel, stop and report the
  concrete invocation error — no manual fallback, no subprocess retry.

## Artifacts

Spec Kit layout: `specs/<issue_id>-<short_title>/` in `--issue` mode, `specs/<nnn>-<slug>/` in
manual mode (Stage 01 resolves the exact path).

## Stage 03 Fix Routing

- PHASE 1: run `speckit.implement` → `speckit.converge` repeatedly until converge reports no gaps.
- PHASE 2 fix application (R6): re-invoke `speckit.implement` with a focused correction prompt
  built from the review `fixes[]`. Never edit files directly as a substitute for the agent.
- Fix classification routing: all FR-*/NFR-*/ARCH-* → re-run `speckit.plan` then `speckit.checklist`
  then `speckit.tasks` then `speckit.analyze`; mix of FR/ARCH + code/test → `speckit.checklist` then
  `speckit.tasks` then `speckit.analyze`; only SEC-*/CODE-*/TEST-* → implement directly. After any
  artifact regeneration, re-run the Stage 02 self-review gate before the next fix iteration.