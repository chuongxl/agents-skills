# Host Adaptation (GitHub Copilot / Claude Code / OpenCode)

This skill runs on three host agents: **GitHub Copilot**, **Claude Code**, and **OpenCode**. The
pipeline logic is identical on all three; only the discovery directory, tool names, and invocation
channel differ. Load this file once at entry dispatch, resolve the host, and keep it fixed for the
whole run.

## Host Detection (resolve once, first match wins)

1. **Discovery directory** — the folder this `SKILL.md` was loaded from implies the host:
   - `~/.agents/skills/`, `.github/skills/`, `~/.copilot/skills/` → **GitHub Copilot**
   - `~/.claude/skills/`, `.claude/skills/` → **Claude Code**
   - `~/.config/opencode/skills/`, `.opencode/skills/` → **OpenCode**
2. **Tool-surface confirmation** (disambiguate overlapping dirs, e.g. `~/.agents/skills/`):
   - Repo slash-agents under `.github/agents/` and a `copilot` CLI → Copilot
   - `Skill` tool (capitalized) and `.claude/skills/` present → Claude Code
   - A `<available_skills>` context block with `skill`-tool loading and no skill slash commands →
     OpenCode
3. If still ambiguous, default to **GitHub Copilot** and note the assumption in the run state. The
   Stage 01 source check is authoritative regardless — it probes actual repo files.

## Per-Host Map

| Aspect | GitHub Copilot | Claude Code | OpenCode |
|--------|----------------|-------------|----------|
| Skill dirs | `~/.agents/skills/`, `.github/skills/`, `~/.copilot/skills/` | `~/.claude/skills/`, `.claude/skills/` | `~/.config/opencode/skills/`, `.opencode/skills/`, plus `.claude/skills/` / `.agents/skills/` |
| Tool names | `bash glob grep view create edit skill` | `Bash Read Edit Write Glob Grep Skill` | `bash glob grep view create edit skill` |
| Invocation channel | `skill` tool; repo skills also surface as `/name` slash commands | `Skill` tool; user-invocable skills surface as `/name` | `skill` tool only — no skill slash commands |
| Skill trigger / flags | `/skill-name <flags...>` body | `/skill-name` body or `$ARGUMENTS` | flags embedded in the natural-language message that triggered the skill |
| Mid-run resume marker | the skill tool list in tool context | `<skill-context name="...">` | `<available_skills>` block |

Rule: never refuse to act because a tool is named differently than `allowed-tools`. The capabilities
are equivalent across all three hosts.

## github-speckit Provider Layout (per host)

Probe order for the Stage 01 source check; install with the host's `--integration` key.

| Host | `specify init` key | Installed layout to probe | Invocation |
|------|--------------------|---------------------------|------------|
| GitHub Copilot | `copilot` | `.github/skills/speckit-<command>/SKILL.md` (skills mode, default) **or** `.github/agents/speckit.<command>.agent.md` + `.github/prompts/speckit.<command>.prompt.md` (commands mode, `--integration-options="--commands"`) | `/speckit.<command>` repo slash-agent command |
| Claude Code | `claude` | `.claude/skills/speckit-<command>/SKILL.md` | `/speckit.<command>` slash command (user-invocable skills) or `Skill` tool |
| OpenCode | `opencode` | `.opencode/skills/speckit-<command>/SKILL.md`, then `.agents/skills/`, then `.claude/skills/` | `skill` tool by the resolved skill name; no slash commands |

`<command>` is one of: `constitution`, `specify`, `clarify`, `plan`, `checklist`, `tasks`,
`analyze`, `implement`, `converge`. Skills-mode installs name the folder `speckit-<command>`; the
slash command is always `/speckit.<command>`.

## superpowers Provider Layout (per host)

| Host | Skill dirs to probe | Install |
|------|---------------------|---------|
| GitHub Copilot | `~/.agents/skills/<name>/SKILL.md`, repo `.agents/skills/<name>/SKILL.md`, `~/.copilot/installed-plugins/<marketplace>/superpowers/skills/<name>/SKILL.md` | `copilot plugin marketplace add obra/superpowers-marketplace` then `copilot plugin install superpowers@superpowers-marketplace` |
| Claude Code | `~/.claude/skills/<name>/SKILL.md`, `.claude/skills/<name>/SKILL.md` | `/plugin marketplace add obra/superpowers-marketplace` then `/plugin install superpowers@superpowers-marketplace` (fallback: `claude plugin marketplace add ...`) |
| OpenCode | `~/.config/opencode/skills/<name>/SKILL.md`, `.opencode/skills/<name>/SKILL.md` | Ask the user **Install** / **Stop** first. On Install: `git clone https://github.com/obra/superpowers.git /tmp/superpowers && mkdir -p <opencode skills dir> && cp -R /tmp/superpowers/skills/* <opencode skills dir>/` |

`<name>` is a superpowers skill such as `brainstorming`, `debugging`, `executing`, `planning`,
`writing-plans`, `systematic-testing`. The availability probe globs all of them.

## Rules

- The host is resolved once at entry dispatch and never changes mid-run.
- The provider's Stage 01 source check is authoritative for layout; this file only lists candidates.
- The `--integration` key passed to `specify init` must match the resolved host (`copilot` /
  `claude` / `opencode`). Never pass a key that does not match the resolved host.
- If the host-specific install command is not available in this environment, stop and report the
  exact manual command from the table above instead of guessing an alternative.
