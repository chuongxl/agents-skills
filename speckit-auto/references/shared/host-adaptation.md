# Shared: Host Adaptation (GitHub Copilot / Claude Code / OpenCode)

This skill runs on three host agents. The pipeline is identical on all three; only the discovery
directory, tool names, and invocation channel differ. Load once at entry dispatch; the host is
fixed for the whole run.

## Host Detection (first match wins)

1. **Discovery directory** — the folder this `SKILL.md` was loaded from implies the host:
   `~/.agents/skills/`, `.github/skills/`, `~/.copilot/skills/` → Copilot;
   `~/.claude/skills/`, `.claude/skills/` → Claude Code;
   `~/.config/opencode/skills/`, `.opencode/skills/` → OpenCode.
2. **Tool-surface confirmation** when directories overlap: repo slash-agents under `.github/agents/`
   + `copilot` CLI → Copilot; a `Skill` tool + `.claude/skills/` → Claude Code; an
   `<available_skills>` block with `skill`-tool loading and no skill slash commands → OpenCode.
3. If still ambiguous, default to GitHub Copilot and note the assumption. The Stage 01 source
   check is authoritative regardless — it probes actual repo files.

## Per-Host Map

| Aspect | GitHub Copilot | Claude Code | OpenCode |
|--------|----------------|-------------|----------|
| Skill dirs | `~/.agents/skills/`, `.github/skills/`, `~/.copilot/skills/` | `~/.claude/skills/`, `.claude/skills/` | `~/.config/opencode/skills/`, `.opencode/skills/`, plus `.claude/skills/` / `.agents/skills/` |
| Tool names | `bash glob grep view create edit skill` | `Bash Read Edit Write Glob Grep Skill` | `bash glob grep view create edit skill` |
| Invocation channel | `skill` tool for installed skills; `@speckit.<command>` agent call for repo agents | `Skill` tool for installed skills; `/speckit.<command>` slash command for repo agents | `skill` tool only — no agent calls or slash commands |
| Repo agent visibility | Slash commands (`/speckit.*`) are **not visible**; call via `@speckit.<command>` | Slash commands are visible and callable as `/speckit.<command>` | N/A — use `skill` tool only |
| Flags | slash-command body / agent message body | slash-command body / `$ARGUMENTS` | embedded in the natural-language trigger message |
| Mid-run resume marker | the skill tool list in tool context | `<skill-context name="...">` | `<available_skills>` block |
| Ask tool (default mode) | `ask_user` | `AskUser` | `question` |

Never refuse to act because a tool is named differently from `allowed-tools` — the capabilities
are equivalent across all three hosts.

## What a Repo Agent/Command Invocation Means (canonical statement)

Invoking a `speckit.*` repo agent means emitting the call as the literal content of this
session's own next assistant turn — so the current host runtime routes it to the repo agent and
executes it in this session:

- **GitHub Copilot:** emit `@speckit.<command> [args]` (agent call — slash commands are **not
  visible** on Copilot and must not be used).
- **Claude Code:** emit `/speckit.<command> [args]` (slash command — visible and callable).
- **OpenCode:** use the `skill` tool by the resolved on-disk name — no agent calls or slash
  commands available.

**This is a turn boundary (Copilot and Claude Code).** The agent call/slash command takes over
execution for the duration of that turn. `speckit-auto` does NOT continue in the same turn. When
the agent finishes and returns output, `speckit-auto` must resume in the **next turn**, read the
agent's output from the conversation, and validate the result before proceeding to the next step.

It does **not** mean spawning a second CLI process. Never invoke a stage by shelling out to a
`copilot`, `claude`, or `opencode` binary from bash — that starts an unrelated, unbounded nested
session. If no valid invocation channel is available for the resolved host, stop and report the
exact error; never work around it with a subprocess.

Provider-specific install keys, probe layouts, and invocation channels live in the provider
adapters: [../providers/github-speckit.md](../providers/github-speckit.md) and
[../providers/superpowers.md](../providers/superpowers.md).