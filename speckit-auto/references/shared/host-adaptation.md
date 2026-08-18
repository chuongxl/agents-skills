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
| Invocation channel | `skill` tool for all skills (including `speckit-*`) | `Skill` tool for all skills (including `speckit-*`) | `skill` tool for all skills |
| Flags | slash-command body | slash-command body / `$ARGUMENTS` | embedded in the natural-language trigger message |
| Mid-run resume marker | the skill tool list in tool context | `<skill-context name="...">` | `<available_skills>` block |
| Ask tool (default mode) | `ask_user` | `AskUser` | `question` |

Never refuse to act because a tool is named differently from `allowed-tools` — the capabilities
are equivalent across all three hosts.

## Skill Invocation (canonical statement)

All skills — including `speckit-*` repo-installed skills — are invoked via the `skill` tool by
name on every host. The `skill` tool returns inline in the same turn. There are no slash commands,
no agent calls, and no turn boundaries for skill invocations.

```
skill speckit-constitution    # same on Copilot, Claude Code, and OpenCode
skill speckit-specify
skill speckit-implement
...
```

Never invoke skills by shelling out to a `copilot`, `claude`, or `opencode` CLI subprocess —
that starts an unrelated, unbounded nested session. Never use the `task` tool with a skill name.
If a skill cannot be resolved by the `skill` tool, it is a provider validation failure — trigger
install recovery per the provider adapter.

Provider-specific install keys, probe layouts, and install commands live in the provider
adapters: [../providers/github-speckit.md](../providers/github-speckit.md) and
[../providers/superpowers.md](../providers/superpowers.md).