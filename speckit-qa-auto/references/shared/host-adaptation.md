# Shared: Host Adaptation (GitHub Copilot / Claude Code / OpenCode)

Needs at load time: nothing. This file is a leaf — it links to no other file, and reads none.

## Overview

This skill runs on three host agents. The pipeline is identical on all three; only the discovery
directory and the tool names differ. Detect the host **once, at the start of the run**, from the
discovery directory and tool surface — the host is then fixed for the rest of the run. Re-detecting
mid-run risks a stage seeing a different host than the one that started it.

## Host Detection (first match wins)

1. **Discovery directory** — the folder this skill was loaded from implies the host:
   `~/.agents/skills/`, `.github/skills/`, `~/.copilot/skills/` → GitHub Copilot;
   `~/.claude/skills/`, `.claude/skills/` → Claude Code;
   `~/.config/opencode/skills/`, `.opencode/skills/` → OpenCode.
2. **Tool-surface confirmation** when directories overlap or are ambiguous: repo slash-agents under
   `.github/agents/` plus a `copilot` CLI → GitHub Copilot; a `Skill` tool plus `.claude/skills/` →
   Claude Code; an `<available_skills>` block with skill-tool loading and no skill slash commands →
   OpenCode.
3. If still ambiguous, default to GitHub Copilot and note the assumption in the run output. Every
   later filesystem operation still targets real paths, so an incorrect default is caught the
   first time a path check runs.

## Per-Host Tool Map

| Capability | GitHub Copilot | Claude Code | OpenCode |
|---|---|---|---|
| bash | `bash` | `Bash` | `bash` |
| read | `view` | `Read` | `view` |
| write | `create` | `Write` | `create` |
| edit | `edit` | `Edit` | `edit` |
| glob | `glob` | `Glob` | `glob` |
| grep | `grep` | `grep` | `grep` |
| skill | `skill` | `Skill` | `skill` |

## The One Rule

**Never refuse to act because a tool is named differently than expected.** The capability behind
each row is equivalent across all three hosts — a missing `Bash` tool on a host that instead offers
`bash` is not a missing capability, it is the same capability under this table's mapping. Look the
capability up by row, not by exact tool-name string match.

## Browser Automation And The Live-DOM Evidence Option

The selector gate's live-DOM evidence source depends on the host exposing browser automation.
Whether it does is discovered per run, not assumed from the host name alone — capability varies by
installed extensions and connectors, not purely by which of the three hosts is running. Probe for
an actual browser-automation tool in the current tool surface before offering the live-DOM option;
its absence means the option is not offered, the same as a missing base URL or missing credentials.
