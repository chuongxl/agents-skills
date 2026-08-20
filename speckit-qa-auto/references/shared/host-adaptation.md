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
| grep | `grep` | `Grep` | `grep` |
| skill | `skill` | `Skill` | `skill` |

## The One Rule

**Never refuse to act because a tool is named differently than expected.** The capability behind
each row is equivalent across all three hosts — a missing `Bash` tool on a host that instead offers
`bash` is not a missing capability, it is the same capability under this table's mapping. Look the
capability up by row, not by exact tool-name string match.

## Subagent Dispatch Is A Capability, Not A Tool Name

Two parts of the pipeline dispatch subagents: discovery's three sweeps, and the selector gate's
live-DOM read. The tool that does it is named differently on each host and is absent on some tool
surfaces entirely, so it is deliberately not in the table above — probe the current tool surface for
a subagent-dispatch capability rather than matching a name.

**When none is available, the work still happens — inline, in the main run.** Every sweep keeps its
same output contract and its same bounds: structured lists, one link hop, no full issue bodies, no
full DOM. What is lost is context isolation, not capability, and the run says so once rather than
degrading silently.

This is why the sweeps were specified to return structured lists rather than prose in the first
place. A contract that only works when a subagent is available is a contract that breaks on the
hosts that need it most.

## Browser Automation And The Live-DOM Evidence Option

The selector gate's live-DOM evidence source depends on the host exposing browser automation.
Whether it does is discovered per run, not assumed from the host name alone — capability varies by
installed extensions and connectors, not purely by which of the three hosts is running. Probe for
an actual browser-automation tool in the current tool surface before offering the live-DOM option;
its absence means the option is not offered, the same as a missing base URL or missing credentials.
