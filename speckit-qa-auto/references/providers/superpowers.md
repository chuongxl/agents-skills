# Provider Adapter: superpowers (QA Edition)

The `obra/superpowers` skills library adapted for `speckit-qa-auto`. Loaded when provider is `superpowers`.

## Skill Map

| Pipeline Step | Superpowers Skill |
|---------------|-------------------|
| Bootstrap | `using-superpowers` |
| Stage 02 Brainstorming | `brainstorming` |
| Stage 02 Test Planning | `writing-plans` |
| Stage 03 Automation | `subagent-driven-development` or `executing-plans` |
| Stage 03 TDD Cycle | `test-driven-development` |
| Stage 03 Debugging | `systematic-debugging` |
| Completion Gate | `verification-before-completion` |
| Stage 04 Completion | `finishing-a-development-branch` |

## Availability & Recovery

- Check for required skills in session or on disk (`~/.agents/skills/`, `~/.claude/skills/`, `~/.config/opencode/skills/`).
- If missing, trigger host-specific install command (`copilot plugin install`, `claude plugin install`, or `git clone`).
- After install, run post-install validation; if failing, request host session restart.
