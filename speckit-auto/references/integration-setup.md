# Integration Setup (`--integration` Invocations Only)

Load this **only** when `--integration` is present in the command. A pipeline run never needs it.

Canonical provider list and resolution rules: [integration-mode.md](integration-mode.md).

## Setup Invocation

```
/speckit-auto --integration github-speckit
/speckit-auto --integration superpowers
```

**Setup-only. The pipeline does NOT run.** Steps:

1. Normalize the value: trim, lowercase, map aliases (`github`, `speckit`, `spec-kit`,
   `github-spec-kit` → `github-speckit`; `superpower`, `obra-superpowers` → `superpowers`).
2. If the value is not one of the two supported providers, report the error and stop.
3. Persist it (see Persistence below).
4. Report and end the turn:
   - resolved provider
   - file path written
   - scope (repo-local or global)
   - next command to run: `/speckit-auto --issue <jira-url>` or `/speckit-auto "<requirement>"`

This is the **only** case where ending the turn without running the pipeline is correct.
It does not violate the Absolute Operating Premise — setup is the requested work and it completed.

Setup ignores all other arguments. If `--issue` or requirement text is also supplied alongside
`--integration`, still perform setup only, and echo the ignored argument in the report so the user
can re-run it.

## Persistence

| Scope | Path | Meaning |
|-------|------|---------|
| Repo-local | `<repo-root>/.speckit/integration.json` | This repository's provider |
| Global | `<skill-dir>/.state/integration.json` — the directory this `SKILL.md` was discovered from (e.g. `~/.agents/skills/speckit-auto/` on Copilot, `~/.claude/skills/speckit-auto/` on Claude Code, `~/.config/opencode/skills/speckit-auto/` on OpenCode) | Default for repos with no local file |

File format (identical for both scopes):

```json
{
  "integration": "github-speckit",
  "updated_at": "2026-08-11T13:40:00Z",
  "set_by": "speckit-auto"
}
```

Write rules:

- Create parent directories if missing (`mkdir -p`).
- Repo-local write requires a git repo — resolve the root with `git rev-parse --show-toplevel`.
- Write **repo-local** by default on setup.
- Write **global** instead when `--global` is passed, or when the current directory is not inside a
  git repository.
- Overwrite silently if the file already exists; report the previous value in the setup output.
- Add `.speckit/` to `.gitignore` only if `.gitignore` exists and does not already ignore it.
  Never create a `.gitignore` just for this. (A pipeline run covers this case instead — see
  [shared/scratch-hygiene.md](shared/scratch-hygiene.md).)

## Errors

| Condition | Behavior |
|-----------|----------|
| `--integration` given with an unsupported value | Stop. Report the received value and the two valid values. Do not write any file. |
| `--integration` given with no value | Stop. Ask once for the value, then perform setup in the same turn. |
| Repo-local write fails (not a git repo, permissions) | Fall back to the global path and report the fallback. Do not stop. |
