# Integration Mode (Provider Selection)

`speckit-auto` is a **factory**: it selects one delivery provider, then delegates every stage to
that provider's reference files. This file defines how the provider is chosen, stored, and resolved.

## Supported Providers

| `integration` value | Provider | Stage references |
|---------------------|----------|------------------|
| `github-speckit` | Repo-installed GitHub Spec Kit agents (`.github/agents/speckit.*`) | `references/github-speckit/` |
| `superpowers` | `obra/superpowers` skills library (`superpowers:*` skills) | `references/superpowers/` |

No other value is valid. An unrecognized value is a hard error (see Errors below).

## Two Invocation Intents

`speckit-auto` behaves differently depending on whether `--integration` is present.

### A. Setup Invocation — `--integration` IS present

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

### B. Pipeline Invocation — `--integration` is ABSENT

```
/speckit-auto --issue https://example.atlassian.net/browse/ABC-123
/speckit-auto "requirement text"
/speckit-auto --issue <url> --yolo
```

Resolve the provider from storage (see Resolution below), then run that provider's pipeline
immediately in the same turn. Never end the turn merely because the provider had to be resolved.

## Persistence

Two scopes. Repo-local always wins over global.

| Scope | Path | Meaning |
|-------|------|---------|
| Repo-local | `<repo-root>/.speckit/integration.json` | This repository's provider |
| Global | `~/.agents/skills/speckit-auto/.state/integration.json` | Default for repos with no local file |

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
  Never create a `.gitignore` just for this.

## Resolution Precedence (Pipeline Invocation)

Resolve the provider by taking the **first** match:

1. `--integration <value>` in the current command — not applicable in pipeline invocation, since
   that is a setup invocation; listed only to make the ordering explicit.
2. Repo-local `<repo-root>/.speckit/integration.json` → `integration` field.
3. Global `~/.agents/skills/speckit-auto/.state/integration.json` → `integration` field.
4. **Nothing stored anywhere** → run First-Run Selection below.

Once resolved, record it in run state as `integration` and reuse it for every stage of the run.
Never re-read the file mid-run and never switch provider mid-run.

## First-Run Selection (No Stored Mode Anywhere)

Provider detection is driven **solely** by `integration.json`. Never infer the provider from repo
contents (do not probe for `.github/agents/speckit.*`, superpowers skill files, or any other
artifact) — a missing provider installation is not a selection signal, it is handled by that
provider's Stage 01 preflight, which auto-installs the missing framework.

When neither the repo-local nor the global file exists:

1. Ask the user **once** to choose, with exactly these two choices and no recommendation:
   - `github-speckit`
   - `superpowers`
2. Persist the answer using the Persistence rules above (repo-local when in a git repo).
3. **Continue the pipeline immediately in the same turn** with that provider. Do not ask the user
   to re-run the command — this ask is a required-input ask, not a stop condition.
4. Stage 01 preflight of the selected provider then verifies that framework is installed and
   auto-installs it if missing. Provider selection never depends on that outcome.

## Dispatch (Factory)

After the provider is resolved, load stage files from that provider's directory only:

| Stage | `github-speckit` | `superpowers` |
|-------|------------------|---------------|
| 01 Preflight + Intake | `references/github-speckit/stage-01-preflight-intake.md` | `references/superpowers/stage-01-preflight-intake.md` |
| 02 Spec / Design | `references/github-speckit/stage-02-spec-design-flow.md` | `references/superpowers/stage-02-spec-design-flow.md` |
| 03 Implement + Review Loop | `references/github-speckit/stage-03-implement-and-code-review-loop.md` | `references/superpowers/stage-03-implement-and-code-review-loop.md` |
| 04 Human Review + Commit | `references/github-speckit/stage-04-human-review-and-commit.md` | `references/superpowers/stage-04-human-review-and-commit.md` |
| 05 YOLO Commit | `references/github-speckit/stage-05-yolo-commit-flow.md` | `references/superpowers/stage-05-yolo-commit-flow.md` |
| 06 Completion | `references/github-speckit/stage-06-spec-completion.md` | `references/superpowers/stage-06-spec-completion.md` |

Provider-agnostic references under `references/shared/` are loaded by both providers.
Never load a stage file from the provider that was not selected.

## Errors

| Condition | Behavior |
|-----------|----------|
| `--integration` given with an unsupported value | Stop. Report the received value and the two valid values. Do not write any file. |
| `--integration` given with no value | Stop. Ask once for the value, then perform setup in the same turn. |
| Stored file exists but is unparseable or has an unsupported `integration` value | Warn, ignore the file, and fall through to the next precedence level (repo-local → global → First-Run Selection). |
| Repo-local write fails (not a git repo, permissions) | Fall back to the global path and report the fallback. Do not stop. |
