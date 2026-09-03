# Shared: Host Lookup (load on demand)

Load **only** when a step needs a host-specific value that the SKILL.md entry dispatch didn't
already fix: the ask-tool name at a human checkpoint, the `specify init` host key during install
recovery, or the on-disk skill directories during an availability probe. The host is detected once
at entry and fixed for the whole run.

| Aspect | GitHub Copilot | Claude Code | OpenCode |
|--------|----------------|-------------|----------|
| Skill dirs | `~/.agents/skills/`, `.agents/skills/`, `.github/skills/`, `~/.copilot/skills/`, `~/.copilot/installed-plugins/<marketplace>/superpowers/skills/` | `~/.claude/skills/`, `.claude/skills/` | `~/.config/opencode/skills/`, `.opencode/skills/`, plus `.claude/skills/` / `.agents/skills/` |
| Tool names | `bash glob grep view create edit skill` | `Bash Read Edit Write Glob Grep Skill` | `bash glob grep view create edit skill` |
| Ask tool (default mode) | `ask_user` | `AskUser` | `question` |
| Flags arrive via | slash-command body | slash-command body / `$ARGUMENTS` | the natural-language trigger message |
| Mid-run resume marker | the skill tool list in tool context | `<skill-context name="...">` | `<available_skills>` block |
| `specify init` host key | `copilot` | `claude` | `opencode` |

Never refuse to act because a tool is named differently from `allowed-tools` — the capabilities
are equivalent on all three hosts.

## Overlapping-Directory Tie-Break

Skill dirs overlap (`.claude/skills/` and `.agents/skills/` appear under more than one host), so
when the discovery directory alone is ambiguous, confirm from the tool surface:

- repo slash-agents under `.github/agents/` + a `copilot` CLI → **Copilot**
- a `Skill` tool (capital S) + `.claude/skills/` → **Claude Code**
- an `<available_skills>` block with `skill`-tool loading and no skill slash commands → **OpenCode**

Still ambiguous → default to GitHub Copilot and note the assumption; the Stage 01 provider gate is
authoritative anyway because it probes actual repo files.
