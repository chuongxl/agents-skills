# Host Adaptation (GitHub Copilot / Claude Code / OpenCode)

Runs on three host agents; pipeline logic is identical — only discovery directory, tool names, and
invocation channel differ. Load once at entry dispatch, resolve the host, keep it fixed for the run.

## Host Detection (resolve once, first match wins)

1. **Discovery directory** — the folder this `SKILL.md` was loaded from implies the host:
   `~/.agents/skills/`, `.github/skills/`, `~/.copilot/skills/` → **Copilot**;
   `~/.claude/skills/`, `.claude/skills/` → **Claude Code**;
   `~/.config/opencode/skills/`, `.opencode/skills/` → **OpenCode**.
2. **Tool-surface confirmation** (overlapping dirs): repo slash-agents under `.github/agents/` +
   a `copilot` CLI → Copilot; `Skill` tool + `.claude/skills/` → Claude Code; an
   `<available_skills>` block with `skill`-tool loading and no skill slash commands → OpenCode.
3. Still ambiguous → default to **GitHub Copilot**, note the assumption. The provider Stage 01
   source check is authoritative regardless.

## Per-Host Map

| Aspect | GitHub Copilot | Claude Code | OpenCode |
|--------|----------------|-------------|----------|
| Skill dirs | `~/.agents/skills/`, `.github/skills/`, `~/.copilot/skills/` | `~/.claude/skills/`, `.claude/skills/` | `~/.config/opencode/skills/`, `.opencode/skills/`, plus `.claude/skills/` / `.agents/skills/` |
| Tool names | `bash glob grep view create edit skill` | `Bash Read Edit Write Glob Grep Skill` | `bash glob grep view create edit skill` |
| Invocation channel | `skill` tool; repo skills also surface as `/name` | `Skill` tool; user-invocable skills surface as `/name` | `skill` tool only — no skill slash commands |
| Ask tool | `ask_user` | `AskUser` | `question` |
| Mid-run resume marker | skill tool list in tool context | `<skill-context name="...">` | `<available_skills>` block |

## Rules

- Never refuse to act because a tool is named differently than `allowed-tools` — capabilities are
  equivalent across hosts.
- Provider layouts (probe paths, `specify init` keys, install commands) are owned by each
  provider's `stage-01-preflight-intake.md` and `install-recovery.md` — not restated here.
