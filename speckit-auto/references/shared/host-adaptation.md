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
| Invocation channel | `skill` tool; repo skills also surface as `/name` slash commands | `Skill` tool; invocable skills surface as `/name` | `skill` tool only — no slash commands |
| Flags | slash-command body | slash-command body / `$ARGUMENTS` | embedded in the natural-language trigger message |
| Mid-run resume marker | the skill tool list in tool context | `<skill-context name="...">` | `<available_skills>` block |
| Ask tool (default mode) | `ask_user` | `AskUser` | `question` |

Never refuse to act because a tool is named differently from `allowed-tools` — the capabilities
are equivalent across all three hosts.

## What a Repo Slash-Agent Command Means (canonical statement)

"Invoke `/speckit.<command> ...`" means: emit that text as the literal content of this session's
own next assistant turn, the same way a human would type it in this same chat — so the current
host runtime intercepts and executes the repo agent in this session, in this turn. It does **not**
mean spawning a second CLI process. Never invoke a stage by shelling out to a `copilot`,
`claude`, or `opencode` binary from bash — that starts an unrelated, unbounded nested session.
The only two valid invocation channels are the literal slash command as this turn's own message
(Copilot, Claude Code) and the `skill` tool by the stage's resolved skill name (OpenCode, and the
Claude Code fallback). If neither channel is available, the stage invocation failed — stop and
report the exact error; never "work around" it with a nested subprocess.

Provider-specific install keys, probe layouts, and install commands live in the provider
adapters: [../providers/github-speckit.md](../providers/github-speckit.md) and
[../providers/superpowers.md](../providers/superpowers.md).