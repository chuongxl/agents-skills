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
`implement`, `converge`. Skills-mode folders are `speckit-<command>`; the slash command is always
`/speckit.<command>`.

| Host | `specify init` key | Layout to probe (first complete set wins) | Invocation |
|------|--------------------|-------------------------------------------|------------|
| GitHub Copilot | `copilot` | `.github/skills/speckit-<command>/SKILL.md` (skills mode) **or** `.github/agents/speckit.<command>.agent.md` + `.github/prompts/speckit.<command>.prompt.md` (commands mode) | `/speckit.<command>` slash-agent |
| Claude Code | `claude` | `.claude/skills/speckit-<command>/SKILL.md` | `/speckit.<command>` slash-agent or `Skill` tool |
| OpenCode | `opencode` | `.opencode/skills/` then `.agents/skills/` then `.claude/skills/` | `skill` tool by resolved name |

Never fall back to a global or external Speckit variant — the repo-installed agents are the only
valid source.

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
6. **Prove executability**: invoke `speckit.constitution` through the host channel within the
   same turn (Copilot: repo slash-agent `/speckit.constitution`, not the `skill` tool; Claude
   Code: `/speckit.constitution` or `Skill` tool; OpenCode: `skill` tool by resolved name). It
   must succeed — otherwise stop and report.
7. **Re-run the source check** from step 1 of Stage 01 against the repo layout. On pass, continue
   the pipeline in the same turn. Only a concrete install/init/constitution failure stops the run.

## Invocation Rules (all stages)

- Copilot / Claude Code: emit the literal `/speckit.<command> ...` as this session's own next
  assistant message — the current host runtime intercepts and executes the repo agent in this
  turn. OpenCode: the `skill` tool by the stage's resolved skill name.
- NEVER use the `task` tool with a `speckit.*` agent_type (fails with `Unknown agent_type`).
- NEVER shell out to a nested `copilot`/`claude`/`opencode` CLI subprocess from bash — that spawns
  an unrelated, unbounded nested session (see host-adaptation.md). A stage invocation is only the
  literal slash command as this turn's own message, or the `skill` tool call.
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