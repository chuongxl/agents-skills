# Installation

How to install the skills in this repository into each supported agent.

## 1. Pick an install location

| Agent | Location | Scope |
|-------|----------|-------|
| GitHub Copilot CLI | `~/.agents/skills/` | user-wide, all repos |
| GitHub Copilot (repo) | `.github/skills/` | one repository |
| Claude Code | `~/.claude/skills/` | user-wide |
| Claude Code (repo) | `.claude/skills/` | one repository |
| OpenCode | `~/.config/opencode/skills/` | user-wide |
| OpenCode (repo) | `.opencode/skills/` | one repository |

## 2. Copy the skills you want

```bash
# One skill, user-wide
mkdir -p ~/.agents/skills
cp -r speckit-auto ~/.agents/skills/

# All skills, user-wide
for skill in */SKILL.md; do
  cp -r "$(dirname "$skill")" ~/.agents/skills/
done
```

Prefer symlinks while developing, so edits take effect without re-copying:

```bash
ln -sfn "$PWD/speckit-auto" ~/.agents/skills/speckit-auto
```

## 3. Restart the agent session

Skills are discovered at session start. Restart your IDE or CLI session, then
confirm the skill resolves by naming it directly (for example, "run
speckit-code-review").

## Dependency Graph

Some skills call others. Install the dependencies too, or the caller will fail
mid-run.

| Skill | Requires |
|-------|----------|
| `speckit-auto` | `jira-to-speckit`, `speckit-code-review` |
| `speckit-code-review` | — |
| `jira-to-speckit` | — |
| `job-security-scan` | — |

For `speckit-auto` you effectively want all three speckit skills installed
together.

## Per-Skill Prerequisites

### `jira-to-speckit`

Add Jira credentials to the `.env` file at your **project** root (never commit
them):

```dotenv
JIRA_URL=https://your-org.atlassian.net
JIRA_USERNAME=you@example.com
JIRA_API_TOKEN=...
```

### `job-security-scan`

Needs `bash`, `git`, and Python 3.8+. Security tools are installed on first run
via Homebrew (macOS) or curl/apt (Linux):

```bash
bash ~/.agents/skills/job-security-scan/scripts/install-tools.sh
```

Then edit `assets/repository.md` to describe your team and repos before the
first scan.

### `speckit-auto`

Choose an integration provider once; the choice is persisted:

```
speckit-auto --integration github-speckit   # repo-installed GitHub Spec Kit agents
speckit-auto --integration superpowers      # the obra/superpowers skills library
```

Invocation differs per host: `/speckit-auto ...` on GitHub Copilot and Claude Code, or the same
flags embedded in a natural-language message on OpenCode (which has no skill slash commands).
`speckit-auto` auto-detects the host at runtime via `references/shared/host-adaptation.md`.

## Keeping Installs Consistent

Whichever agent you use, the following must stay aligned:

- Folder name equals the `name` in `SKILL.md` frontmatter.
- Trigger phrases in `description` are identical across agents.
- `speckit-code-review` is invoked as a **skill**, never as a background task
  agent — its caller needs the JSON verdict in-band.

Run the validator before installing to confirm the definitions are well formed:

```bash
python3 tools/validate_skills.py
```

## Troubleshooting

| Symptom | Cause | Fix |
|---------|-------|-----|
| Agent does not see the skill | Session started before the copy | Restart the session |
| "skill not found" when one skill calls another | Dependency not installed | See the dependency graph above |
| Skill loads but does nothing | Folder/`name` mismatch | Run `python3 tools/validate_skills.py` |
| Jira steps fail with 401/403 | Missing or stale `.env` credentials | Regenerate the Jira API token |
