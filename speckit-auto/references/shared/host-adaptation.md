# Shared: Host Lookup (load on demand)

Load **only** when a step needs a host-specific value that the SKILL.md entry dispatch didn't
already fix: the ask-tool name at a human checkpoint, the `specify init` host key during install
recovery, or the on-disk skill directories during an availability probe. The host is detected once
at entry and fixed for the whole run.

| Aspect | GitHub Copilot | Claude Code | OpenCode | Hermes Agent |
|--------|----------------|-------------|----------|--------------|
| Skill dirs | `~/.agents/skills/`, `.agents/skills/`, `.github/skills/`, `~/.copilot/skills/`, `~/.copilot/installed-plugins/<marketplace>/superpowers/skills/` | `~/.claude/skills/`, `.claude/skills/` | `~/.config/opencode/skills/`, `.opencode/skills/`, plus `.claude/skills/` / `.agents/skills/` | `~/.hermes/skills/` (bind-mounted as `/opt/data/skills/` in Docker) |
| Tool names | `bash glob grep view create edit skill` | `Bash Read Edit Write Glob Grep Skill` | `bash glob grep view create edit skill` | `terminal read_file write_file patch search_files skill_view` |
| Ask tool (default mode) | `ask_user` | `AskUser` | `question` | plain chat message in the session; user approves via a Slack button, `!approve`/`!deny` in the thread, or a reply in the desktop app |
| Flags arrive via | slash-command body | slash-command body / `$ARGUMENTS` | the natural-language trigger message | the natural-language trigger message (e.g. `@hermes start DEMO-42 --issue <url>` in a Slack thread, or a desktop message) |
| Mid-run resume marker | the skill tool list in tool context | `<skill-context name="...">` | `<available_skills>` block | none needed -- Hermes sessions never rotate on timers; the same Slack thread / session id is the run |
| `specify init` host key | `copilot` | `claude` | `opencode` | `hermes` |

Never refuse to act because a tool is named differently from `allowed-tools` — the capabilities
are equivalent on all four hosts. On Hermes Agent, `AskUser`/`ask_user`/`question` all resolve to
posting a plain message and waiting for the user's reply (Slack or desktop); there is no dedicated
ask-tool call.

## Overlapping-Directory Tie-Break

Skill dirs overlap (`.claude/skills/` and `.agents/skills/` appear under more than one host), so
when the discovery directory alone is ambiguous, confirm from the tool surface:

- repo slash-agents under `.github/agents/` + a `copilot` CLI → **Copilot**
- a `Skill` tool (capital S) + `.claude/skills/` → **Claude Code**
- an `<available_skills>` block with `skill`-tool loading and no skill slash commands → **OpenCode**
- loaded from `~/.hermes/skills/` or `/opt/data/skills/`, with `terminal`/`read_file`/`patch`/
  `skill_view` tools and no `Skill`/`ask_user`/`question` tool present → **Hermes Agent**

Still ambiguous → default to GitHub Copilot and note the assumption; the Stage 01 provider gate is
authoritative anyway because it probes actual repo files.
