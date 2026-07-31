Here’s the setup checklist.

## 1. GitHub Copilot CLI

- Place both skills here:
  - `~/.agents/skills/speckit-auto/SKILL.md`
  - `~/.agents/skills/speckit-code-review/SKILL.md`
- Make sure the frontmatter `name:` matches the folder name.
- Keep the `description:` trigger phrases clear, so Copilot can resolve them.
- No extra command registration is needed if Copilot is already reading `~/.agents/skills`.

## 2. Claude Code

- Add command files:
  - `/.claude/commands/speckit-auto.md`
  - `/.claude/commands/speckit-code-review.md`
- Each file should contain the skill content or point to it.
- Use slash commands:
  - `/speckit-auto`
  - `/speckit-code-review`

## 3. OpenCode

- Add instruction files:
  - `/.opencode/instructions/speckit-auto.md`
  - `/.opencode/instructions/speckit-code-review.md`
- Use the same skill content or symlink/copy it.
- Invoke with:
  - `/speckit-auto` or `@speckit-auto`
  - `/speckit-code-review` or `@speckit-code-review`

## 4. Keep these aligned for all 3 tools

- Same skill names: `speckit-auto`, `speckit-code-review`
- Same trigger phrases in `description`
- Same stage flow and output contract
- Same `state_file` / `fixes[]` behavior for the review loop

## 5. Recommended validation

- Test one simple trigger for each tool:
  - Copilot: ask for `speckit-auto`
  - Claude Code: run `/speckit-auto`
  - OpenCode: run `/speckit-auto`
- Confirm `speckit-code-review` is invoked as a skill/command, not as a task agent.
