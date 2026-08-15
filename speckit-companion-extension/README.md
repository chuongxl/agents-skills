# Speckit Companion Extension

Editor settings for the [Spec Kit companion VS Code extension](https://github.com/github/spec-kit),
wiring it up to drive a `superpowers`-based workflow instead of the built-in one.

This folder is **not a skill** — it holds no `SKILL.md` and is skipped by
`tools/validate_skills.py`. It is configuration you merge into your editor.

## What `setting.json` Configures

| Setting | Effect |
|---------|--------|
| `speckit.aiProvider` | Routes companion actions through GitHub Copilot |
| `speckit.telemetry` | Disabled |
| `speckit.companion.installPrompt` | Suppresses the repeat install prompt |
| `speckit.customWorkflows` | Adds a **Superpowers** workflow: Brainstorm → Plan → Execute (TDD) → Verify |
| `speckit.customCommands` | Adds worktree isolation, systematic debugging, code review, and branch-finishing commands to the relevant steps |

## Workflow Steps

| Step | Command | Produces |
|------|---------|----------|
| Brainstorm | `superpowers:brainstorming` | `spec.md` |
| Plan | `superpowers:writing-plans` | `plan.md` |
| Execute (TDD) | `superpowers:subagent-driven-development` | code |
| Verify | `superpowers:verification-before-completion` | verification evidence |

The `spec.md` this workflow produces is exactly the input `speckit-code-review`
expects, so the two compose directly.

## Install

Merge the contents into your VS Code settings:

```bash
# Workspace settings
mkdir -p .vscode
cp speckit-companion-extension/setting.json .vscode/settings.json
```

If `.vscode/settings.json` already exists, merge the keys by hand rather than
overwriting — the file is a fragment, not a complete settings file.

## Prerequisites

- The Spec Kit companion VS Code extension.
- The [`obra/superpowers`](https://github.com/obra/superpowers) skills library,
  since every command references a `superpowers:*` skill.

Without the superpowers library installed, the custom workflow steps resolve to
nothing and the companion falls back to its default behaviour.
